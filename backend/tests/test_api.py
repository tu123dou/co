"""API 测试：验证认证、对话、问数流式响应和错误处理。"""

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
    async def fake_retrieve(*args, **kwargs):
        return {"context": [], "audit": None}

    monkeypatch.setattr(main, "retrieve", fake_retrieve)
    async def fake_call_model(*args, **kwargs):
        return "OK", {"total_tokens": 1}

    monkeypatch.setattr(main, "call_model", fake_call_model)
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
        conn.execute(
            delete(s.user_question_stats).where(s.user_question_stats.c.user_id.in_(ids))
        )
        conn.execute(
            delete(s.user_workbench_settings).where(
                s.user_workbench_settings.c.user_id.in_(ids)
            )
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
    analysis_events = [event["step"] for event in events if event["type"] == "analysis"]
    assert analysis_events[0]["key"] == "source"
    assert analysis_events[0]["status"] == "running"
    final_steps = {step["key"]: step for step in analysis_events}
    assert list(final_steps) == ["source", "plan", "sql", "result", "done"]
    assert all(step["status"] == "complete" for step in final_steps.values())
    assert events[-1]["type"] == "result"
    answer = events[-1]["message"]
    assert answer["result"]["status"] == "success"
    assert answer["result"]["completed_at"].endswith("+00:00")
    assert len(answer["result"]["rows"]) == 5
    process = answer["result"]["analysis_process"]
    assert [step["key"] for step in process] == ["source", "plan", "sql", "result", "done"]
    assert "analytics.revenue_entries" in str(process[0])
    sql_step = process[2]["executions"][0]
    assert "WITH facts AS" in sql_step["executable_sql"]
    assert ":start_date" not in sql_step["executable_sql"]
    assert "收入确认流水" in sql_step["business_sql"]
    saved = a.get("/api/conversations/" + cid).json()
    assert len(saved["messages"]) == 2
    assert saved["context"]["metric"] == "revenue"
    mid = answer["id"]
    assert b.get("/api/messages/" + mid + "/export").status_code == 404
    export = a.get("/api/messages/" + mid + "/export")
    assert export.status_code == 200 and "通用计算" in export.text
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
    feedback_id = a.get("/api/feedbacks").json()["items"][0]["id"]
    assert b.get("/api/feedbacks").json()["items"] == []
    assert (
        a.patch(
            "/api/feedbacks/" + str(feedback_id),
            json={"status": "resolved", "resolution_note": "已核查"},
        ).status_code
        == 403
    )
    # 超管可以查看跨用户反馈并保存校对结论。
    with engine.begin() as conn:
        conn.execute(
            s.users.update()
            .where(s.users.c.id == b.get("/api/auth/me").json()["id"])
            .values(is_superuser=True)
        )
    assert feedback_id in {
        row["id"] for row in b.get("/api/feedbacks").json()["items"]
    }
    assert (
        b.patch(
            "/api/feedbacks/" + str(feedback_id),
            json={"status": "resolved", "resolution_note": "已核查"},
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


def test_workbench_settings_are_user_scoped(clients):
    a, b = clients
    default_a = a.get("/api/workbench/settings").json()
    default_b = b.get("/api/workbench/settings").json()
    assert default_a["common_question_threshold"] == 3
    assert default_a["llm_model"] == "qwen3.8-max"
    updated = a.patch(
        "/api/workbench/settings",
        json={
            "welcome_title": "我的经营助手",
            "common_question_threshold": 1,
            "llm_model": "qwen3.8-flash",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["welcome_title"] == "我的经营助手"
    assert updated.json()["llm_model"] == "qwen3.8-flash"
    assert b.get("/api/workbench/settings").json()["welcome_title"] == default_b["welcome_title"]
    assert b.get("/api/workbench/settings").json()["llm_model"] == "qwen3.8-max"
    assert (
        a.patch("/api/workbench/settings", json={"llm_model": "unknown-model"}).status_code
        == 422
    )
    tested = a.post("/api/model/test", json={"model": "glm-5.2"})
    assert tested.status_code == 200
    assert tested.json()["model"] == "glm-5.2"


def test_common_questions_count_only_current_users_successes(clients):
    a, b = clients
    a.patch("/api/workbench/settings", json={"common_question_threshold": 1})
    cid = a.post("/api/conversations").json()["id"]
    response = a.post(
        "/api/conversations/" + cid + "/ask",
        json={"question": "今年各产品线收入占比？"},
    )
    assert response.status_code == 200
    common = a.get("/api/common-questions").json()
    assert common[0]["question"] == "今年各产品线收入占比？"
    assert common[0]["success_count"] == 1
    assert b.get("/api/common-questions").json() == []
    a.patch("/api/workbench/settings", json={"common_questions_enabled": False})
    assert a.get("/api/common-questions").json() == []


def test_origin_and_catalog_do_not_expose_model_credentials(clients):
    a, b = clients
    assert (
        a.post(
            "/api/conversations", headers={"origin": "https://untrusted.example"}
        ).status_code
        == 403
    )
    assert a.post("/api/model/test", json={}).status_code == 200
    assert b.post("/api/model/test", json={}).status_code == 200
    c = a.get("/api/catalog").json()
    assert "api_key" not in str(c).lower()
    assert c["model"]["available"] == [
        "qwen3.8-max",
        "qwen3.8-flash",
        "qwen3.7-plus",
        "deepseek-v4-flash",
        "glm-5.2",
        "MiniMax-M2.5",
    ]
