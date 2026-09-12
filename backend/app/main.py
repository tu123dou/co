"""FastAPI 接口入口。

这个文件负责接收浏览器请求，并把一次问数串成完整流程：读取对话上下文、
从 pgvector 召回业务知识、让大模型生成结构化计划、执行只读 SQL，最后保存
回答和审计记录。具体 SQL 规则放在 query.py，模型调用放在 llm.py。
"""

import asyncio, csv, io, json, logging, time, uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update, delete, text, func
from sqlalchemy.exc import SQLAlchemyError
from . import schema as s
from .db import engine, query_engine
from .auth import current_user, token_for, verify_password
from .config import settings
from .semantic import METRICS, DIMENSIONS
from .query import compile_plan, execute_plan, render_business_sql, render_executable_sql
from .llm import interpret, configured, call_model, ModelError
from .retrieval import EmbeddingError, retrieve
from .catalog import TABLE_CATALOG
from .user_settings import (
    ALLOWED_LLM_MODELS,
    ensure_user_settings,
    record_successful_question,
)

app = FastAPI(title="经管之星 API", version="0.1.0")
log = logging.getLogger("jingguan")
User = Annotated[dict, Depends(current_user)]
login_attempts = defaultdict(deque)

# 允许本地正式前端和指定的开发前端携带登录 Cookie 调用 API。
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def origin_guard(request, call_next):
    """限制写请求来源，并为所有响应添加基础安全与禁缓存响应头。"""
    if request.method not in ["GET", "HEAD", "OPTIONS"]:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in settings().allowed_origins:
            return JSONResponse({"detail": "请求来源不允许"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(SQLAlchemyError)
async def db_error(request, exc):
    log.error("database_request_failed type=%s", type(exc).__name__)
    return JSONResponse(
        {"detail": "数据库暂时不可用，请确认数据库已启动并完成初始化"}, status_code=503
    )


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


@app.post("/api/auth/login")
def login(body: Login, request: Request, response: Response):
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    queue = login_attempts[key]
    while queue and queue[0] < now - 60:
        queue.popleft()
    if len(queue) >= 10:
        raise HTTPException(429, "尝试过于频繁，请稍后再试")
    queue.append(now)
    with engine.connect() as conn:
        user = (
            conn.execute(
                select(s.users).where(
                    s.users.c.username == body.username, s.users.c.active.is_(True)
                )
            )
            .mappings()
            .first()
        )
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "用户名或密码错误")
    response.set_cookie(
        "session",
        token_for(user["id"]),
        httponly=True,
        samesite="strict",
        secure=settings().cookie_secure,
        max_age=43200,
        path="/",
    )
    return {
        "id": user["id"],
        "display_name": user["display_name"],
    }


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("session", path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: User):
    return {k: user[k] for k in ["id", "display_name"]}


@app.get("/api/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


def dataset_info():
    """读取当前演示数据版本以及可查询的起止日期。"""
    with engine.connect() as conn:
        d = (
            conn.execute(
                select(s.dataset_versions).order_by(s.dataset_versions.c.id.desc())
            )
            .mappings()
            .first()
        )
    if not d:
        raise HTTPException(503, "请先初始化业务数据")
    return dict(d)


def get_catalog():
    """读取标准筛选值，供受控查询规划器解析实体名称。"""
    with engine.connect() as conn:
        catalog = {
            "region": list(conn.scalars(select(s.org_units.c.region).distinct())),
            "city": list(conn.scalars(select(s.org_units.c.city))),
            "org_unit": list(conn.scalars(select(s.org_units.c.name))),
            "industry": list(conn.scalars(select(s.industries.c.name))),
            "product_line": list(conn.scalars(select(s.product_lines.c.name))),
            "salesperson": list(conn.scalars(select(s.salespeople.c.name))),
        }
    return catalog


def dataset_table_rows(counts):
    """把数据表记录数与数据库业务字典合并，供前端解释每张表的用途。"""
    rows = []
    for table_name, count in counts.items():
        comment = TABLE_CATALOG.get(f"analytics.{table_name}", {}).get("comment", "")
        purpose = comment.partition("用途：")[2].partition("。粒度：")[0]
        rows.append(
            {
                "table": table_name,
                "description": purpose or comment or "业务数据表",
                "count": count,
            }
        )
    return rows


@app.get("/api/catalog")
def catalog(user: User):
    d = dataset_info()
    with engine.begin() as conn:
        user_settings = ensure_user_settings(conn, user["id"])
    return {
        "metrics": METRICS,
        "dimensions": DIMENSIONS,
        "values": get_catalog(),
        "dataset": d,
        "data_tables": dataset_table_rows(d["counts"]),
        "model": {
            "name": user_settings["llm_model"],
            "available": ALLOWED_LLM_MODELS,
            "configured": configured(),
        },
        "examples": [
            "今年各经营单元确认收入排名",
            "今年各产品线的收入占比",
            "华东区今年按月收入趋势，与去年同期相比",
            "2026年8月各产品线毛利率",
            "今年各区域收入目标达成率",
            "2026年8月回款额比上个月变化多少",
            "今年各经营单元逾期应收金额",
            "明瀚教育科研集团0034客户哪一笔合同应收计划逾期应收最高",
            "2026年8月各产品线签约额排名",
            "今年各行业确认收入排名",
            "上海代表处今年毛利率是多少",
            "2026年第二季度各区域确认收入",
            "今年每月签约额趋势",
            "今年各区域回款额排名",
            "今年各客户未回款金额排名",
            "今年各销售人员确认收入排名",
            "通用计算2026年8月直接成本是多少",
            "今年各经营单元滚动预测金额",
        ],
    }


class ModelTest(BaseModel):
    model: str | None = None

    @field_validator("model")
    @classmethod
    def validate_model(cls, value):
        if value is not None and value not in ALLOWED_LLM_MODELS:
            raise ValueError("不支持该模型")
        return value


@app.post("/api/model/test")
async def test_model(body: ModelTest, user: User):
    with engine.begin() as conn:
        saved_model = ensure_user_settings(conn, user["id"])["llm_model"]
    model = body.model or saved_model
    try:
        start = time.monotonic()
        await call_model(
            [{"role": "user", "content": "请只回复 OK"}],
            model=model,
            max_tokens=16,
        )
        return {
            "ok": True,
            "model": model,
            "duration_ms": round((time.monotonic() - start) * 1000),
        }
    except ModelError as exc:
        raise HTTPException(502, str(exc))


def owned(cid, uid, conn):
    row = (
        conn.execute(
            select(s.conversations).where(
                s.conversations.c.id == cid, s.conversations.c.user_id == uid
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, "会话不存在")
    return dict(row)


@app.get("/api/conversations")
def conversations(user: User):
    with engine.connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                select(s.conversations)
                .where(s.conversations.c.user_id == user["id"])
                .order_by(
                    s.conversations.c.pinned.desc(), s.conversations.c.updated_at.desc()
                )
            ).mappings()
        ]


@app.post("/api/conversations")
def new_conversation(user: User):
    cid = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            s.conversations.insert().values(id=cid, user_id=user["id"], title="新对话")
        )
    return {"id": cid}


@app.get("/api/conversations/{cid}")
def conversation(cid: str, user: User):
    with engine.connect() as conn:
        convo = owned(cid, user["id"], conn)
        convo["messages"] = [
            dict(r)
            for r in conn.execute(
                select(s.messages)
                .where(s.messages.c.conversation_id == cid)
                .order_by(s.messages.c.created_at, s.messages.c.id)
            ).mappings()
        ]
    return convo


class ConversationEdit(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    pinned: bool | None = None


@app.patch("/api/conversations/{cid}")
def edit_conversation(cid: str, body: ConversationEdit, user: User):
    with engine.begin() as conn:
        owned(cid, user["id"], conn)
        values = body.model_dump(exclude_none=True)
        if values:
            conn.execute(
                update(s.conversations)
                .where(s.conversations.c.id == cid)
                .values(**values)
            )
    return {"ok": True}


@app.delete("/api/conversations/{cid}")
def remove_conversation(cid: str, user: User):
    with engine.begin() as conn:
        owned(cid, user["id"], conn)
        conn.execute(delete(s.conversations).where(s.conversations.c.id == cid))
    return {"ok": True}


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class Favorite(Question):
    pass


class WorkbenchSettingsEdit(BaseModel):
    """用户可以修改的工作台设置；未提交的字段保持原值。"""

    welcome_enabled: bool | None = None
    welcome_title: str | None = Field(default=None, min_length=1, max_length=100)
    welcome_message: str | None = Field(default=None, min_length=1, max_length=500)
    starter_questions: list[str] | None = None
    suggestions_enabled: bool | None = None
    common_questions_enabled: bool | None = None
    common_question_threshold: int | None = Field(default=None, ge=1, le=100)
    llm_model: str | None = None

    @field_validator("welcome_title", "welcome_message")
    @classmethod
    def strip_text(cls, value):
        if value is not None and not value.strip():
            raise ValueError("内容不能为空")
        return value.strip() if value is not None else value

    @field_validator("starter_questions")
    @classmethod
    def validate_starter_questions(cls, value):
        if value is None:
            return value
        cleaned = [question.strip() for question in value if question.strip()]
        if len(cleaned) > 10:
            raise ValueError("开场问题最多十条")
        if any(len(question) > 1000 for question in cleaned):
            raise ValueError("单条开场问题不能超过一千字")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("开场问题不能重复")
        return cleaned

    @field_validator("llm_model")
    @classmethod
    def validate_llm_model(cls, value):
        if value is not None and value not in ALLOWED_LLM_MODELS:
            raise ValueError("不支持该模型")
        return value


def public_workbench_settings(row):
    """只返回浏览器需要的用户配置，不包含任何模型凭据。"""
    return {
        key: row[key]
        for key in [
            "welcome_enabled",
            "welcome_title",
            "welcome_message",
            "starter_questions",
            "suggestions_enabled",
            "common_questions_enabled",
            "common_question_threshold",
            "llm_model",
            "updated_at",
        ]
    }


@app.get("/api/workbench/settings")
def get_workbench_settings(user: User):
    with engine.begin() as conn:
        return public_workbench_settings(ensure_user_settings(conn, user["id"]))


@app.patch("/api/workbench/settings")
def edit_workbench_settings(body: WorkbenchSettingsEdit, user: User):
    values = body.model_dump(exclude_none=True)
    with engine.begin() as conn:
        ensure_user_settings(conn, user["id"])
        if values:
            conn.execute(
                update(s.user_workbench_settings)
                .where(s.user_workbench_settings.c.user_id == user["id"])
                .values(**values, updated_at=func.now())
            )
        row = ensure_user_settings(conn, user["id"])
    return public_workbench_settings(row)


@app.get("/api/common-questions")
def common_questions(user: User):
    with engine.begin() as conn:
        prefs = ensure_user_settings(conn, user["id"])
        if not prefs["common_questions_enabled"]:
            return []
        return [
            dict(row)
            for row in conn.execute(
                select(
                    s.user_question_stats.c.question,
                    s.user_question_stats.c.success_count,
                    s.user_question_stats.c.last_asked_at,
                )
                .where(
                    s.user_question_stats.c.user_id == user["id"],
                    s.user_question_stats.c.success_count
                    >= prefs["common_question_threshold"],
                )
                .order_by(
                    s.user_question_stats.c.success_count.desc(),
                    s.user_question_stats.c.last_asked_at.desc(),
                )
                .limit(20)
            ).mappings()
        ]


@app.get("/api/favorites")
def favorites(user: User):
    with engine.connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                select(s.favorite_questions)
                .where(s.favorite_questions.c.user_id == user["id"])
                .order_by(s.favorite_questions.c.created_at.desc())
            ).mappings()
        ]


@app.post("/api/favorites")
def add_favorite(body: Favorite, user: User):
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    with engine.begin() as conn:
        conn.execute(
            pg_insert(s.favorite_questions)
            .values(user_id=user["id"], question=body.question)
            .on_conflict_do_nothing()
        )
    return {"ok": True}


@app.delete("/api/favorites/{fid}")
def delete_favorite(fid: int, user: User):
    with engine.begin() as conn:
        conn.execute(
            delete(s.favorite_questions).where(
                s.favorite_questions.c.id == fid,
                s.favorite_questions.c.user_id == user["id"],
            )
        )
    return {"ok": True}


class Feedback(BaseModel):
    message_id: str
    comment: str = Field(min_length=1, max_length=1000)


class FeedbackReview(BaseModel):
    """回复校对更新项；处理状态只允许待处理和已处理。"""

    status: str
    resolution_note: str | None = Field(default=None, max_length=2000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        if value not in {"pending", "resolved"}:
            raise ValueError("不支持的反馈状态")
        return value


@app.post("/api/feedbacks")
def feedback(body: Feedback, user: User):
    with engine.begin() as conn:
        msg = conn.execute(
            select(s.messages)
            .join(s.conversations)
            .where(
                s.messages.c.id == body.message_id,
                s.conversations.c.user_id == user["id"],
                s.messages.c.role == "assistant",
            )
        ).first()
        if not msg:
            raise HTTPException(404, "回答不存在")
        conn.execute(
            s.feedbacks.insert().values(
                user_id=user["id"], message_id=body.message_id, comment=body.comment
            )
        )
    return {"ok": True}


@app.get("/api/feedbacks")
def list_feedbacks(
    user: User,
    question: str = "",
    username: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 10,
):
    """分页查询回复校对列表，并找到每条助手回答之前最近的用户问题。"""
    if status and status not in {"pending", "resolved"}:
        raise HTTPException(422, "不支持的反馈状态")
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    params = {
        "question": f"%{question.strip()}%",
        "username": f"%{username.strip()}%",
        "status": status,
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }
    statement = text(
        """
        WITH review_rows AS (
            SELECT
                f.id,
                u.display_name,
                f.comment,
                f.status,
                f.resolution_note,
                f.created_at,
                f.updated_at,
                answer.content AS answer,
                answer.result,
                COALESCE((
                    SELECT question.content
                    FROM app.messages AS question
                    WHERE question.conversation_id = answer.conversation_id
                      AND question.role = 'user'
                      AND (question.created_at, question.id) < (answer.created_at, answer.id)
                    ORDER BY question.created_at DESC, question.id DESC
                    LIMIT 1
                ), '') AS question
            FROM app.feedbacks AS f
            JOIN app.users AS u ON u.id = f.user_id
            JOIN app.messages AS answer ON answer.id = f.message_id
        )
        SELECT *, count(*) OVER () AS total
        FROM review_rows
        WHERE question ILIKE :question
          AND display_name ILIKE :username
          AND (:status = '' OR status = :status)
        ORDER BY created_at DESC, id DESC
        LIMIT :limit OFFSET :offset
        """
    )
    with engine.connect() as conn:
        rows = [dict(row) for row in conn.execute(statement, params).mappings()]
    total = rows[0].pop("total") if rows else 0
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


@app.patch("/api/feedbacks/{feedback_id}")
def review_feedback(feedback_id: int, body: FeedbackReview, user: User):
    """保存回复核查状态和处理说明。所有登录用户均可使用此业务能力。"""
    with engine.begin() as conn:
        row = conn.execute(
            update(s.feedbacks)
            .where(s.feedbacks.c.id == feedback_id)
            .values(
                status=body.status,
                resolution_note=(body.resolution_note or "").strip() or None,
                updated_at=datetime.now(timezone.utc),
            )
            .returning(s.feedbacks.c.id)
        ).first()
        if not row:
            raise HTTPException(404, "反馈不存在")
    return {"ok": True}


def summary(result, plan):
    metric = METRICS[plan.metric]
    unit = metric["unit"]

    def fmt(v):
        return "暂无可计算数据" if v is None else f"{v:,.2f}{unit}"

    if result["empty"]:
        return "所选范围没有业务记录。请检查筛选条件或更换时间范围。"
    sentence = f"{plan.start_date} 至 {plan.end_date}，{metric['name']}为 {fmt(result['total'])}。"
    if result["previous_total"] is not None:
        sentence += f"对比期间为 {fmt(result['previous_total'])}。"
        if unit == "%" and result["difference"] is not None:
            sentence += f"变化 {result['difference']:+.2f} 个百分点。"
        elif result["change"] is not None:
            sentence += f"{'同比' if plan.comparison == 'yoy' else '环比'} {result['change']:+.2f}%。"
        else:
            sentence += "对比基数为零，增幅不适用。"
    if plan.dimensions and result["rows"]:
        valid = [r for r in result["rows"] if r["value"] is not None]
        if valid:
            top = max(valid, key=lambda r: r["value"])
            sentence += f"当前展示中，{top['label']}最高，为 {fmt(top['value'])}。"
    if result["truncated"]:
        sentence += (
            f"共 {result['group_count']} 组，展示前 {plan.limit} 组；汇总包含全部分组。"
        )
    return sentence


def validate_filters(plan, catalog):
    """确认模型生成的筛选值能匹配真实业务实体。"""
    for f in plan.filters:
        if f.dimension == "month":
            import re

            if any(not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", v) for v in f.values):
                raise ValueError("月份格式需为 YYYY-MM")
        elif f.dimension == "customer":
            with engine.connect() as conn:
                found = set(
                    conn.scalars(
                        select(s.customers.c.name).where(
                            s.customers.c.name.in_(f.values)
                        )
                    )
                )
            if set(f.values) - found:
                raise ValueError("未找到该客户，请使用完整客户名称")
        elif set(f.values) - set(catalog[f.dimension]):
            raise ValueError(
                "未找到筛选值：" + ", ".join(set(f.values) - set(catalog[f.dimension]))
            )


SOURCE_LABELS = {
    "revenue": ["收入确认流水（analytics.revenue_entries）", "合同明细（analytics.contract_items）"],
    "signed": ["合同台账（analytics.contracts）", "合同明细（analytics.contract_items）"],
    "payments": ["回款流水（analytics.payment_entries）", "合同台账（analytics.contracts）"],
    "cost": ["成本确认流水（analytics.cost_entries）", "合同明细（analytics.contract_items）"],
    "target": ["月度经营目标（analytics.monthly_targets）"],
    "floor": ["月度经营目标（analytics.monthly_targets）"],
    "forecast": ["月度经营目标（analytics.monthly_targets）"],
    "outstanding_receivables": ["合同应收计划（analytics.receivable_entries）", "合同台账（analytics.contracts）"],
    "overdue_receivables": ["合同应收计划（analytics.receivable_entries）", "合同台账（analytics.contracts）"],
}
DIMENSION_LABELS = {
    "region": "区域", "city": "城市", "org_unit": "经营单元",
    "industry": "行业", "customer": "客户", "product_line": "产品线",
    "salesperson": "销售人员", "contract": "合同",
    "receivable_plan": "应收计划", "month": "月份",
}
CHART_LABELS = {"bar": "柱状图", "line": "折线图", "pie": "占比图", "table": "数据表"}


def analysis_intro(question, explanation, plan, dataset):
    """生成查询执行前已经确定的数据源和结构化解析步骤。"""
    sources = []
    for fact in METRICS[plan.metric]["facts"]:
        for source in SOURCE_LABELS[fact]:
            if source not in sources:
                sources.append(source)
    filters = [
        f"{DIMENSION_LABELS[f.dimension]}={ '、'.join(f.values) }"
        for f in plan.filters
    ]
    dimensions = "、".join(DIMENSION_LABELS[d] for d in plan.dimensions) or "不分组（汇总值）"
    return [
        {
            "key": "source",
            "title": "选择数据表与数据时效",
            "status": "complete",
            "items": [
                "选用数据源：" + "、".join(sources),
                f"数据覆盖：{dataset['start_date']} 至 {dataset['cutoff_date']}",
                "业务口径：" + METRICS[plan.metric]["definition"],
            ],
        },
        {
            "key": "plan",
            "title": "解析与计算逻辑",
            "status": "complete",
            "items": [
                f"问题：{question}",
                f"解析结果：{explanation}",
                f"指标：{METRICS[plan.metric]['name']}；分析维度：{dimensions}",
                "筛选条件：" + ("；".join(filters) if filters else "全部"),
                f"排序：{'从高到低' if plan.sort == 'desc' else '从低到高'}；最多展示 {plan.limit} 组",
            ],
        },
    ]


def analysis_sql_step(executions):
    """生成 SQL 展示步骤，同时提供可执行版本和中文口径版本。"""
    return {
        "key": "sql",
        "title": "执行取数 SQL",
        "status": "complete",
        "items": [],
        "executions": [
            {
                "name": "本期 SQL" if index == 0 else "对比期 SQL",
                "executable_sql": execution["executable_sql"],
                "business_sql": execution["business_sql"],
            }
            for index, execution in enumerate(executions)
        ],
    }


def analysis_process(question, explanation, plan, result, dataset):
    """根据真实计划和执行结果生成前端可展示、可审计的五步过程。"""
    preview = [
        f"{row['label']}：{row['value']:,.2f}{METRICS[plan.metric]['unit']}"
        for row in result["rows"][:5]
        if row["value"] is not None
    ]
    return [
        *analysis_intro(question, explanation, plan, dataset),
        analysis_sql_step(result["executions"]),
        {
            "key": "result",
            "title": "展示取数结果",
            "status": "complete",
            "items": [
                f"汇总结果：{result['total']:,.2f}{METRICS[plan.metric]['unit']}" if result["total"] is not None else "汇总结果：暂无可计算数据",
                "前五项：" + ("；".join(preview) if preview else "无明细分组"),
                "预览方式：" + CHART_LABELS[plan.chart],
            ],
        },
        {
            "key": "done",
            "title": "执行结束",
            "status": "complete",
            "items": ["全流程取数和分析已经完成，最终结果已在当前回答中生成。"],
        },
    ]


@app.post("/api/conversations/{cid}/ask")
async def ask(cid: str, body: Question, user: User):
    # PostgreSQL advisory lock is shared across backend workers; one active request per user.
    lock = engine.connect()
    locked = lock.scalar(
        text("SELECT pg_try_advisory_lock(7721, :uid)"), {"uid": user["id"]}
    )
    if not locked:
        lock.close()
        raise HTTPException(409, "上一条问题仍在处理中，请完成或停止后再试")
    try:
        with engine.begin() as conn:
            convo = owned(cid, user["id"], conn)
            user_preferences = ensure_user_settings(conn, user["id"])
            selected_model = user_preferences["llm_model"]
            history = [
                {"role": r["role"], "content": r["content"]}
                for r in conn.execute(
                    select(s.messages)
                    .where(s.messages.c.conversation_id == cid)
                    .order_by(s.messages.c.created_at.desc())
                    .limit(6)
                ).mappings()
            ][::-1]
            conn.execute(
                s.messages.insert().values(
                    id=str(uuid.uuid4()),
                    conversation_id=cid,
                    role="user",
                    content=body.question,
                )
            )
            conn.execute(
                update(s.conversations)
                .where(s.conversations.c.id == cid)
                .values(
                    title=body.question[:50]
                    if convo["title"] == "新对话"
                    else convo["title"],
                    updated_at=func.now(),
                )
            )
    except BaseException:
        lock.execute(text("SELECT pg_advisory_unlock(7721, :uid)"), {"uid": user["id"]})
        lock.close()
        raise

    async def stream():
        """按 NDJSON 逐行返回处理阶段和最终结果，供前端实时展示进度。"""
        started = time.monotonic()
        mid = str(uuid.uuid4())
        plan = None
        usage = {}
        result = None
        content = ""
        status = "error"
        error_code = None
        dataset = None
        retrieval_audit = None
        saved = False

        def event(kind, **kwargs):
            return (
                json.dumps({"type": kind, **kwargs}, ensure_ascii=False, default=str)
                + "\n"
            )

        def persist():
            """仅保存一次最终结果、SQL 执行审计和向量召回审计。"""
            nonlocal saved
            if saved:
                return
            with engine.begin() as conn:
                if not conn.scalar(
                    select(s.conversations.c.id).where(s.conversations.c.id == cid)
                ):
                    return
                conn.execute(
                    s.messages.insert().values(
                        id=mid,
                        conversation_id=cid,
                        role="assistant",
                        content=content,
                        result=result or {"status": status, "error_code": error_code},
                    )
                )
                query_run_id = str(uuid.uuid4())
                conn.execute(
                    s.query_runs.insert().values(
                        id=query_run_id,
                        message_id=mid,
                        plan=plan.model_dump(mode="json") if plan else None,
                        sql="\n\n".join(
                            e["sql"] for e in (result or {}).get("executions", [])
                        ),
                        parameters=(result or {}).get("executions", []),
                        status=status,
                        error_code=error_code,
                        duration_ms=round((time.monotonic() - started) * 1000),
                        model=selected_model,
                        usage=usage,
                        dataset_version=dataset["version"] if dataset else None,
                    )
                )
                if retrieval_audit:
                    conn.execute(
                        s.retrieval_events.insert().values(
                            id=str(uuid.uuid4()),
                            query_run_id=query_run_id,
                            **retrieval_audit,
                        )
                    )
                if status == "success":
                    record_successful_question(conn, user["id"], body.question)
                    conn.execute(
                        update(s.conversations)
                        .where(s.conversations.c.id == cid)
                        .values(
                            context=plan.model_dump(mode="json"), updated_at=func.now()
                        )
                    )
            saved = True

        try:
            # 第一阶段：准备数据范围、可选筛选值和与问题相关的业务知识。
            yield event("status", stage="理解问题", detail="识别指标、时间与筛选条件")
            # 第一条分析事件在任何外部模型调用前发出，让用户立即看到系统已开始工作。
            yield event(
                "analysis",
                step={
                    "key": "source",
                    "title": "选择数据表与数据时效",
                    "status": "running",
                    "items": ["正在读取数据版本、业务目录和可查询时间范围……"],
                },
            )
            dataset = dataset_info()
            catalog = get_catalog()
            yield event(
                "analysis",
                step={
                    "key": "source",
                    "title": "选择数据表与数据时效",
                    "status": "running",
                    "items": [
                        f"已读取数据版本 {dataset['version']}，数据截止 {dataset['cutoff_date']}。",
                        "正在根据问题确认需要使用的业务表……",
                    ],
                },
            )
            yield event(
                "analysis",
                step={
                    "key": "plan",
                    "title": "解析与计算逻辑",
                    "status": "running",
                    "items": ["正在通过 pgvector 匹配相关指标、维度和标准实体名称……"],
                },
            )
            semantic_context = []
            try:
                # 向量召回只增强术语理解；临时失败时退回静态目录，仍执行计划校验。
                retrieval = await retrieve(body.question, dataset["version"])
                semantic_context = retrieval["context"]
                retrieval_audit = retrieval["audit"]
                for hit in semantic_context:
                    if hit["kind"] == "entity":
                        meta = hit["metadata"]
                        catalog.setdefault(meta["dimension"], [])
                        if meta["value"] not in catalog[meta["dimension"]]:
                            catalog[meta["dimension"]].append(meta["value"])
                yield event(
                    "analysis",
                    step={
                        "key": "plan",
                        "title": "解析与计算逻辑",
                        "status": "running",
                        "items": [
                            f"pgvector 已召回 {len(semantic_context)} 条相关业务知识。",
                            "正在请求大模型生成受控查询计划……",
                        ],
                    },
                )
            except EmbeddingError as exc:
                log.warning("semantic_retrieval_unavailable reason=%s", exc)
                retrieval_audit = {
                    "question": body.question,
                    "embedding_model": settings().embedding_model,
                    "top_k": settings().retrieval_top_k,
                    "duration_ms": 0,
                    "hits": [{"error": str(exc)}],
                }
                yield event(
                    "analysis",
                    step={
                        "key": "plan",
                        "title": "解析与计算逻辑",
                        "status": "running",
                        "items": ["向量检索暂不可用，正在使用静态业务目录生成查询计划……"],
                    },
                )
            interpretation, usage = await interpret(
                body.question,
                convo["context"],
                history,
                catalog,
                {k: str(dataset[k]) for k in ["version", "start_date", "cutoff_date"]},
                semantic_context,
                model=selected_model,
            )
            if interpretation.action != "query":
                status = interpretation.action
                content = interpretation.explanation
                result = {"status": status}
            else:
                # 第二阶段：再次校验模型计划，再在线程池中执行同步数据库查询。
                plan = interpretation.plan
                validate_filters(plan, catalog)
                # 先把已经确认的数据源、解析计划和 SQL 流式返回，再开始数据库查询。
                for step in analysis_intro(
                    body.question, interpretation.explanation, plan, dataset
                ):
                    yield event("analysis", step=step)
                preview_sql, preview_params = compile_plan(plan)
                yield event(
                    "analysis",
                    step=analysis_sql_step([
                        {
                            "executable_sql": render_executable_sql(preview_sql, preview_params),
                            "business_sql": render_business_sql(plan),
                        }
                    ]),
                )
                yield event(
                    "analysis",
                    step={
                        "key": "result",
                        "title": "展示取数结果",
                        "status": "running",
                        "items": ["SQL 已生成，正在通过只读账号执行数据库查询……"],
                    },
                )
                yield event(
                    "status", stage="执行取数", detail=interpretation.explanation
                )
                result = await run_in_threadpool(
                    execute_plan,
                    plan,
                    query_engine,
                    dataset["cutoff_date"],
                    dataset["start_date"],
                )
                yield event("status", stage="整理结果", detail="核对指标并生成图表")
                # 第三阶段：生成确定性的文字摘要，并附上前端绘图所需的结构化数据。
                content = summary(result, plan)
                status = "success"
                completed_at = datetime.now(timezone.utc).isoformat()
                complete_process = analysis_process(
                    body.question, interpretation.explanation, plan, result, dataset
                )
                for step in complete_process[3:]:
                    yield event("analysis", step=step)
                result.update(
                    {
                        "status": status,
                        "plan": plan.model_dump(mode="json"),
                        "metric": METRICS[plan.metric],
                        "dataset_version": dataset["version"],
                        "cutoff_date": str(dataset["cutoff_date"]),
                        "model": selected_model,
                        "duration_ms": round((time.monotonic() - started) * 1000),
                        "completed_at": completed_at,
                        "usage": usage,
                        "analysis_process": complete_process,
                        "suggestions": [
                            "只看上海" if plan.filters else "只看华东区",
                            "换成按区域展示"
                            if "month" in plan.dimensions
                            else "换成按月展示",
                            "查看同一范围的毛利率"
                            if plan.comparison != "none"
                            else "与去年同期相比",
                        ]
                        if user_preferences["suggestions_enabled"]
                        else [],
                    }
                )
            persist()
            yield event(
                "result",
                message={
                    "id": mid,
                    "role": "assistant",
                    "content": content,
                    "result": result,
                },
            )
        except asyncio.CancelledError:
            status = "cancelled"
            content = "本次生成已停止。"
            error_code = "CANCELLED"
            persist()
            raise
        except (ModelError, ValueError) as exc:
            content = str(exc)
            error_code = exc.code if isinstance(exc, ModelError) else "QUERY_VALIDATION"
            persist()
            yield event(
                "result",
                message={
                    "id": mid,
                    "role": "assistant",
                    "content": content,
                    "result": {"status": "error", "error_code": error_code},
                },
            )
        except Exception as exc:
            log.error("query_failed type=%s message_id=%s", type(exc).__name__, mid)
            content = "本次查询未完成，请重试。若反复出现，请查看后端执行记录。"
            error_code = "QUERY_FAILED"
            persist()
            yield event(
                "result",
                message={
                    "id": mid,
                    "role": "assistant",
                    "content": content,
                    "result": {"status": "error", "error_code": error_code},
                },
            )
        finally:
            lock.execute(
                text("SELECT pg_advisory_unlock(7721, :uid)"), {"uid": user["id"]}
            )
            lock.close()

    return StreamingResponse(
        stream(), media_type="application/x-ndjson", headers={"X-Accel-Buffering": "no"}
    )


@app.get("/api/messages/{mid}/export")
def export(mid: str, user: User):
    with engine.connect() as conn:
        msg = (
            conn.execute(
                select(s.messages)
                .join(s.conversations)
                .where(s.messages.c.id == mid, s.conversations.c.user_id == user["id"])
            )
            .mappings()
            .first()
        )
    if not msg or not msg["result"] or msg["result"].get("status") != "success":
        raise HTTPException(404, "没有可导出的结果")
    out = io.StringIO()
    out.write("\ufeff")
    writer = csv.writer(out)
    result = msg["result"]
    writer.writerow(
        [
            "分组",
            result["metric"]["name"] + "（" + result["metric"]["unit"] + "）",
            "对比值",
            "变化率（%）",
            "差额/百分点",
        ]
    )
    for r in result["rows"]:
        label = r["label"]
        label = (
            "'" + label if label.startswith(("=", "+", "-", "@", "\t", "\r")) else label
        )
        writer.writerow(
            [label, r["value"], r["previous"], r["change"], r["difference"]]
        )
    return Response(
        out.getvalue(),
        media_type="text/csv;charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="query-result.csv"'},
    )
