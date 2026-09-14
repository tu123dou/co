"""锁操作失败时不能将仍可能持锁的物理连接返回连接池。"""

from types import SimpleNamespace

import pytest
from app.errors import QueryBusy
from app.repositories import query_lock


class Connection:
    def __init__(self, locked=True):
        self.locked = locked
        self.closed = False
        self.invalidated = False

    def scalar(self, *args):
        return self.locked

    def execute(self, *args):
        raise RuntimeError("connection lost during unlock")

    def commit(self):
        pass

    def invalidate(self):
        self.invalidated = True

    def close(self):
        self.closed = True


def test_unlock_failure_invalidates_and_closes(monkeypatch):
    conn = Connection()
    monkeypatch.setattr(
        query_lock, "lock_engine", SimpleNamespace(connect=lambda: conn)
    )
    lock = query_lock.UserQueryLock(1)
    lock.acquire()
    with pytest.raises(RuntimeError):
        lock.release()
    assert conn.invalidated and conn.closed
    lock.release()  # repeated cleanup is safe


def test_busy_user_does_not_leak_connection(monkeypatch):
    conn = Connection(False)
    monkeypatch.setattr(
        query_lock, "lock_engine", SimpleNamespace(connect=lambda: conn)
    )
    with pytest.raises(QueryBusy):
        query_lock.UserQueryLock(1).acquire()
    assert conn.closed
