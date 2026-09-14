"""召回 SQL 不得阻塞处理模型网络请求的事件循环。"""

import asyncio
from threading import get_ident

from app import retrieval


def test_retrieval_database_work_runs_off_event_loop(monkeypatch):
    event_loop_thread = get_ident()

    async def embed(texts):
        assert get_ident() == event_loop_thread
        assert texts == ["问题"]
        return [[0.0]]

    def search(question, version, vector, started):
        assert get_ident() != event_loop_thread
        assert (question, version, vector) == ("问题", "test", [0.0])
        return {"context": [], "audit": None}

    monkeypatch.setattr(retrieval, "embed_texts", embed)
    monkeypatch.setattr(retrieval, "_retrieve", search)
    assert asyncio.run(retrieval.retrieve("问题", "test")) == {
        "context": [],
        "audit": None,
    }
