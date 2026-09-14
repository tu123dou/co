"""用户级 PostgreSQL 会话锁；锁连接与应用事务使用独立连接池。"""

from sqlalchemy import text
from sqlalchemy.engine import Connection

from ..db import lock_engine
from ..errors import QueryBusy


class UserQueryLock:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.connection: Connection | None = None

    def acquire(self) -> None:
        conn = lock_engine.connect()
        try:
            locked = conn.scalar(
                text("SELECT pg_try_advisory_lock(7721, :uid)"), {"uid": self.user_id}
            )
            # 会话锁不依赖事务，避免等待模型期间保持 idle in transaction。
            conn.commit()
            if not locked:
                raise QueryBusy("上一条问题仍在处理中，请完成或停止后再试")
        except BaseException:
            # 获取结果不确定时销毁物理连接，不能把潜在持锁连接放回连接池。
            conn.invalidate()
            conn.close()
            raise
        self.connection = conn

    def release(self) -> None:
        conn, self.connection = self.connection, None
        if conn is None:
            return
        try:
            conn.execute(
                text("SELECT pg_advisory_unlock(7721, :uid)"), {"uid": self.user_id}
            )
            conn.commit()
        except BaseException:
            conn.invalidate()
            raise
        finally:
            conn.close()
