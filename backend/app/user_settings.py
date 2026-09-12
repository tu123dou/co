"""用户工作台设置与常见问题统计。

配置以 user_id 为边界，每名用户只能读取和修改自己的设置。主模型名称来自固定白名单；
模型密钥、服务地址和向量模型仍由后端环境变量统一管理。
"""

import re
import unicodedata
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from . import schema as s


ALLOWED_LLM_MODELS = [
    "qwen3.8-max",
    "qwen3.8-flash",
    "qwen3.7-plus",
    "deepseek-v4-flash",
    "glm-5.2",
    "MiniMax-M2.5",
]
DEFAULT_STARTER_QUESTIONS = [
    "今年各经营单元确认收入排名",
    "今年各产品线的收入占比",
    "华东区今年按月收入趋势，与去年同期相比",
    "2026年8月各产品线毛利率",
    "今年各区域收入目标达成率",
    "2026年8月回款额比上个月变化多少",
]
DEFAULT_USER_SETTINGS = {
    "welcome_enabled": True,
    "welcome_title": "你好，今天想了解哪些数据？",
    "welcome_message": "从收入趋势到目标达成，用自然语言探索你的经营数据。",
    "starter_questions": DEFAULT_STARTER_QUESTIONS,
    "suggestions_enabled": True,
    "common_questions_enabled": True,
    "common_question_threshold": 3,
    "llm_model": "qwen3.8-max",
}


def ensure_user_settings(conn, user_id):
    """确保用户拥有默认设置，并返回当前数据库记录。"""
    conn.execute(
        pg_insert(s.user_workbench_settings)
        .values(user_id=user_id, **DEFAULT_USER_SETTINGS)
        .on_conflict_do_nothing(index_elements=[s.user_workbench_settings.c.user_id])
    )
    return dict(
        conn.execute(
            select(s.user_workbench_settings).where(
                s.user_workbench_settings.c.user_id == user_id
            )
        )
        .mappings()
        .one()
    )


def normalize_question(question):
    """做可解释的文本归并，不用语义相似度合并不同业务问题。"""
    value = unicodedata.normalize("NFKC", question).strip()
    value = re.sub(r"\s+", " ", value)
    return value.rstrip("。！？!?；;，, ").casefold()


def record_successful_question(conn, user_id, question):
    """成功问数后原子递增当前用户的问题频次。"""
    normalized = normalize_question(question)
    if not normalized:
        return
    stmt = pg_insert(s.user_question_stats).values(
        user_id=user_id,
        normalized_question=normalized,
        question=question.strip(),
        success_count=1,
        last_asked_at=func.now(),
    )
    conn.execute(
        stmt.on_conflict_do_update(
            index_elements=[
                s.user_question_stats.c.user_id,
                s.user_question_stats.c.normalized_question,
            ],
            set_={
                "question": stmt.excluded.question,
                "success_count": s.user_question_stats.c.success_count + 1,
                "last_asked_at": func.now(),
            },
        )
    )
