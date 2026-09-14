import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import llm
from app.config import settings
from app.errors import InvalidRequest, ServiceUnavailable
from app.main import app
from app.auth import current_user
from app.model_connections import (
    ModelConnection, encrypt_key, decrypt_key, normalize_request_url,
)


@pytest.fixture
def model_config(monkeypatch):
    monkeypatch.setattr(settings(), "model_encryption_secret", "test-only-key-" * 4)


@pytest.mark.parametrize("url", [
    "http://model.example/v1", "https://user:pass@model.example/v1",
    "https://model.example/v1?q=x", "https://model.example/v1#x",
    "https://model.example:bad/v1",
])
def test_invalid_urls(url):
    with pytest.raises(InvalidRequest):
        normalize_request_url(url)


def test_full_url_without_vendor_allowlist():
    url = "https://dashscope.aliyuncs.com/apps/anthropic/v1/messages"
    assert normalize_request_url(url) == url
    assert normalize_request_url(" https://model.example:8443/custom/ ") == "https://model.example:8443/custom/"


@pytest.mark.parametrize("url", ["https://127.0.0.1/v1", "https://10.0.0.1/v1", "https://[::1]/v1", "https://169.254.169.254/v1", "https://model.internal/messages"])
def test_private_and_reserved_addresses_allowed(url):
    assert normalize_request_url(url) == url


def test_encryption_and_user_binding(model_config):
    encrypted = encrypt_key(10, "test-api-key")
    assert "test-api-key" not in encrypted
    assert decrypt_key(10, encrypted) == "test-api-key"
    with pytest.raises(ServiceUnavailable):
        decrypt_key(11, encrypted)
    with pytest.raises(ServiceUnavailable):
        decrypt_key(10, encrypted[:-5])
    assert "test-api-key" not in repr(ModelConnection("https://model.example/v1", "test-api-key"))


def test_custom_transport_and_redirect_refused(model_config, monkeypatch):
    original_client = httpx.AsyncClient
    seen = []

    def handler(request):
        seen.append(request)
        assert request.headers["authorization"] == "Bearer test-api-key"
        assert str(request.url) == "https://model.example/custom/path"
        assert request.headers["host"] == "model.example"
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    def client(**kwargs):
        assert kwargs["follow_redirects"] is False
        assert kwargs["trust_env"] is False
        return original_client(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(llm.httpx, "AsyncClient", client)
    with pytest.raises(llm.ModelError, match="302"):
        asyncio.run(llm.call_model([], model="custom", connection=ModelConnection(
            "https://model.example/custom/path", "test-api-key")))
    assert len(seen) == 1


@pytest.mark.parametrize("api_format", ["openai", "anthropic"])
@pytest.mark.parametrize("host", ["model.example", "127.0.0.1", "model.internal"])
def test_protocol_request_response(monkeypatch, api_format, host):
    original_client = httpx.AsyncClient

    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "国产厂商/model-id"
        assert str(request.url) == f"https://{host}/exact/path/"
        assert body["max_tokens"] == 1800
        if api_format == "anthropic":
            assert request.headers["x-api-key"] == "test-key"
            assert request.headers["anthropic-version"] == "2023-06-01"
            assert "authorization" not in request.headers
            assert "response_format" not in body
            assert body["system"].startswith("system prompt")
            assert body["messages"] == [{"role": "user", "content": "question"}]
            return httpx.Response(200, json={"content": [
                {"type": "thinking", "thinking": "not returned"},
                {"type": "text", "text": '{"ok":'}, {"type": "text", "text": "true}"},
            ], "usage": {"input_tokens": 4, "output_tokens": 2}, "stop_reason": "end_turn"})
        assert request.headers["authorization"] == "Bearer test-key"
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok":true}'}}],
                                       "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6}})

    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kwargs: original_client(**kwargs, transport=httpx.MockTransport(handler)))
    content, usage = asyncio.run(llm.call_model([
        {"role": "system", "content": "system prompt"}, {"role": "user", "content": "question"},
    ], model="国产厂商/model-id", json_mode=True, connection=ModelConnection(
        f"https://{host}/exact/path/", "test-key", api_format)))
    assert json.loads(content) == {"ok": True}
    assert usage["total_tokens"] == 6


def test_validation_never_echoes_credentials():
    app.dependency_overrides[current_user] = lambda: {"id": 123}
    try:
        with TestClient(app) as client:
            for path in ["/api/models", "/api/models/test"]:
                response = client.post(path, json={"api_key": "must-not-appear", "request_url": []})
                assert response.status_code == 422
                assert "must-not-appear" not in response.text
                assert "input" not in response.text
    finally:
        app.dependency_overrides.pop(current_user, None)
@pytest.mark.parametrize("api_format,base,expected", [
    ("openai", "https://model.example/compatible-mode/v1/", "https://model.example/compatible-mode/v1/chat/completions"),
    ("anthropic", "https://model.example/apps/anthropic", "https://model.example/apps/anthropic/v1/messages"),
    ("anthropic", "https://model.example/v1/", "https://model.example/v1/messages"),
])
def test_base_and_full_url_modes(api_format, base, expected):
    from app.model_connections import resolve_request_url

    assert resolve_request_url(base, api_format, False) == expected
    assert resolve_request_url(expected, api_format, True) == expected
    assert resolve_request_url("https://model.example/custom/", api_format) == "https://model.example/custom/"
