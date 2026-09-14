"""通过真实本地数据库验证说明回答、历史、权限及经营追问上下文。"""

import json
import os

import pytest
from app import schema as s
from app.db import engine
from app.information import InformationRequest
from app.presentation.information import business_tables
from app.semantic import Interpretation
from app.services import ask
from sqlalchemy import select

pytestmark = pytest.mark.skipif(
    os.getenv("TEST_DATABASE") != "1", reason="Requires confirmed local database"
)


def ask_message(client, cid, question):
    response = client.post(f"/api/conversations/{cid}/ask", json={"question": question})
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[-1]["type"] == "result"
    return events[-1]["message"]


def test_four_questions_are_answered_without_model_and_preserve_context(
    clients, monkeypatch
):
    a, b = clients
    cid = a.post("/api/conversations").json()["id"]
    query = ask_message(a, cid, "今年各产品线收入")
    prior = a.get(f"/api/conversations/{cid}").json()["context"]
    normal_interpret = ask.interpret

    async def forbidden(*args, **kwargs):
        raise AssertionError("No model or embedding request for metadata")

    monkeypatch.setattr(ask, "interpret", forbidden)
    monkeypatch.setattr(ask, "retrieve", forbidden)
    answers = {}
    for question in ["你是谁", "有多少个数据表", "数据日期范围", "每个数据表是什么"]:
        message = ask_message(a, cid, question)
        answers[question] = message
        assert message["result"]["status"] == "info"
        assert "rows" not in message["result"] and "plan" not in message["result"]
        assert a.get(f"/api/messages/{message['id']}/export").status_code == 404
        assert b.get(f"/api/conversations/{cid}").status_code == 404
        with engine.connect() as conn:
            audit = (
                conn.execute(
                    select(s.query_runs).where(
                        s.query_runs.c.message_id == message["id"]
                    )
                )
                .mappings()
                .one()
            )
            assert (
                audit["status"] == "info"
                and audit["sql"] == ""
                and audit["plan"] is None
            )
    assert f"{len(business_tables())} 张" in answers["有多少个数据表"]["content"]
    assert "经管之星" in answers["你是谁"]["content"]
    tables = answers["每个数据表是什么"]["content"]
    for name in business_tables():
        assert name.split(".")[1] in tables
    assert (
        "app." not in tables
        and "password_hash" not in tables
        and "favorite_questions" not in tables
    )
    history = a.get(f"/api/conversations/{cid}").json()
    assert history["context"] == prior
    for message in answers.values():
        saved = next(row for row in history["messages"] if row["id"] == message["id"])
        assert (
            saved["content"] == message["content"]
            and saved["result"] == message["result"]
        )
    assert (
        a.post(
            "/api/feedbacks",
            json={"message_id": answers["你是谁"]["id"], "comment": "说明测试"},
        ).status_code
        == 200
    )

    async def followup(*args, **kwargs):
        assert args[1] == prior
        return await normal_interpret(*args, **kwargs)

    async def no_embedding(*args):
        return {"context": [], "audit": None}

    monkeypatch.setattr(ask, "interpret", followup)
    monkeypatch.setattr(ask, "retrieve", no_embedding)
    assert (
        ask_message(a, cid, "再按区域展示")["result"]["status"]
        == query["result"]["status"]
    )


@pytest.mark.parametrize(
    "table,expected",
    [("contracts", "signed_date"), ("app.users", "当前仅提供可查询业务数据表")],
)
def test_model_interpreted_paraphrases_use_program_generated_content(
    clients, monkeypatch, table, expected
):
    a, _ = clients
    cid = a.post("/api/conversations").json()["id"]

    async def interpret(*args, **kwargs):
        return Interpretation(
            action="info",
            information=InformationRequest(topics=["fields"], table=table),
            explanation="UNTRUSTED_ANSWER",
        ), {"total_tokens": 5}

    monkeypatch.setattr(ask, "interpret", interpret)
    message = ask_message(a, cid, "展开讲一讲这张表里每一列的含义")
    assert message["result"]["status"] == "info"
    assert (
        expected in message["content"] and "UNTRUSTED_ANSWER" not in message["content"]
    )
    assert (
        "app.users" not in message["content"]
        and "password_hash" not in message["content"]
    )
