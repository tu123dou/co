import asyncio, csv, io, json, logging, time, uuid
from collections import defaultdict, deque
from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select, update, delete, text, func
from sqlalchemy.exc import SQLAlchemyError
from . import schema as s
from .db import engine, query_engine
from .auth import current_user, token_for, verify_password
from .config import settings
from .semantic import METRICS, DIMENSIONS
from .query import execute_plan
from .llm import interpret, configured, call_model, ModelError

app = FastAPI(title="经管之星 API", version="0.1.0")
log = logging.getLogger("jingguan")
User = Annotated[dict, Depends(current_user)]
login_attempts = defaultdict(deque)


@app.middleware("http")
async def origin_guard(request, call_next):
    if request.method not in ["GET", "HEAD", "OPTIONS"]:
        origin = request.headers.get("origin")
        if origin and origin != settings().allowed_origin:
            return JSONResponse({"detail": "请求来源不允许"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(SQLAlchemyError)
async def db_error(request, exc):
    log.error("database_request_failed type=%s", type(exc).__name__)
    return JSONResponse(
        {"detail": "数据库暂时不可用，请确认数据库已启动并完成初始化"}, status_code=503
    )


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


@app.post("/api/auth/login")
def login(body: Login, request: Request, response: Response):
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    queue = login_attempts[key]
    while queue and queue[0] < now - 60:
        queue.popleft()
    if len(queue) >= 10:
        raise HTTPException(429, "尝试过于频繁，请稍后再试")
    queue.append(now)
    with engine.connect() as conn:
        user = (
            conn.execute(
                select(s.users).where(
                    s.users.c.username == body.username, s.users.c.active.is_(True)
                )
            )
            .mappings()
            .first()
        )
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "用户名或密码错误")
    response.set_cookie(
        "session",
        token_for(user["id"]),
        httponly=True,
        samesite="strict",
        secure=settings().cookie_secure,
        max_age=43200,
        path="/",
    )
    return {
        "id": user["id"],
        "display_name": user["display_name"],
        "role": user["role"],
    }


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("session", path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: User):
    return {k: user[k] for k in ["id", "display_name", "role"]}


@app.get("/api/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


def dataset_info():
    with engine.connect() as conn:
        d = (
            conn.execute(
                select(s.dataset_versions).order_by(s.dataset_versions.c.id.desc())
            )
            .mappings()
            .first()
        )
    if not d:
        raise HTTPException(503, "请先初始化模拟数据")
    return dict(d)


def get_catalog():
    with engine.connect() as conn:
        catalog = {
            "region": list(conn.scalars(select(s.org_units.c.region).distinct())),
            "city": list(conn.scalars(select(s.org_units.c.city))),
            "org_unit": list(conn.scalars(select(s.org_units.c.name))),
            "industry": list(conn.scalars(select(s.industries.c.name))),
            "product_line": list(conn.scalars(select(s.product_lines.c.name))),
            "salesperson": list(conn.scalars(select(s.salespeople.c.name))),
        }
    return catalog


@app.get("/api/catalog")
def catalog(user: User):
    d = dataset_info()
    return {
        "metrics": METRICS,
        "dimensions": DIMENSIONS,
        "values": get_catalog(),
        "dataset": d,
        "model": {"name": settings().llm_model, "configured": configured()},
        "examples": [
            "今年各经营单元确认收入排名",
            "今年各产品线的收入占比",
            "华东区今年按月收入趋势，与去年同期相比",
            "2026年8月各产品线毛利率",
            "今年各区域收入目标达成率",
            "2026年8月回款额比上个月变化多少",
        ],
    }


@app.post("/api/model/test")
async def test_model(user: User):
    if user["role"] != "admin":
        raise HTTPException(403, "仅管理员可测试模型连接")
    try:
        start = time.monotonic()
        await call_model([{"role": "user", "content": "请只回复 OK"}], max_tokens=16)
        return {
            "ok": True,
            "model": settings().llm_model,
            "duration_ms": round((time.monotonic() - start) * 1000),
        }
    except ModelError as exc:
        raise HTTPException(502, str(exc))


def owned(cid, uid, conn):
    row = (
        conn.execute(
            select(s.conversations).where(
                s.conversations.c.id == cid, s.conversations.c.user_id == uid
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise HTTPException(404, "会话不存在")
    return dict(row)


@app.get("/api/conversations")
def conversations(user: User):
    with engine.connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                select(s.conversations)
                .where(s.conversations.c.user_id == user["id"])
                .order_by(
                    s.conversations.c.pinned.desc(), s.conversations.c.updated_at.desc()
                )
            ).mappings()
        ]


@app.post("/api/conversations")
def new_conversation(user: User):
    cid = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            s.conversations.insert().values(id=cid, user_id=user["id"], title="新对话")
        )
    return {"id": cid}


@app.get("/api/conversations/{cid}")
def conversation(cid: str, user: User):
    with engine.connect() as conn:
        convo = owned(cid, user["id"], conn)
        convo["messages"] = [
            dict(r)
            for r in conn.execute(
                select(s.messages)
                .where(s.messages.c.conversation_id == cid)
                .order_by(s.messages.c.created_at, s.messages.c.id)
            ).mappings()
        ]
    return convo


class ConversationEdit(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    pinned: bool | None = None


@app.patch("/api/conversations/{cid}")
def edit_conversation(cid: str, body: ConversationEdit, user: User):
    with engine.begin() as conn:
        owned(cid, user["id"], conn)
        values = body.model_dump(exclude_none=True)
        if values:
            conn.execute(
                update(s.conversations)
                .where(s.conversations.c.id == cid)
                .values(**values)
            )
    return {"ok": True}


@app.delete("/api/conversations/{cid}")
def remove_conversation(cid: str, user: User):
    with engine.begin() as conn:
        owned(cid, user["id"], conn)
        conn.execute(delete(s.conversations).where(s.conversations.c.id == cid))
    return {"ok": True}


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class Favorite(Question):
    pass


@app.get("/api/favorites")
def favorites(user: User):
    with engine.connect() as conn:
        return [
            dict(r)
            for r in conn.execute(
                select(s.favorite_questions)
                .where(s.favorite_questions.c.user_id == user["id"])
                .order_by(s.favorite_questions.c.created_at.desc())
            ).mappings()
        ]


@app.post("/api/favorites")
def add_favorite(body: Favorite, user: User):
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    with engine.begin() as conn:
        conn.execute(
            pg_insert(s.favorite_questions)
            .values(user_id=user["id"], question=body.question)
            .on_conflict_do_nothing()
        )
    return {"ok": True}


@app.delete("/api/favorites/{fid}")
def delete_favorite(fid: int, user: User):
    with engine.begin() as conn:
        conn.execute(
            delete(s.favorite_questions).where(
                s.favorite_questions.c.id == fid,
                s.favorite_questions.c.user_id == user["id"],
            )
        )
    return {"ok": True}


class Feedback(BaseModel):
    message_id: str
    comment: str = Field(min_length=1, max_length=1000)


@app.post("/api/feedbacks")
def feedback(body: Feedback, user: User):
    with engine.begin() as conn:
        msg = conn.execute(
            select(s.messages)
            .join(s.conversations)
            .where(
                s.messages.c.id == body.message_id,
                s.conversations.c.user_id == user["id"],
                s.messages.c.role == "assistant",
            )
        ).first()
        if not msg:
            raise HTTPException(404, "回答不存在")
        conn.execute(
            s.feedbacks.insert().values(
                user_id=user["id"], message_id=body.message_id, comment=body.comment
            )
        )
    return {"ok": True}


def summary(result, plan):
    metric = METRICS[plan.metric]
    unit = metric["unit"]

    def fmt(v):
        return "暂无可计算数据" if v is None else f"{v:,.2f}{unit}"

    if result["empty"]:
        return "所选范围没有业务记录。请检查筛选条件或更换时间范围。"
    sentence = f"{plan.start_date} 至 {plan.end_date}，{metric['name']}为 {fmt(result['total'])}。"
    if result["previous_total"] is not None:
        sentence += f"对比期间为 {fmt(result['previous_total'])}。"
        if unit == "%" and result["difference"] is not None:
            sentence += f"变化 {result['difference']:+.2f} 个百分点。"
        elif result["change"] is not None:
            sentence += f"{'同比' if plan.comparison == 'yoy' else '环比'} {result['change']:+.2f}%。"
        else:
            sentence += "对比基数为零，增幅不适用。"
    if plan.dimensions and result["rows"]:
        valid = [r for r in result["rows"] if r["value"] is not None]
        if valid:
            top = max(valid, key=lambda r: r["value"])
            sentence += f"当前展示中，{top['label']}最高，为 {fmt(top['value'])}。"
    if result["truncated"]:
        sentence += (
            f"共 {result['group_count']} 组，展示前 {plan.limit} 组；汇总包含全部分组。"
        )
    return sentence


def validate_filters(plan, catalog):
    for f in plan.filters:
        if f.dimension == "month":
            import re

            if any(not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", v) for v in f.values):
                raise ValueError("月份格式需为 YYYY-MM")
        elif f.dimension == "customer":
            with engine.connect() as conn:
                found = set(
                    conn.scalars(
                        select(s.customers.c.name).where(
                            s.customers.c.name.in_(f.values)
                        )
                    )
                )
            if set(f.values) - found:
                raise ValueError("未找到该客户，请使用完整客户名称")
        elif set(f.values) - set(catalog[f.dimension]):
            raise ValueError(
                "未找到筛选值：" + ", ".join(set(f.values) - set(catalog[f.dimension]))
            )


@app.post("/api/conversations/{cid}/ask")
async def ask(cid: str, body: Question, user: User):
    # PostgreSQL advisory lock is shared across backend workers; one active request per user.
    lock = engine.connect()
    locked = lock.scalar(
        text("SELECT pg_try_advisory_lock(7721, :uid)"), {"uid": user["id"]}
    )
    if not locked:
        lock.close()
        raise HTTPException(409, "上一条问题仍在处理中，请完成或停止后再试")
    try:
        with engine.begin() as conn:
            convo = owned(cid, user["id"], conn)
            history = [
                {"role": r["role"], "content": r["content"]}
                for r in conn.execute(
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
                    content=body.question,
                )
            )
            conn.execute(
                update(s.conversations)
                .where(s.conversations.c.id == cid)
                .values(
                    title=body.question[:50]
                    if convo["title"] == "新对话"
                    else convo["title"],
                    updated_at=func.now(),
                )
            )
    except BaseException:
        lock.execute(text("SELECT pg_advisory_unlock(7721, :uid)"), {"uid": user["id"]})
        lock.close()
        raise

    async def stream():
        started = time.monotonic()
        mid = str(uuid.uuid4())
        plan = None
        usage = {}
        result = None
        content = ""
        status = "error"
        error_code = None
        dataset = None
        saved = False

        def event(kind, **kwargs):
            return (
                json.dumps({"type": kind, **kwargs}, ensure_ascii=False, default=str)
                + "\n"
            )

        def persist():
            nonlocal saved
            if saved:
                return
            with engine.begin() as conn:
                if not conn.scalar(
                    select(s.conversations.c.id).where(s.conversations.c.id == cid)
                ):
                    return
                conn.execute(
                    s.messages.insert().values(
                        id=mid,
                        conversation_id=cid,
                        role="assistant",
                        content=content,
                        result=result or {"status": status, "error_code": error_code},
                    )
                )
                conn.execute(
                    s.query_runs.insert().values(
                        id=str(uuid.uuid4()),
                        message_id=mid,
                        plan=plan.model_dump(mode="json") if plan else None,
                        sql="\n\n".join(
                            e["sql"] for e in (result or {}).get("executions", [])
                        ),
                        parameters=(result or {}).get("executions", []),
                        status=status,
                        error_code=error_code,
                        duration_ms=round((time.monotonic() - started) * 1000),
                        model=settings().llm_model,
                        usage=usage,
                        dataset_version=dataset["version"] if dataset else None,
                    )
                )
                if status == "success":
                    conn.execute(
                        update(s.conversations)
                        .where(s.conversations.c.id == cid)
                        .values(
                            context=plan.model_dump(mode="json"), updated_at=func.now()
                        )
                    )
            saved = True

        try:
            yield event("status", stage="理解问题", detail="识别指标、时间与筛选条件")
            dataset = dataset_info()
            catalog = get_catalog()
            interpretation, usage = await interpret(
                body.question,
                convo["context"],
                history,
                catalog,
                {k: str(dataset[k]) for k in ["version", "start_date", "cutoff_date"]},
            )
            if interpretation.action != "query":
                status = interpretation.action
                content = interpretation.explanation
                result = {"status": status}
            else:
                plan = interpretation.plan
                validate_filters(plan, catalog)
                yield event(
                    "status", stage="执行取数", detail=interpretation.explanation
                )
                result = await run_in_threadpool(
                    execute_plan,
                    plan,
                    query_engine,
                    dataset["cutoff_date"],
                    dataset["start_date"],
                )
                yield event("status", stage="整理结果", detail="核对指标并生成图表")
                content = summary(result, plan)
                status = "success"
                result.update(
                    {
                        "status": status,
                        "plan": plan.model_dump(mode="json"),
                        "metric": METRICS[plan.metric],
                        "dataset_version": dataset["version"],
                        "cutoff_date": str(dataset["cutoff_date"]),
                        "model": settings().llm_model,
                        "duration_ms": round((time.monotonic() - started) * 1000),
                        "usage": usage,
                        "suggestions": [
                            "只看上海" if plan.filters else "只看华东区",
                            "换成按区域展示"
                            if "month" in plan.dimensions
                            else "换成按月展示",
                            "查看同一范围的毛利率"
                            if plan.comparison != "none"
                            else "与去年同期相比",
                        ],
                    }
                )
            persist()
            yield event(
                "result",
                message={
                    "id": mid,
                    "role": "assistant",
                    "content": content,
                    "result": result,
                },
            )
        except asyncio.CancelledError:
            status = "cancelled"
            content = "本次生成已停止。"
            error_code = "CANCELLED"
            persist()
            raise
        except (ModelError, ValueError) as exc:
            content = str(exc)
            error_code = exc.code if isinstance(exc, ModelError) else "QUERY_VALIDATION"
            persist()
            yield event(
                "result",
                message={
                    "id": mid,
                    "role": "assistant",
                    "content": content,
                    "result": {"status": "error", "error_code": error_code},
                },
            )
        except Exception as exc:
            log.error("query_failed type=%s message_id=%s", type(exc).__name__, mid)
            content = "本次查询未完成，请重试。若反复出现，请联系管理员查看执行记录。"
            error_code = "QUERY_FAILED"
            persist()
            yield event(
                "result",
                message={
                    "id": mid,
                    "role": "assistant",
                    "content": content,
                    "result": {"status": "error", "error_code": error_code},
                },
            )
        finally:
            lock.execute(
                text("SELECT pg_advisory_unlock(7721, :uid)"), {"uid": user["id"]}
            )
            lock.close()

    return StreamingResponse(
        stream(), media_type="application/x-ndjson", headers={"X-Accel-Buffering": "no"}
    )


@app.get("/api/messages/{mid}/export")
def export(mid: str, user: User):
    with engine.connect() as conn:
        msg = (
            conn.execute(
                select(s.messages)
                .join(s.conversations)
                .where(s.messages.c.id == mid, s.conversations.c.user_id == user["id"])
            )
            .mappings()
            .first()
        )
    if not msg or not msg["result"] or msg["result"].get("status") != "success":
        raise HTTPException(404, "没有可导出的结果")
    out = io.StringIO()
    out.write("\ufeff")
    writer = csv.writer(out)
    result = msg["result"]
    writer.writerow(
        [
            "分组",
            result["metric"]["name"] + "（" + result["metric"]["unit"] + "）",
            "对比值",
            "变化率（%）",
            "差额/百分点",
        ]
    )
    for r in result["rows"]:
        label = r["label"]
        label = (
            "'" + label if label.startswith(("=", "+", "-", "@", "\t", "\r")) else label
        )
        writer.writerow(
            [label, r["value"], r["previous"], r["change"], r["difference"]]
        )
    return Response(
        out.getvalue(),
        media_type="text/csv;charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="query-result.csv"'},
    )
