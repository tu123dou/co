"""catalog HTTP 接口。"""

import time

from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from ..catalog import TABLE_CATALOG
from ..db import engine
from ..llm import ModelError, call_model, configured
from ..repositories.catalog import dataset_info, get_catalog
from ..repositories.workbench import get_workbench_settings, list_models
from ..repositories.models import selected_connection
from ..semantic import DIMENSIONS, METRICS
from ..user_settings import (
    ALLOWED_LLM_MODELS,
)
from .dependencies import User
from .schemas import ModelTest

router = APIRouter()


@router.get("/api/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


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


@router.get("/api/catalog")
def catalog(user: User):
    d = dataset_info()
    user_settings = get_workbench_settings(user["id"])
    return {
        "metrics": METRICS,
        "dimensions": DIMENSIONS,
        "values": get_catalog(),
        "dataset": d,
        "data_tables": dataset_table_rows(d["counts"]),
        "model": {
            "name": user_settings["llm_model"],
            "available": ALLOWED_LLM_MODELS,
            "configured": bool(user_settings["custom_model_id"]) or configured(),
            "builtin_configured": configured(),
            "custom": list_models(user["id"]),
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


@router.post("/api/model/test")
async def test_model(body: ModelTest, user: User):
    model, connection = await run_in_threadpool(
        selected_connection, user["id"], body.model, body.custom_model_id,
    )
    try:
        start = time.monotonic()
        await call_model(
            [{"role": "user", "content": "请只回复 OK"}],
            model=model,
            max_tokens=16,
            **({"connection": connection} if connection else {}),
        )
        return {
            "ok": True,
            "model": model,
            "duration_ms": round((time.monotonic() - start) * 1000),
        }
    except ModelError as exc:
        raise HTTPException(502, str(exc))
