from datetime import datetime, timezone

from sqlalchemy import select, text, update

from .. import schema as s
from ..db import engine
from ..errors import Forbidden, InvalidRequest, ResourceNotFound


def feedback(message_id: str, comment: str, uid: int):
    with engine.begin() as conn:
        msg = conn.execute(
            select(s.messages)
            .join(s.conversations)
            .where(
                s.messages.c.id == message_id,
                s.conversations.c.user_id == uid,
                s.messages.c.role == "assistant",
            )
        ).first()
        if not msg:
            raise ResourceNotFound("回答不存在")
        conn.execute(
            s.feedbacks.insert().values(
                user_id=uid, message_id=message_id, comment=comment
            )
        )
    return {"ok": True}


def list_feedbacks(
    uid: int,
    is_superuser: bool,
    question: str,
    username: str,
    status: str,
    page: int,
    page_size: int,
):
    """分页查询回复校对列表，并找到每条助手回答之前最近的用户问题。"""
    if status and status not in {"pending", "resolved"}:
        raise InvalidRequest("不支持的反馈状态")
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    params = {
        "question": f"%{question.strip()}%",
        "username": f"%{username.strip()}%",
        "status": status,
        "limit": page_size,
        "offset": (page - 1) * page_size,
        "user_id": uid,
        "is_superuser": is_superuser,
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
            -- 普通用户只能看到自己的反馈；超管可以集中校对全部用户反馈。
            WHERE :is_superuser OR f.user_id = :user_id
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


def review_feedback(
    feedback_id: int,
    status: str,
    resolution_note: str | None,
    uid: int,
    is_superuser: bool,
):
    """仅允许超管保存跨用户回复核查状态和处理说明。"""
    if not is_superuser:
        raise Forbidden("仅超管可以处理反馈")
    with engine.begin() as conn:
        row = conn.execute(
            update(s.feedbacks)
            .where(s.feedbacks.c.id == feedback_id)
            .values(
                status=status,
                resolution_note=(resolution_note or "").strip() or None,
                updated_at=datetime.now(timezone.utc),
            )
            .returning(s.feedbacks.c.id)
        ).first()
        if not row:
            raise ResourceNotFound("反馈不存在")
    return {"ok": True}
