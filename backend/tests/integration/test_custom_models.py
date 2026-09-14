import json
import os
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy import text

from app import schema as s
from app.config import settings
from app.db import engine
from app.api import workbench as workbench_api, catalog as catalog_api
from app.services import ask as ask_service
from app.semantic import Interpretation

pytestmark = pytest.mark.skipif(os.getenv("TEST_DATABASE") != "1", reason="Local database only")


@pytest.mark.parametrize("api_format", ["openai", "anthropic"])
def test_custom_model_lifecycle_and_isolation(clients, monkeypatch, api_format):
    a, b = clients
    monkeypatch.setattr(settings(), "model_encryption_secret", "test-only-secret-" * 3)
    body = {"request_url": "https://model.example/exact-endpoint", "api_key": "test-only-api-key", "model_name": "custom-test", "api_format": api_format}
    calls = []

    async def fake_model(*args, **kwargs):
        calls.append(kwargs)
        return "OK", {}

    monkeypatch.setattr(workbench_api, "call_model", fake_model)
    monkeypatch.setattr(catalog_api, "call_model", fake_model)
    assert a.post("/api/models/test", json=body).status_code == 200
    assert a.get("/api/catalog").json()["model"]["custom"] == []
    added = a.post("/api/models", json=body)
    assert added.status_code == 201
    assert set(added.json()) == {"id", "request_url", "model_name", "api_format", "display_name", "full_url"}
    assert added.json()["display_name"] == body["model_name"]
    assert added.json()["api_format"] == api_format
    mid = added.json()["id"]
    assert a.post("/api/models", json=body).status_code == 422
    assert a.get("/api/workbench/settings").json()["custom_model_id"] is None
    assert b.get("/api/catalog").json()["model"]["custom"] == []
    assert b.patch("/api/workbench/settings", json={"custom_model_id": mid}).status_code == 404
    assert b.post("/api/model/test", json={"custom_model_id": mid}).status_code == 404

    updated = a.patch("/api/workbench/settings", json={"custom_model_id": mid})
    assert updated.status_code == 200
    assert updated.json()["llm_model"] == "custom-test"
    assert updated.json()["custom_model_id"] == mid
    for response in [updated, a.get("/api/catalog"), a.get("/api/workbench/settings")]:
        assert "test-only-api-key" not in response.text
        assert "encrypted_key" not in response.text
    with engine.connect() as conn:
        rows = conn.execute(select(s.user_workbench_settings.c.custom_models)).scalars()
        stored = next(m for models in rows for m in models if m["id"] == mid)
        assert "api_key" not in stored
        assert stored["encrypted_key"] != body["api_key"]

    assert a.post("/api/model/test", json={"custom_model_id": mid}).status_code == 200
    assert calls[-1]["model"] == "custom-test"
    assert calls[-1]["connection"].api_key == body["api_key"]

    async def fake_interpret(*args, **kwargs):
        assert kwargs["model"] == "custom-test"
        assert kwargs["connection"].request_url == body["request_url"]
        assert kwargs["connection"].api_format == api_format
        assert kwargs["connection"].api_key == body["api_key"]
        return Interpretation(action="unsupported", explanation="隔离模型验证"), {}

    monkeypatch.setattr(ask_service, "interpret", fake_interpret)
    cid = a.post("/api/conversations").json()["id"]
    response = a.post(f"/api/conversations/{cid}/ask", json={"question": "验证自定义模型路由"})
    result = [json.loads(line) for line in response.text.splitlines()][-1]
    assert result["message"]["result"]["status"] == "unsupported"
    assert "test-only-api-key" not in a.get(f"/api/conversations/{cid}").text
    reverted = a.patch("/api/workbench/settings", json={"llm_model": "qwen3.8-max"})
    assert reverted.json()["custom_model_id"] is None
    assert a.post("/api/model/test", json={"model": "qwen3.8-max"}).status_code == 200
    assert "connection" not in calls[-1]
    internal = a.post("/api/models/test", json={**body, "request_url": "https://127.0.0.1/v1"})
    assert internal.status_code == 200
    assert calls[-1]["connection"].request_url == "https://127.0.0.1/v1"


def test_model_edit_delete_and_url_modes(clients, monkeypatch):
    a, b = clients
    monkeypatch.setattr(settings(), "model_encryption_secret", "test-only-secret-" * 3)
    calls = []

    async def fake_model(*args, **kwargs):
        calls.append(kwargs)
        return "OK", {}

    monkeypatch.setattr(workbench_api, "call_model", fake_model)
    monkeypatch.setattr(catalog_api, "call_model", fake_model)
    body = {"request_url": "https://model.example/compatible-mode/v1/", "full_url": False,
            "api_key": "test-only-key", "model_name": "国产模型", "api_format": "openai", "display_name": "测试模型"}
    assert a.post("/api/models/test", json=body).status_code == 200
    endpoint = "https://model.example/compatible-mode/v1/chat/completions"
    assert calls[-1]["connection"].request_url == endpoint
    added = a.post("/api/models", json=body)
    assert added.status_code == 201
    mid = added.json()["id"]
    assert added.json()["full_url"] is False
    assert a.post("/api/models", json={**body, "request_url": endpoint, "full_url": True}).status_code == 422
    assert a.patch("/api/workbench/settings", json={"custom_model_id": mid}).status_code == 200
    cid = a.post("/api/conversations").json()["id"]
    edit = {key: value for key, value in body.items() if key != "api_key"}
    edit.update(model_name="新模型", display_name="新展示名称")
    for method, path in [(b.patch, f"/api/models/{mid}"), (b.post, f"/api/models/{mid}/test")]:
        assert method(path, json=edit).status_code == 404
    assert b.delete(f"/api/models/{mid}").status_code == 404
    assert a.post(f"/api/models/{mid}/test", json=edit).status_code == 200
    assert calls[-1]["connection"].api_key == body["api_key"]
    assert a.get("/api/catalog").json()["model"]["custom"][0]["model_name"] == body["model_name"]
    edited = a.patch(f"/api/models/{mid}", json=edit)
    assert edited.status_code == 200
    assert edited.json()["id"] == mid
    assert a.get("/api/workbench/settings").json()["llm_model"] == "新模型"
    assert a.post("/api/model/test", json={"custom_model_id": mid}).status_code == 200
    assert calls[-1]["connection"].api_key == body["api_key"]
    assert calls[-1]["connection"].request_url == endpoint
    rotate = {**edit, "api_key": "new-test-only-key"}
    assert a.patch(f"/api/models/{mid}", json=rotate).status_code == 200
    assert a.post("/api/model/test", json={"custom_model_id": mid}).status_code == 200
    assert calls[-1]["connection"].api_key == rotate["api_key"]
    second = a.post("/api/models", json={**body, "model_name": "other"}).json()["id"]
    assert a.patch(f"/api/models/{second}", json=edit).status_code == 422
    assert a.delete(f"/api/models/{second}").json()["custom_model_id"] == mid
    deleted = a.delete(f"/api/models/{mid}")
    assert deleted.status_code == 200
    assert deleted.json()["custom_model_id"] is None
    assert a.get("/api/catalog").json()["model"]["custom"] == []
    assert a.get(f"/api/conversations/{cid}").status_code == 200
    assert a.delete(f"/api/models/{mid}").status_code == 404
    assert a.post("/api/model/test", json={"custom_model_id": mid}).status_code == 404


def test_protocol_migration_preserves_existing_models():
    """用事务临时表验证迁移 SQL，不改动任何现有账号配置。"""
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0014_model_protocols.py"
    spec = importlib.util.spec_from_file_location("model_protocol_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old_model = {"id": "old-id", "base_url": "https://model.example/v1/", "model_name": "国产模型", "encrypted_key": "unchanged-ciphertext"}
    with engine.begin() as conn:
        conn.execute(text("CREATE TEMPORARY TABLE model_migration_check (custom_models jsonb NOT NULL) ON COMMIT DROP"))
        conn.execute(text("INSERT INTO model_migration_check VALUES (CAST(:models AS jsonb)), ('[]'::jsonb)"), {"models": json.dumps([old_model])})
        module.op = SimpleNamespace(execute=lambda sql: conn.execute(text(sql.replace(
            "app.user_workbench_settings", "model_migration_check",
        ))))
        module.upgrade()
        rows = conn.execute(text("SELECT custom_models FROM model_migration_check")).scalars().all()
        migrated = next(row[0] for row in rows if row)
        assert [] in rows
        assert migrated == {"id": "old-id", "request_url": "https://model.example/v1/chat/completions", "model_name": "国产模型", "display_name": "国产模型", "api_format": "openai", "encrypted_key": "unchanged-ciphertext"}
        module.upgrade()
        assert conn.scalar(text("SELECT custom_models FROM model_migration_check WHERE jsonb_array_length(custom_models)>0")) == [migrated]
