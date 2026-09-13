"""pgvector 语义检索模块。

系统把指标口径、维度、表结构、标准实体名称和示例问题整理成文档，再调用向量模型
生成 embedding 写入 PostgreSQL。用户提问时，先召回最相关的少量文档交给大模型，
帮助它理解业务术语和标准名称。召回结果只提供上下文，不直接决定或执行 SQL。
"""

import argparse
import asyncio
import hashlib
import time
import uuid
from collections import Counter

import httpx
from sqlalchemy import delete, func, insert, select, update

from . import schema as s
from .catalog import TABLE_CATALOG
from .config import settings
from .db import engine
from .semantic import DIMENSIONS, METRICS


class EmbeddingError(RuntimeError):
    """向量接口不可用或返回格式不符合配置。"""
    pass


METRIC_ALIASES = {
    "revenue": ["收入", "营收", "确认收入"],
    "signed": ["签约额", "合同额", "新签"],
    "payments": ["回款", "回款额", "收款"],
    "cost": ["成本", "直接成本"],
    "gross_profit": ["毛利", "毛利润"],
    "gross_margin": ["毛利率"],
    "attainment": ["达成率", "目标完成率", "收入目标达成率"],
    "floor": ["保底", "保底收入"], "forecast": ["预测", "滚动预测", "预测收入"],
    "outstanding_receivables": ["未回款", "应收余额"], "overdue_receivables": ["逾期应收", "逾期未回款"],
}
# 这些文字用于向量检索解释数据血缘，真正执行口径仍以 query.py 为准。
METRIC_SOURCES = {
    "revenue": "analytics.revenue_entries.amount_ex_tax，按 recognition_date；经 contract_items 关联合同和产品",
    "signed": "analytics.contract_items.amount_ex_tax，关联 analytics.contracts.signed_date，并排除 cancelled 合同",
    "payments": "analytics.payment_entries.amount_ex_tax，按 payment_date；该事实只有合同粒度",
    "cost": "analytics.cost_entries.amount_ex_tax，按 cost_date；经 contract_items 关联合同和产品",
    "gross_profit": "analytics.revenue_entries 与 analytics.cost_entries 分别聚合后相减",
    "gross_margin": "analytics.revenue_entries 与 analytics.cost_entries 分别聚合后计算比率",
    "attainment": "analytics.revenue_entries 与 analytics.monthly_targets 分别聚合后计算比率",
    "floor": "analytics.monthly_targets.floor_amount，按 month",
    "forecast": "analytics.monthly_targets.forecast_amount，按 month",
    "outstanding_receivables": "analytics.receivable_entries 应收金额减已核销金额",
    "overdue_receivables": "到期日前尚未结清的应收余额",
}
DIMENSION_ALIASES = {
    "region": ["区域", "大区"],
    "city": ["城市"],
    "org_unit": ["经营单元", "代表处", "组织"],
    "industry": ["行业"],
    "customer": ["客户"],
    "product_line": ["产品线", "业务线"],
    "salesperson": ["销售", "销售人员", "负责人"],
    "contract": ["合同", "合同清单", "签约合同", "合同列表"],
    "receivable_plan": ["应收计划", "单笔应收", "哪一笔应收", "应收明细"],
    "month": ["月份", "按月", "月度"],
}
EXAMPLES = [
    ("销售人员数量与清单", "有多少销售人员，列出20个。使用 master_data 查询，entity=salesperson，intent=count_and_list，limit=20，图表 table。"),
    ("客户数量与清单", "有多少个客户或列出客户。使用 master_data 查询，entity=customer；按问题选择 count、list 或 count_and_list，默认清单20条。"),
    ("基础资料查询", "产品、产品线、经营单元、行业的数量和清单使用 master_data 查询，不需要经营指标和时间范围。"),
    ("收入排名", "今年各经营单元确认收入排名。指标 revenue，维度 org_unit，按值降序。"),
    ("收入趋势", "华东区今年按月收入趋势。指标 revenue，筛选 region=华东，维度 month，折线图。"),
    ("同比", "今年收入与去年同期相比。指标 revenue，比较方式 yoy。"),
    ("环比", "2026年8月回款额比上个月变化多少。指标 payments，比较方式 previous_period。"),
    ("毛利率", "2026年8月各产品线毛利率。指标 gross_margin，维度 product_line。"),
    ("目标达成", "今年各区域收入目标达成率。指标 attainment，维度 region，仅使用完整月份。"),
    ("逾期应收", "今年各经营单元逾期应收金额。指标 overdue_receivables，维度 org_unit。"),
    ("客户合同清单", "某客户签约了哪些合同。指标 signed，维度 contract，筛选 customer=客户标准名称，图表 table；未指定时间时查询完整数据覆盖期，返回合同编号、合同名称和签约额。"),
    ("最高单笔逾期应收", "某客户哪一笔合同应收计划逾期应收最高。指标 overdue_receivables，维度 receivable_plan，筛选 customer=客户标准名称，按值降序，limit=1，图表 table；未指定时间时查询完整数据覆盖期。"),
]


def _doc(key, kind, title, content, metadata, version):
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return {
        "document_key": key,
        "kind": kind,
        "title": title,
        "content": content,
        "metadata": metadata,
        "version": version,
        "content_hash": digest,
        "active": True,
    }


def catalog_documents(conn, version):
    """为指标、维度、表结构和实体值生成版本化语义文档。"""
    docs = []
    for code, spec in METRICS.items():
        aliases = METRIC_ALIASES[code]
        docs.append(
            _doc(
                f"metric:{code}",
                "metric",
                spec["name"],
                f"指标：{spec['name']}（{code}）。别名：{'、'.join(aliases)}。口径：{spec['definition']} 单位：{spec['unit']}。数据来源：{METRIC_SOURCES[code]}。",
                {"metric": code, "aliases": aliases, "sources": METRIC_SOURCES[code]},
                version,
            )
        )
    for code, name in DIMENSIONS.items():
        aliases = DIMENSION_ALIASES[code]
        docs.append(
            _doc(
                f"dimension:{code}",
                "dimension",
                name,
                f"分析维度：{name}（{code}）。常见说法：{'、'.join(aliases)}。",
                {"dimension": code, "aliases": aliases},
                version,
            )
        )
    for full_name, spec in TABLE_CATALOG.items():
        if not full_name.startswith("analytics."):
            continue
        columns = "；".join(f"{name}：{comment}" for name, comment in spec["columns"].items())
        docs.append(
            _doc(
                f"table:{full_name}",
                "table",
                full_name,
                f"数据库对象 {full_name}。{spec['comment']} 字段：{columns}",
                {"table": full_name},
                version,
            )
        )
    entity_sources = {
        # 实体值也进入索引，使用户问题中的客户或组织名称能匹配标准筛选值。
        "region": select(s.org_units.c.region).distinct(),
        "city": select(s.org_units.c.city).distinct(),
        "org_unit": select(s.org_units.c.name).distinct(),
        "industry": select(s.industries.c.name).distinct(),
        "customer": select(s.customers.c.name).distinct(),
        "product_line": select(s.product_lines.c.name).distinct(),
        "salesperson": select(s.salespeople.c.name).distinct(),
    }
    for dimension, statement in entity_sources.items():
        for value in conn.scalars(statement.order_by(None)):
            docs.append(
                _doc(
                    f"entity:{dimension}:{value}",
                    "entity",
                    value,
                    f"{DIMENSIONS[dimension]}实体：{value}。查询筛选字段为 {dimension}，筛选值必须使用完整标准名称。",
                    {"dimension": dimension, "value": value},
                    version,
                )
            )
    for index, (title, content) in enumerate(EXAMPLES):
        docs.append(_doc(f"example:{index}", "example", title, content, {}, version))
    return docs


def _embedding_credentials():
    cfg = settings()
    return (
        cfg.embedding_base_url.strip() or cfg.llm_base_url,
        cfg.embedding_api_key.strip() or cfg.llm_api_key.strip(),
    )


async def embed_texts(texts):
    """批量生成向量，并在写入 PostgreSQL 前校验数量和维度。"""
    cfg = settings()
    base_url, api_key = _embedding_credentials()
    if not api_key:
        raise EmbeddingError("未配置向量模型 API Key")
    body = {
        "model": cfg.embedding_model,
        "input": texts,
        "dimensions": cfg.embedding_dimensions,
        "encoding_format": "float",
    }
    try:
        async with httpx.AsyncClient(timeout=cfg.llm_timeout, follow_redirects=False) as client:
            response = await client.post(
                base_url.rstrip("/") + "/embeddings",
                headers={"Authorization": "Bearer " + api_key},
                json=body,
            )
        if response.status_code != 200:
            raise EmbeddingError(f"向量模型返回 HTTP {response.status_code}")
        rows = sorted(response.json()["data"], key=lambda item: item["index"])
        vectors = [row["embedding"] for row in rows]
        if len(vectors) != len(texts) or any(len(v) != cfg.embedding_dimensions for v in vectors):
            raise EmbeddingError("向量模型返回的数量或维度不符合配置")
        return vectors
    except httpx.TimeoutException as exc:
        raise EmbeddingError("向量模型响应超时") from exc
    except httpx.HTTPError as exc:
        raise EmbeddingError("无法连接向量模型") from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise EmbeddingError("向量模型返回格式异常") from exc


async def sync_index(force=False):
    """语义内容变化时，以事务方式替换当前数据版本的向量索引。"""
    cfg = settings()
    with engine.connect() as conn:
        dataset = conn.execute(select(s.dataset_versions).order_by(s.dataset_versions.c.id.desc())).mappings().first()
        if not dataset:
            raise RuntimeError("请先初始化业务数据")
        version = dataset["version"]
        docs = catalog_documents(conn, version)
        current_hashes = set(conn.scalars(
            select(s.semantic_documents.c.content_hash).join(s.semantic_chunks).where(
                s.semantic_documents.c.version == version,
                s.semantic_documents.c.active.is_(True),
                s.semantic_chunks.c.embedding_model == cfg.embedding_model,
            )
        ))
    expected_hashes = {doc["content_hash"] for doc in docs}
    # 内容哈希完全一致时无需再次调用向量接口，可减少耗时和模型费用。
    if current_hashes == expected_hashes and len(current_hashes) == len(docs) and not force:
        return {"status": "current", "version": version, "documents": len(docs)}

    job_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(insert(s.embedding_jobs).values(id=job_id, version=version, embedding_model=cfg.embedding_model, status="running"))
    try:
        vectors = []
        # 小批量调用向量接口，避免单次请求过大；全部成功后才替换旧索引。
        for offset in range(0, len(docs), 10):
            vectors.extend(await embed_texts([doc["content"] for doc in docs[offset : offset + 10]]))
        with engine.begin() as conn:
            old_ids = select(s.semantic_documents.c.id).where(s.semantic_documents.c.version == version)
            conn.execute(delete(s.semantic_chunks).where(s.semantic_chunks.c.document_id.in_(old_ids)))
            conn.execute(delete(s.semantic_documents).where(s.semantic_documents.c.version == version))
            for doc, vector in zip(docs, vectors, strict=True):
                document_id = conn.scalar(insert(s.semantic_documents).values(**doc).returning(s.semantic_documents.c.id))
                conn.execute(insert(s.semantic_chunks).values(document_id=document_id, content=doc["content"], embedding=vector, embedding_model=cfg.embedding_model))
            conn.execute(update(s.embedding_jobs).where(s.embedding_jobs.c.id == job_id).values(status="success", document_count=len(docs), finished_at=func.now()))
        return {"status": "success", "version": version, "documents": len(docs)}
    except Exception as exc:
        with engine.begin() as conn:
            conn.execute(update(s.embedding_jobs).where(s.embedding_jobs.c.id == job_id).values(status="error", error=str(exc)[:500], finished_at=func.now()))
        raise


async def retrieve(question, version):
    """合并名称精确命中与余弦相似召回，并限制各类文档数量。"""
    cfg = settings()
    started = time.monotonic()
    vector = (await embed_texts([question]))[0]
    distance = s.semantic_chunks.c.embedding.cosine_distance(vector).label("distance")
    base = (
        select(s.semantic_documents, distance)
        .join(s.semantic_chunks)
        .where(
            s.semantic_documents.c.version == version,
            s.semantic_documents.c.active.is_(True),
            s.semantic_chunks.c.embedding_model == cfg.embedding_model,
        )
    )
    with engine.connect() as conn:
        semantic = conn.execute(base.order_by(distance).limit(cfg.retrieval_top_k * 12)).mappings().all()
        exact = conn.execute(
            base.where(func.strpos(func.lower(question), func.lower(s.semantic_documents.c.title)) > 0)
            .order_by(distance)
            .limit(cfg.retrieval_top_k)
        ).mappings().all()
    combined = []
    seen = set()
    kind_counts = Counter()
    exact_ids = {row["id"] for row in exact}
    for row in [*exact, *semantic]:
        # 精确名称优先；分类上限避免大量实体文档挤占模型上下文。
        if row["id"] in seen:
            continue
        is_exact = row["id"] in exact_ids
        if not is_exact and row["kind"] == "entity" and float(row["distance"]) > 0.35:
            continue
        if not is_exact and row["kind"] == "example" and kind_counts["example"] >= 2:
            continue
        if not is_exact and row["kind"] == "table" and kind_counts["table"] >= 3:
            continue
        if not is_exact and row["kind"] == "dimension" and kind_counts["dimension"] >= 4:
            continue
        if not is_exact and row["kind"] == "metric" and kind_counts["metric"] >= 3:
            continue
        seen.add(row["id"])
        combined.append(row)
        kind_counts[row["kind"]] += 1
        if len(combined) == cfg.retrieval_top_k:
            break
    hits = [
        {
            "document_key": row["document_key"],
            "kind": row["kind"],
            "title": row["title"],
            "content": row["content"],
            "metadata": row["metadata"],
            "distance": round(float(row["distance"]), 6),
            "match": "exact" if row["id"] in exact_ids else "semantic",
        }
        for row in combined
    ]
    return {
        "context": hits,
        "audit": {
            "question": question,
            "embedding_model": cfg.embedding_model,
            "top_k": cfg.retrieval_top_k,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "hits": [{k: hit[k] for k in ["document_key", "kind", "title", "distance", "match"]} for hit in hits],
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["sync"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.command == "sync":
        print(asyncio.run(sync_index(force=args.force)))


if __name__ == "__main__":
    main()
