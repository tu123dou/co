"""仅创建隔离账号；先注册清理，确保 setup 失败也不遗留记录。"""

import uuid
from collections import defaultdict, deque

import pytest
from app import schema as s
from app.api import auth as auth_api
from app.api import catalog as catalog_api
from app.auth import hash_password
from app.db import engine
from app.main import app
from app.semantic import Interpretation, Plan
from app.services import ask as ask_service
from fastapi.testclient import TestClient
from sqlalchemy import delete, insert


@pytest.fixture
def clients(monkeypatch, request):
    monkeypatch.setattr(auth_api, "login_attempts", defaultdict(deque))

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

    monkeypatch.setattr(ask_service, "interpret", fake_interpret)

    async def fake_retrieve(*args, **kwargs):
        return {"context": [], "audit": None}

    monkeypatch.setattr(ask_service, "retrieve", fake_retrieve)

    async def fake_call_model(*args, **kwargs):
        return "OK", {"total_tokens": 1}

    monkeypatch.setattr(catalog_api, "call_model", fake_call_model)
    names = ["test_" + uuid.uuid4().hex[:12] for _ in range(2)]
    ids = []
    cs = []

    def cleanup():
        for client in cs:
            client.close()
        with engine.begin() as conn:
            conn.execute(
                delete(s.conversations).where(s.conversations.c.user_id.in_(ids))
            )
            conn.execute(
                delete(s.favorite_questions).where(
                    s.favorite_questions.c.user_id.in_(ids)
                )
            )
            conn.execute(
                delete(s.user_question_stats).where(
                    s.user_question_stats.c.user_id.in_(ids)
                )
            )
            conn.execute(
                delete(s.user_workbench_settings).where(
                    s.user_workbench_settings.c.user_id.in_(ids)
                )
            )
            conn.execute(delete(s.users).where(s.users.c.id.in_(ids)))

    request.addfinalizer(cleanup)
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
