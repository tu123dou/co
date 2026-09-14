"""公开注册仅创建隔离的普通账号，并安全处理凭据校验错误。"""

import os
import uuid

import pytest
from app import schema as s
from app.api import auth as auth_api
from app.config import settings
from app.db import engine
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_DATABASE") != "1", reason="Local database only"
)


def test_register_login_and_duplicate(monkeypatch):
    monkeypatch.setattr(settings(), "registration_enabled", True)
    auth_api.registration_attempts.clear()
    auth_api.login_attempts.clear()
    username = "register_" + uuid.uuid4().hex[:12]
    password = "RegisterOnly9423"
    client = TestClient(app)
    user_id = None
    try:
        registered = client.post(
            "/api/auth/register",
            json={
                "username": username,
                "display_name": "注册用户",
                "password": password,
            },
        )
        assert registered.status_code == 201
        user_id = registered.json()["id"]
        assert registered.json() == {
            "id": user_id,
            "display_name": "注册用户",
            "is_superuser": False,
        }
        assert "session=" in registered.headers["set-cookie"]
        assert client.get("/api/auth/me").json() == registered.json()
        with engine.connect() as connection:
            stored = (
                connection.execute(select(s.users).where(s.users.c.id == user_id))
                .mappings()
                .one()
            )
        assert stored["username"] == username
        assert stored["password_hash"] != password
        assert stored["active"] is True
        assert stored["is_superuser"] is False

        duplicate = TestClient(app).post(
            "/api/auth/register",
            json={
                "username": username,
                "display_name": "另一个用户",
                "password": password,
            },
        )
        assert duplicate.status_code == 422
        assert duplicate.json()["detail"] == "用户名已存在"

        assert client.post("/api/auth/logout").status_code == 200
        assert client.get("/api/auth/me").status_code == 401
        assert (
            client.post(
                "/api/auth/login", json={"username": username, "password": password}
            ).status_code
            == 200
        )

        invalid_password = "password-without-number"
        invalid = TestClient(app).post(
            "/api/auth/register",
            json={
                "username": "bad user",
                "display_name": "无效用户",
                "password": invalid_password,
            },
        )
        assert invalid.status_code == 422
        assert invalid.json()["detail"] == "账号信息格式不正确，请检查必填项及长度"
        assert invalid_password not in invalid.text
    finally:
        client.close()
        if user_id is not None:
            with engine.begin() as connection:
                connection.execute(
                    delete(s.user_workbench_settings).where(
                        s.user_workbench_settings.c.user_id == user_id
                    )
                )
                connection.execute(delete(s.users).where(s.users.c.id == user_id))


def test_registration_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings(), "registration_enabled", False)
    auth_api.registration_attempts.clear()
    response = TestClient(app).post(
        "/api/auth/register",
        json={
            "username": "disabled_registration",
            "display_name": "禁用注册验证",
            "password": "Disabled9423",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "当前未开放注册"
