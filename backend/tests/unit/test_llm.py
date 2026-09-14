"""模型适配测试：验证调用重试、错误归一化和结构化计划解析。"""

import asyncio
import pytest
from app import llm


def test_transient_network_retry(monkeypatch):
    attempts = []

    async def once(*args, **kwargs):
        attempts.append(1)
        if len(attempts) < 3:
            raise llm.ModelError("MODEL_NETWORK", "temporary")
        return "ok", {}

    async def no_sleep(*args):
        pass

    monkeypatch.setattr(llm, "_call_once", once)
    monkeypatch.setattr(llm.asyncio, "sleep", no_sleep)
    assert asyncio.run(llm.call_model([]))[0] == "ok"
    assert len(attempts) == 3


def test_auth_failure_not_retried(monkeypatch):
    attempts = []

    async def once(*args, **kwargs):
        attempts.append(1)
        raise llm.ModelError("MODEL_AUTH", "denied")

    monkeypatch.setattr(llm, "_call_once", once)
    with pytest.raises(llm.ModelError):
        asyncio.run(llm.call_model([]))
    assert len(attempts) == 1


def test_cancellation_not_retried(monkeypatch):
    async def once(*args, **kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(llm, "_call_once", once)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(llm.call_model([]))


def test_selected_model_is_forwarded(monkeypatch):
    received = []

    async def once(*args, **kwargs):
        received.append(kwargs["model"])
        return "ok", {}

    monkeypatch.setattr(llm, "_call_once", once)
    assert asyncio.run(llm.call_model([], model="glm-5.2"))[0] == "ok"
    assert received == ["glm-5.2"]
