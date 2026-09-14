"""认证使用的账号查询。"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .. import schema as s
from ..db import engine
from ..errors import InvalidRequest


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


def create_user(username: str, password_hash: str, display_name: str):
    """创建普通用户；唯一约束负责处理并发注册同名账号。"""
    try:
        with engine.begin() as conn:
            return dict(
                conn.execute(
                    s.users.insert()
                    .values(
                        username=username,
                        password_hash=password_hash,
                        display_name=display_name,
                        active=True,
                        is_superuser=False,
                    )
                    .returning(s.users)
                )
                .mappings()
                .one()
            )
    except IntegrityError:
        raise InvalidRequest("用户名已存在") from None
