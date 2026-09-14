"""问数用例：协调解释、只读查询、展示和终态，不依赖 FastAPI。"""

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import aclosing, asynccontextmanager
from datetime import datetime, timezone

from anyio import CancelScope, to_thread

from ..config import settings
from ..contracts import (
    AnalysisEvent,
    AnalysisStep,
    AskContext,
    QueryRun,
    StatusEvent,
    StreamEvent,
)
from ..db import query_engine
from ..llm import ModelError, interpret
from ..presentation.answers import (
    analysis_intro,
    analysis_process,
    analysis_sql_step,
    answer_metadata,
    summary,
)
from ..query import (
    compile_plan,
    execute_plan,
    render_business_sql,
    render_executable_sql,
)
from ..repositories.ask import persist_run, prepare_question
from ..repositories.catalog import dataset_info, get_catalog, validate_filters
from ..repositories.query_lock import UserQueryLock
from ..retrieval import EmbeddingError, retrieve

log = logging.getLogger("jingguan")
run_in_threadpool = to_thread.run_sync


def status_event(*, stage: str, detail: str) -> StatusEvent:
    return {"type": "status", "stage": stage, "detail": detail}


def analysis_event(*, step: AnalysisStep) -> AnalysisEvent:
    return {"type": "analysis", "step": step}


class AskSession:
    def __init__(self, context: AskContext):
        self.context = context
        self.run = QueryRun(message_id=str(uuid.uuid4()), context=context)
        self.started = time.monotonic()
        self.saved = False

    async def persist(self) -> None:
        if self.saved:
            return
        self.run.duration_ms = round((time.monotonic() - self.started) * 1000)
        # 提交与 saved 标记必须一起完成；客户端断连不能留下不确定的提交状态。
        with CancelScope(shield=True):
            await run_in_threadpool(persist_run, self.run)
            self.saved = True

    async def cancel(self) -> None:
        if self.saved:
            return
        self.run.status = "cancelled"
        self.run.content = "本次生成已停止。"
        self.run.error_code = "CANCELLED"
        await self.persist()

    async def stream(self) -> AsyncIterator[StreamEvent]:
        try:
            async with aclosing(self.execute()) as events:
                async for event in events:
                    yield event
            await self.persist()
        except asyncio.CancelledError:
            raise
        except (ModelError, ValueError) as exc:
            self.run.status = "error"
            self.run.content = str(exc)
            self.run.error_code = (
                exc.code if isinstance(exc, ModelError) else "QUERY_VALIDATION"
            )
            await self.persist_error()
        except Exception as exc:
            log.error(
                "query_failed type=%s message_id=%s",
                type(exc).__name__,
                self.run.message_id,
            )
            self.run.status = "error"
            self.run.content = (
                "本次查询未完成，请重试。若反复出现，请查看后端执行记录。"
            )
            self.run.error_code = "QUERY_FAILED"
            await self.persist_error()
        yield {"type": "result", "message": self.run.message()}

    async def persist_error(self) -> None:
        try:
            await self.persist()
        except Exception as exc:
            # 数据库故障时不能保证持久化，但仍返回安全错误且让请求清理释放锁。
            log.error(
                "query_persistence_failed type=%s message_id=%s",
                type(exc).__name__,
                self.run.message_id,
            )

    async def execute(self) -> AsyncIterator[StreamEvent]:
        yield status_event(stage="理解问题", detail="识别指标、时间与筛选条件")
        yield analysis_event(
            step={
                "key": "source",
                "title": "选择数据表与数据时效",
                "status": "running",
                "items": ["正在读取数据版本、业务目录和可查询时间范围……"],
            }
        )
        dataset = await run_in_threadpool(dataset_info)
        self.run.dataset_version = dataset["version"]
        catalog = await run_in_threadpool(get_catalog)
        yield analysis_event(
            step={
                "key": "source",
                "title": "选择数据表与数据时效",
                "status": "running",
                "items": [
                    f"已读取数据版本 {dataset['version']}，数据截止 {dataset['cutoff_date']}。",
                    "正在根据问题确认需要使用的业务表……",
                ],
            }
        )
        yield analysis_event(
            step={
                "key": "plan",
                "title": "解析与计算逻辑",
                "status": "running",
                "items": ["正在通过 pgvector 匹配相关指标、维度和标准实体名称……"],
            }
        )
        semantic_context = []
        try:
            retrieval = await retrieve(self.context.question, dataset["version"])
            semantic_context = retrieval["context"]
            self.run.retrieval_audit = retrieval["audit"]
            for hit in semantic_context:
                if hit["kind"] == "entity":
                    meta = hit["metadata"]
                    catalog.setdefault(meta["dimension"], [])
                    if meta["value"] not in catalog[meta["dimension"]]:
                        catalog[meta["dimension"]].append(meta["value"])
            yield analysis_event(
                step={
                    "key": "plan",
                    "title": "解析与计算逻辑",
                    "status": "running",
                    "items": [
                        f"pgvector 已召回 {len(semantic_context)} 条相关业务知识。",
                        "正在请求大模型生成受控查询计划……",
                    ],
                }
            )
        except EmbeddingError as exc:
            log.warning("semantic_retrieval_unavailable reason=%s", exc)
            self.run.retrieval_audit = {
                "question": self.context.question,
                "embedding_model": settings().embedding_model,
                "top_k": settings().retrieval_top_k,
                "duration_ms": 0,
                "hits": [{"error": str(exc)}],
            }
            yield analysis_event(
                step={
                    "key": "plan",
                    "title": "解析与计算逻辑",
                    "status": "running",
                    "items": ["向量检索暂不可用，正在使用静态业务目录生成查询计划……"],
                }
            )
        interpretation, self.run.usage = await interpret(
            self.context.question,
            self.context.previous_plan,
            self.context.history,
            catalog,
            {k: str(dataset[k]) for k in ["version", "start_date", "cutoff_date"]},
            semantic_context,
            model=self.context.model,
        )
        if interpretation.action != "query":
            self.run.status = interpretation.action
            self.run.content = interpretation.explanation
            self.run.result = {"status": self.run.status}
        else:
            self.run.plan = interpretation.plan
            if self.run.plan is None:
                raise ValueError("查询需要完整计划")
            await run_in_threadpool(validate_filters, self.run.plan, catalog)
            for step in analysis_intro(
                self.context.question,
                interpretation.explanation,
                self.run.plan,
                dataset,
            ):
                yield analysis_event(step=step)
            preview_sql, preview_params = compile_plan(self.run.plan)
            yield analysis_event(
                step=analysis_sql_step(
                    [
                        {
                            "executable_sql": render_executable_sql(
                                preview_sql, preview_params
                            ),
                            "business_sql": render_business_sql(self.run.plan),
                        }
                    ]
                )
            )
            yield analysis_event(
                step={
                    "key": "result",
                    "title": "展示取数结果",
                    "status": "running",
                    "items": ["SQL 已生成，正在通过只读账号执行数据库查询……"],
                }
            )
            yield status_event(stage="执行取数", detail=interpretation.explanation)
            self.run.result = await run_in_threadpool(
                execute_plan,
                self.run.plan,
                query_engine,
                dataset["cutoff_date"],
                dataset["start_date"],
            )
            yield status_event(stage="整理结果", detail="核对指标并生成图表")
            self.run.content = summary(self.run.result, self.run.plan)
            self.run.status = "success"
            completed_at = datetime.now(timezone.utc).isoformat()
            complete_process = analysis_process(
                self.context.question,
                interpretation.explanation,
                self.run.plan,
                self.run.result,
                dataset,
            )
            for step in complete_process[3:]:
                yield analysis_event(step=step)
            self.run.result.update(
                answer_metadata(
                    self.run,
                    dataset,
                    complete_process,
                    completed_at,
                    round((time.monotonic() - self.started) * 1000),
                )
            )


@asynccontextmanager
async def open_session(cid: str, uid: int, question: str) -> AsyncIterator[AskSession]:
    lock = UserQueryLock(uid)
    session = None
    try:
        with CancelScope(shield=True):
            await run_in_threadpool(lock.acquire)
            context = await run_in_threadpool(prepare_question, cid, uid, question)
            session = AskSession(context)
        yield session
    finally:
        # 请求作用域清理也覆盖响应未开始迭代、断连与发送失败。
        with CancelScope(shield=True):
            try:
                if session is not None and not session.saved:
                    if session.run.error_code is None:
                        await session.cancel()
                    else:
                        await session.persist_error()
            finally:
                await run_in_threadpool(lock.release)
