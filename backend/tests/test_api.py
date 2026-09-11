import os, uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, insert
from app.main import app
from app import main, schema as s
from app.auth import hash_password
from app.db import engine
from app.semantic import Interpretation, Plan

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_DATABASE") != "1",
    reason="Set TEST_DATABASE=1 for local integration checks",
)


@pytest.fixture
def clients(monkeypatch):
    async def fake_interpret(*args, **kwargs):
        return Interpretation(
            action="query",
            plan=Plan(
                metric="revenue",
                dimensions=["product_line"],
                start_date="2026-01-01",
                end_date="2026-08-31",
            ),
            explanation="按产品线查询确认收入",
        ), {"total_tokens": 0}

    monkeypatch.setattr(main, "interpret", fake_interpret)
    names = ["test_" + uuid.uuid4().hex[:12] for _ in range(2)]
    ids = []
    cs = []
    with engine.begin() as conn:
        for name in names:
            ids.append(
                conn.scalar(
                    insert(s.users)
                    .values(
                        username=name,
                        password_hash=hash_password("TestOnly!9423"),
                        display_name="自动测试",
                        role="user",
                    )
                    .returning(s.users.c.id)
                )
            )
    for name in names:
        client = TestClient(app)
        res = client.post(
            "/api/auth/login", json={"username": name, "password": "TestOnly!9423"}
        )
        assert res.status_code == 200
        cs.append(client)
    yield cs
    for client in cs:
        client.close()
    with engine.begin() as conn:
        conn.execute(delete(s.conversations).where(s.conversations.c.user_id.in_(ids)))
        conn.execute(
            delete(s.favorite_questions).where(s.favorite_questions.c.user_id.in_(ids))
        )
        conn.execute(delete(s.users).where(s.users.c.id.in_(ids)))


def test_auth_required():
    assert TestClient(app).get("/api/catalog").status_code == 401


def test_query_persistence_export_and_isolation(clients):
    a, b = clients
    cid = a.post("/api/conversations").json()["id"]
    assert b.get("/api/conversations/" + cid).status_code == 404
    assert b.patch("/api/conversations/" + cid, json={"title": "x"}).status_code == 404
    assert b.delete("/api/conversations/" + cid).status_code == 404
    response = a.post(
        "/api/conversations/" + cid + "/ask", json={"question": "今年各产品线收入"}
    )
    import json

    events = [json.loads(line) for line in response.text.splitlines()]
    answer = events[-1]["message"]
    assert answer["result"]["status"] == "success"
    assert len(answer["result"]["rows"]) == 5
    saved = a.get("/api/conversations/" + cid).json()
    assert len(saved["messages"]) == 2
    assert saved["context"]["metric"] == "revenue"
    mid = answer["id"]
    assert b.get("/api/messages/" + mid + "/export").status_code == 404
    export = a.get("/api/messages/" + mid + "/export")
    assert export.status_code == 200 and "企业管理软件" in export.text
    assert (
        b.post("/api/feedbacks", json={"message_id": mid, "comment": "x"}).status_code
        == 404
    )
    assert (
        a.post(
            "/api/feedbacks", json={"message_id": mid, "comment": "自动测试反馈"}
        ).status_code
        == 200
    )
    assert (
        a.patch(
            "/api/conversations/" + cid, json={"title": "测试重命名", "pinned": True}
        ).status_code
        == 200
    )
    assert a.get("/api/conversations/" + cid).json()["pinned"] is True
    assert a.delete("/api/conversations/" + cid).status_code == 200
    assert a.get("/api/conversations/" + cid).status_code == 404


def test_favorites_deduplicate_and_isolate(clients):
    a, b = clients
    for _ in range(2):
        assert (
            a.post("/api/favorites", json={"question": "测试收藏"}).status_code == 200
        )
    rows = a.get("/api/favorites").json()
    assert len(rows) == 1
    assert b.get("/api/favorites").json() == []
    b.delete("/api/favorites/" + str(rows[0]["id"]))
    assert len(a.get("/api/favorites").json()) == 1


def test_origin_and_model_admin_only(clients):
    a, b = clients
    assert (
        a.post(
            "/api/conversations", headers={"origin": "https://untrusted.example"}
        ).status_code
        == 403
    )
    assert a.post("/api/model/test").status_code == 403
    c = a.get("/api/catalog").json()
    assert "api_key" not in str(c).lower()
