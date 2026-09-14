"""ASGI 入口：只装配应用、异常处理、中间件和路由。"""

import logging

from fastapi import FastAPI
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from .api import ask, audio, auth, catalog, conversations, exports, feedback, workbench
from .config import settings
from .errors import (
    Forbidden,
    InvalidRequest,
    QueryBusy,
    ResourceNotFound,
    ServiceUnavailable,
)

log = logging.getLogger("jingguan")


async def validation_error(request, exc):
    # Pydantic 的 input 字段可能携带整个提交对象，凭据接口不得回显校验输入。
    if request.url.path == "/api/models" or request.url.path.startswith("/api/models/"):
        return JSONResponse(
            {"detail": "模型配置格式不正确，请检查必填项及长度"}, status_code=422
        )
    if request.url.path in {"/api/auth/login", "/api/auth/register"}:
        return JSONResponse(
            {"detail": "账号信息格式不正确，请检查必填项及长度"}, status_code=422
        )
    return await request_validation_exception_handler(request, exc)


async def origin_guard(request, call_next):
    """限制写请求来源，并为所有响应添加基础安全与禁缓存响应头。"""
    if request.method not in ["GET", "HEAD", "OPTIONS"]:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in settings().allowed_origins:
            return JSONResponse({"detail": "请求来源不允许"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


async def db_error(request, exc):
    log.error("database_request_failed type=%s", type(exc).__name__)
    return JSONResponse(
        {"detail": "数据库暂时不可用，请确认数据库已启动并完成初始化"}, status_code=503
    )


async def application_error(request, exc):
    status = {
        ResourceNotFound: 404,
        ServiceUnavailable: 503,
        QueryBusy: 409,
        Forbidden: 403,
        InvalidRequest: 422,
    }[type(exc)]
    return JSONResponse({"detail": str(exc)}, status_code=status)


def create_app() -> FastAPI:
    application = FastAPI(title="经管之星 API", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings().allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    application.middleware("http")(origin_guard)
    application.add_exception_handler(SQLAlchemyError, db_error)
    application.add_exception_handler(RequestValidationError, validation_error)
    for error in (
        ResourceNotFound,
        ServiceUnavailable,
        QueryBusy,
        Forbidden,
        InvalidRequest,
    ):
        application.add_exception_handler(error, application_error)
    for module in (
        auth,
        audio,
        catalog,
        conversations,
        workbench,
        feedback,
        ask,
        exports,
    ):
        application.include_router(module.router)
    return application


app = create_app()
