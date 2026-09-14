"""真实本地 PostgreSQL 与 HTTP 流验证；外部模型在明确边界替换，不消耗额度。"""

import asyncio
import json
import os
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from app import schema as s
from app.db import engine, lock_engine
from app.llm import ModelError
from app.main import create_app
from app.repositories.query_lock import UserQueryLock
from app.semantic import Interpretation
from app.services import ask
from sqlalchemy import select

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_DATABASE") != "1",
    reason="Requires confirmed local integration database",
)


@pytest.fixture
def live_api():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(
        uvicorn.Config(create_app(), log_level="error", lifespan="off")
    )
    thread = threading.Thread(
        target=server.run, kwargs={"sockets": [sock]}, daemon=True
    )
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        yield f"http://127.0.0.1:{sock.getsockname()[1]}"
    finally:
        server.should_exit = True
        thread.join(5)
        sock.close()
        assert not thread.is_alive()


def audit_for(mid):
    with engine.connect() as conn:
        return dict(
            conn.execute(select(s.query_runs).where(s.query_runs.c.message_id == mid))
            .mappings()
            .one()
        )


@pytest.mark.parametrize(
    "outcome", ["clarify", "unsupported", "model_error", "system_error"]
)
def test_terminal_outcomes_match_history_and_audit(clients, monkeypatch, outcome):
    a, _ = clients
    cid = a.post("/api/conversations").json()["id"]

    async def interpret(*args, **kwargs):
        if outcome == "model_error":
            raise ModelError("MODEL_TIMEOUT", "模型响应超时")
        if outcome == "system_error":
            raise RuntimeError("private-server-details")
        return Interpretation(action=outcome, explanation="请补充查询条件"), {}

    monkeypatch.setattr(ask, "interpret", interpret)
    response = a.post(
        f"/api/conversations/{cid}/ask", json={"question": "隔离测试问题"}
    )
    events = [json.loads(line) for line in response.text.splitlines()]
    assert response.status_code == 200 and events[-1]["type"] == "result"
    message = events[-1]["message"]
    history = a.get(f"/api/conversations/{cid}").json()
    saved = next(row for row in history["messages"] if row["id"] == message["id"])
    assert (
        saved["content"] == message["content"] and saved["result"] == message["result"]
    )
    assert audit_for(message["id"])["status"] == message["result"]["status"]
    assert "private-server-details" not in response.text
    assert history["context"] == {}
    uid = a.get("/api/auth/me").json()["id"]
    lock = UserQueryLock(uid)
    lock.acquire()
    lock.release()


def test_real_disconnect_cancels_model_saves_status_and_releases_lock(
    clients, live_api, monkeypatch
):
    a, b = clients
    cid = a.post("/api/conversations").json()["id"]
    uid = a.get("/api/auth/me").json()["id"]
    entered, cancelled = threading.Event(), threading.Event()
    normal_interpret = ask.interpret

    async def waiting_model(*args, **kwargs):
        entered.set()
        try:
            await asyncio.sleep(20)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(ask, "interpret", waiting_model)
    with httpx.Client(base_url=live_api, cookies=dict(a.cookies), timeout=5) as client:
        with client.stream(
            "POST", f"/api/conversations/{cid}/ask", json={"question": "断连测试"}
        ) as response:
            assert response.status_code == 200
            lines = response.iter_lines()
            assert json.loads(next(lines))["type"] == "status"
            assert entered.wait(3)
            # 同用户被锁定；其他请求仍可完成。
            blocked = client.post(
                f"/api/conversations/{cid}/ask", json={"question": "并发测试"}
            )
            assert blocked.status_code == 409
            assert (
                httpx.get(
                    live_api + "/api/auth/me", cookies=dict(b.cookies), timeout=3
                ).status_code
                == 200
            )
        assert cancelled.wait(3)

    deadline = time.monotonic() + 5
    messages = []
    while time.monotonic() < deadline:
        messages = a.get(f"/api/conversations/{cid}").json()["messages"]
        if len(messages) == 2 and lock_engine.pool.checkedout() == 0:
            break
        time.sleep(0.02)
    assert len(messages) == 2
    answer = next(message for message in messages if message["role"] == "assistant")
    assert answer["result"] == {"status": "cancelled", "error_code": "CANCELLED"}
    assert audit_for(answer["id"])["status"] == "cancelled"
    assert lock_engine.pool.checkedout() == 0
    lock = UserQueryLock(uid)
    lock.acquire()
    lock.release()
    monkeypatch.setattr(ask, "interpret", normal_interpret)
    retry = a.post(f"/api/conversations/{cid}/ask", json={"question": "重试查询"})
    assert (
        json.loads(retry.text.splitlines()[-1])["message"]["result"]["status"]
        == "success"
    )
