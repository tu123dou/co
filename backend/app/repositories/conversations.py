"""会话所有权校验，供接口与问数服务共用。"""

import uuid

from sqlalchemy import delete, select, update

from .. import schema as s
from ..db import engine
from ..errors import ResourceNotFound


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
        raise ResourceNotFound("会话不存在")
    return dict(row)


def conversations(uid: int):
    with engine.connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                select(s.conversations)
                .where(s.conversations.c.user_id == uid)
                .order_by(
                    s.conversations.c.pinned.desc(), s.conversations.c.updated_at.desc()
                )
            ).mappings()
        ]


def new_conversation(uid: int):
    cid = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            s.conversations.insert().values(id=cid, user_id=uid, title="新对话")
        )
    return {"id": cid}


def conversation(cid: str, uid: int):
    with engine.connect() as conn:
        convo = owned(cid, uid, conn)
        convo["messages"] = [
            dict(r)
            for r in conn.execute(
                select(s.messages)
                .where(s.messages.c.conversation_id == cid)
                .order_by(s.messages.c.created_at, s.messages.c.id)
            ).mappings()
        ]
    return convo


def edit_conversation(cid: str, values: dict, uid: int):
    with engine.begin() as conn:
        owned(cid, uid, conn)
        if values:
            conn.execute(
                update(s.conversations)
                .where(s.conversations.c.id == cid)
                .values(**values)
            )
    return {"ok": True}


def remove_conversation(cid: str, uid: int):
    with engine.begin() as conn:
        owned(cid, uid, conn)
        conn.execute(delete(s.conversations).where(s.conversations.c.id == cid))
    return {"ok": True}
