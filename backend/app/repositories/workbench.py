from sqlalchemy import delete, func, select, update

from .. import schema as s
from ..db import engine
from ..errors import ResourceNotFound
from ..user_settings import ensure_user_settings
from .models import find_model, public_models


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
            "custom_model_id",
            "updated_at",
        ]
    }


def get_workbench_settings(uid: int):
    with engine.begin() as conn:
        return public_workbench_settings(ensure_user_settings(conn, uid))


def edit_workbench_settings(values: dict, uid: int):
    with engine.begin() as conn:
        ensure_user_settings(conn, uid)
        preferences = conn.execute(select(s.user_workbench_settings).where(
            s.user_workbench_settings.c.user_id == uid
        ).with_for_update()).mappings().one()
        if values.get("custom_model_id"):
            model = find_model(preferences, values["custom_model_id"])
            values = {**values, "llm_model": model["model_name"]}
        elif "llm_model" in values:
            values = {**values, "custom_model_id": None}
        if values:
            conn.execute(
                update(s.user_workbench_settings)
                .where(s.user_workbench_settings.c.user_id == uid)
                .values(**values, updated_at=func.now())
            )
        row = ensure_user_settings(conn, uid)
    return public_workbench_settings(row)


def list_models(uid: int):
    with engine.begin() as conn:
        return public_models(ensure_user_settings(conn, uid))


def common_questions(uid: int):
    with engine.begin() as conn:
        prefs = ensure_user_settings(conn, uid)
        if not prefs["common_questions_enabled"]:
            return []
        return [
            dict(row)
            for row in conn.execute(
                select(
                    s.user_question_stats.c.id,
                    s.user_question_stats.c.question,
                    s.user_question_stats.c.success_count,
                    s.user_question_stats.c.last_asked_at,
                )
                .where(
                    s.user_question_stats.c.user_id == uid,
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


def delete_common_question(question_id: int, uid: int):
    """删除当前用户的问题频次记录，使其从常见问题中消失。"""
    with engine.begin() as conn:
        result = conn.execute(
            delete(s.user_question_stats).where(
                s.user_question_stats.c.id == question_id,
                s.user_question_stats.c.user_id == uid,
            )
        )
    if result.rowcount == 0:
        raise ResourceNotFound("常见问题不存在")
    return {"ok": True}


def favorites(uid: int):
    with engine.connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                select(s.favorite_questions)
                .where(s.favorite_questions.c.user_id == uid)
                .order_by(s.favorite_questions.c.created_at.desc())
            ).mappings()
        ]


def add_favorite(question: str, uid: int):
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    with engine.begin() as conn:
        conn.execute(
            pg_insert(s.favorite_questions)
            .values(user_id=uid, question=question)
            .on_conflict_do_nothing()
        )
    return {"ok": True}


def delete_favorite(fid: int, uid: int):
    with engine.begin() as conn:
        conn.execute(
            delete(s.favorite_questions).where(
                s.favorite_questions.c.id == fid,
                s.favorite_questions.c.user_id == uid,
            )
        )
    return {"ok": True}
