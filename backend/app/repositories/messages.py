"""按当前用户归属读取可导出的历史结果。"""

from sqlalchemy import select

from .. import schema as s
from ..db import engine
from ..errors import ResourceNotFound


def exportable_result(mid: str, uid: int):
    with engine.connect() as conn:
        msg = (
            conn.execute(
                select(s.messages)
                .join(s.conversations)
                .where(s.messages.c.id == mid, s.conversations.c.user_id == uid)
            )
            .mappings()
            .first()
        )
    if not msg or not msg["result"] or msg["result"].get("status") != "success":
        raise ResourceNotFound("没有可导出的结果")
    return msg["result"]
