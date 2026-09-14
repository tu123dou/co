"""认证使用的账号查询。"""

from sqlalchemy import select

from .. import schema as s
from ..db import engine


def active_user_by_name(username: str):
    with engine.connect() as conn:
        user = (
            conn.execute(
                select(s.users).where(
                    s.users.c.username == username, s.users.c.active.is_(True)
                )
            )
            .mappings()
            .first()
        )
    return user
