"""问数服务终态与资源生命周期，不需要数据库或外部模型。"""

import asyncio
from contextlib import aclosing
from copy import deepcopy
from datetime import date
from threading import get_ident

import anyio
import pytest
from app.contracts import AskContext
from app.errors import ResourceNotFound
from app.llm import ModelError
from app.semantic import Interpretation, Plan
from app.services import ask


@pytest.fixture
def workflow(monkeypatch):
    main_thread = get_ident()
    saved = []
    locks = []
    calls = []

    def worker(name):
        assert get_ident() != main_thread, f"{name} blocked the event loop"
        calls.append(name)

    class Lock:
        def __init__(self, uid):
            self.released = False
            locks.append(self)

        def acquire(self):
            worker("acquire")

        def release(self):
            worker("release")
            self.released = True

    def prepare(cid, uid, question):
        worker("prepare")
        return AskContext(cid, uid, question, "test-model", True, {}, [])

    def persist(run):
        worker("persist")
        saved.append(deepcopy(run))

    def dataset():
        worker("dataset")
        return {
            "version": "test",
            "start_date": date(2024, 1, 1),
            "cutoff_date": date(2026, 8, 31),
        }

    def catalog():
        worker("catalog")
        return {}

    def validate(*args):
        worker("validate")

    async def retrieve(*args):
        return {"context": [], "audit": None}

    async def interpret(*args, **kwargs):
        return Interpretation(
            action="query",
            plan=Plan(metric="revenue", start_date="2026-01-01", end_date="2026-08-31"),
            explanation="确认收入",
        ), {}

    def execute(*args):
        worker("execute")
        return {
            "rows": [],
            "total": 0,
            "previous_total": None,
            "change": None,
            "difference": None,
            "group_count": 0,
            "truncated": False,
            "empty": True,
            "executions": [],
            "comparison_range": None,
        }

    for name, value in {
        "UserQueryLock": Lock,
        "prepare_question": prepare,
        "persist_run": persist,
        "dataset_info": dataset,
        "get_catalog": catalog,
        "validate_filters": validate,
        "retrieve": retrieve,
        "interpret": interpret,
        "execute_plan": execute,
    }.items():
        monkeypatch.setattr(ask, name, value)
    return saved, locks, calls


def collect():
    async def run():
        async with ask.open_session("conversation", 1, "确认收入") as session:
            return [event async for event in session.stream()]

    return asyncio.run(run())


def test_success_is_saved_once_and_all_database_work_is_off_loop(workflow):
    saved, locks, calls = workflow
    events = collect()
    assert events[-1]["message"] == saved[0].message()
    assert saved[0].status == "success"
    assert len(saved) == 1 and locks[0].released
    assert {
        "prepare",
        "persist",
        "dataset",
        "catalog",
        "validate",
        "execute",
        "acquire",
        "release",
    } <= set(calls)
    assert sum(event["type"] == "result" for event in events) == 1


@pytest.mark.parametrize("action", ["clarify", "unsupported"])
def test_non_query_outcomes_are_persisted_without_execution(
    workflow, monkeypatch, action
):
    async def interpret(*args, **kwargs):
        return Interpretation(action=action, explanation="请补充信息"), {}

    monkeypatch.setattr(ask, "interpret", interpret)
    events = collect()
    saved, locks, calls = workflow
    assert events[-1]["message"] == saved[0].message()
    assert saved[0].status == action
    assert "execute" not in calls and locks[0].released


@pytest.mark.parametrize(
    "error,code,visible",
    [
        (ModelError("MODEL_TIMEOUT", "模型响应超时"), "MODEL_TIMEOUT", "模型响应超时"),
        (ValueError("请调整日期"), "QUERY_VALIDATION", "请调整日期"),
        (RuntimeError("private-upstream-detail"), "QUERY_FAILED", None),
    ],
)
def test_errors_have_consistent_wire_and_saved_state(
    workflow, monkeypatch, error, code, visible
):
    async def interpret(*args, **kwargs):
        raise error

    monkeypatch.setattr(ask, "interpret", interpret)
    events = collect()
    saved, locks, _ = workflow
    message = events[-1]["message"]
    assert message == saved[0].message()
    assert message["result"] == {"status": "error", "error_code": code}
    assert "private-upstream-detail" not in str(events)
    if visible:
        assert message["content"] == visible
    assert locks[0].released


def test_cancellation_during_model_call_persists_and_releases(workflow, monkeypatch):
    async def run():
        with anyio.CancelScope() as scope:

            async def interpret(*args, **kwargs):
                scope.cancel()
                await anyio.sleep(0)

            monkeypatch.setattr(ask, "interpret", interpret)
            async with ask.open_session("conversation", 1, "问题") as session:
                async for _ in session.stream():
                    pass

    asyncio.run(run())
    saved, locks, _ = workflow
    assert len(saved) == 1
    assert saved[0].message()["result"] == {
        "status": "cancelled",
        "error_code": "CANCELLED",
    }
    assert locks[0].released


@pytest.mark.parametrize("stop_at", ["before_stream", "after_query", "after_done"])
def test_early_close_never_saves_partial_success(workflow, stop_at):
    async def run():
        async with ask.open_session("conversation", 1, "问题") as session:
            if stop_at == "before_stream":
                return
            async with aclosing(session.stream()) as stream:
                async for event in stream:
                    if stop_at == "after_query" and event.get("stage") == "整理结果":
                        break
                    if (
                        stop_at == "after_done"
                        and event.get("step", {}).get("key") == "done"
                    ):
                        break

    asyncio.run(run())
    saved, locks, _ = workflow
    assert len(saved) == 1 and saved[0].status == "cancelled"
    assert saved[0].message()["result"] == {
        "status": "cancelled",
        "error_code": "CANCELLED",
    }
    assert locks[0].released


def test_preparation_failure_releases_lock_without_answer(workflow, monkeypatch):
    def prepare(*args):
        raise ResourceNotFound("会话不存在")

    monkeypatch.setattr(ask, "prepare_question", prepare)
    with pytest.raises(ResourceNotFound):
        collect()
    saved, locks, _ = workflow
    assert not saved and locks[0].released


def test_persistence_failure_returns_safe_error_and_releases(workflow, monkeypatch):
    def persist(run):
        raise RuntimeError("private-database-detail")

    monkeypatch.setattr(ask, "persist_run", persist)
    events = collect()
    assert events[-1]["message"]["result"] == {
        "status": "error",
        "error_code": "QUERY_FAILED",
    }
    assert "private-database-detail" not in str(events)
    assert workflow[1][0].released


def test_presentation_failure_does_not_persist_success(workflow, monkeypatch):
    def metadata(*args):
        raise RuntimeError("presentation failed")

    monkeypatch.setattr(ask, "answer_metadata", metadata)
    events = collect()
    assert events[-1]["message"] == workflow[0][0].message()
    assert workflow[0][0].status == "error"


def test_information_does_not_call_models_or_execute_queries(workflow, monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("Metadata must not call external models")

    monkeypatch.setattr(ask, "interpret", forbidden)
    monkeypatch.setattr(ask, "retrieve", forbidden)

    async def run():
        async with ask.open_session("conversation", 1, "有多少个数据表") as session:
            return [event async for event in session.stream()]

    events = asyncio.run(run())
    saved, locks, calls = workflow
    assert events[-1]["message"] == saved[0].message()
    assert saved[0].status == "info" and saved[0].plan is None
    assert "execute" not in calls and "catalog" not in calls
    assert locks[0].released
