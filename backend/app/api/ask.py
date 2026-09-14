"""HTTP 适配：管理请求作用域、将服务事件编码为 NDJSON。"""

import json
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..services.ask import AskSession, open_session
from .dependencies import User
from .schemas import Question

router = APIRouter()


async def ask_session(
    cid: str, body: Question, user: User
) -> AsyncIterator[AskSession]:
    async with open_session(cid, user["id"], body.question) as session:
        yield session


@router.post("/api/conversations/{cid}/ask")
async def ask(session: Annotated[AskSession, Depends(ask_session, scope="request")]):
    async def encoded():
        async with aclosing(session.stream()) as events:
            async for event in events:
                yield json.dumps(event, ensure_ascii=False, default=str) + "\n"

    return StreamingResponse(
        encoded(),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no"},
    )
