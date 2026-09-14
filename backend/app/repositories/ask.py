"""一次问数的准备事务与终态事务；所有函数均为同步数据库工作。"""

import uuid

from sqlalchemy import func, select, update

from .. import schema as s
from ..contracts import AskContext, QueryRun
from ..db import engine
from ..user_settings import ensure_user_settings, record_successful_question
from .conversations import owned


def prepare_question(cid: str, uid: int, question: str) -> AskContext:
    with engine.begin() as conn:
        convo = owned(cid, uid, conn)
        preferences = ensure_user_settings(conn, uid)
        history = [
            {"role": row["role"], "content": row["content"]}
            for row in conn.execute(
                select(s.messages)
                .where(s.messages.c.conversation_id == cid)
                .order_by(s.messages.c.created_at.desc())
                .limit(6)
            ).mappings()
        ][::-1]
        conn.execute(
            s.messages.insert().values(
                id=str(uuid.uuid4()),
                conversation_id=cid,
                role="user",
                content=question,
            )
        )
        conn.execute(
            update(s.conversations)
            .where(s.conversations.c.id == cid)
            .values(
                title=question[:50] if convo["title"] == "新对话" else convo["title"],
                updated_at=func.now(),
            )
        )
    return AskContext(
        cid,
        uid,
        question,
        preferences["llm_model"],
        preferences["suggestions_enabled"],
        convo["context"],
        history,
    )


def persist_run(run: QueryRun) -> None:
    context = run.context
    with engine.begin() as conn:
        # 锁定归属行，避免检查完成后被并发删除；已删除的会话不重新创建。
        exists = conn.scalar(
            select(s.conversations.c.id)
            .where(
                s.conversations.c.id == context.conversation_id,
                s.conversations.c.user_id == context.user_id,
            )
            .with_for_update()
        )
        if not exists:
            return
        conn.execute(
            s.messages.insert().values(
                id=run.message_id,
                conversation_id=context.conversation_id,
                role="assistant",
                content=run.content,
                result=run.message()["result"],
            )
        )
        query_run_id = str(uuid.uuid4())
        executions = run.result.get("executions", [])
        conn.execute(
            s.query_runs.insert().values(
                id=query_run_id,
                message_id=run.message_id,
                plan=run.plan.model_dump(mode="json") if run.plan else None,
                sql="\n\n".join(execution["sql"] for execution in executions),
                parameters=executions,
                status=run.status,
                error_code=run.error_code,
                duration_ms=run.duration_ms,
                model=context.model,
                usage=run.usage,
                dataset_version=run.dataset_version,
            )
        )
        if run.retrieval_audit:
            conn.execute(
                s.retrieval_events.insert().values(
                    id=str(uuid.uuid4()),
                    query_run_id=query_run_id,
                    **run.retrieval_audit,
                )
            )
        if run.status == "success" and run.plan is not None:
            record_successful_question(conn, context.user_id, context.question)
            conn.execute(
                update(s.conversations)
                .where(
                    s.conversations.c.id == context.conversation_id,
                    s.conversations.c.user_id == context.user_id,
                )
                .values(context=run.plan.model_dump(mode="json"), updated_at=func.now())
            )
