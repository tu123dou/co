"""auth HTTP 接口。"""

import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, Response

from ..auth import hash_password, token_for, verify_password
from ..config import settings
from ..repositories.users import active_user_by_name, create_user
from .dependencies import User
from .schemas import Login, Register

login_attempts = defaultdict(deque)
registration_attempts = defaultdict(deque)


router = APIRouter()


def enforce_rate_limit(attempts, key: str, limit: int):
    now = time.monotonic()
    queue = attempts[key]
    while queue and queue[0] < now - 60:
        queue.popleft()
    if len(queue) >= limit:
        raise HTTPException(429, "尝试过于频繁，请稍后再试")
    queue.append(now)


def set_session_cookie(response: Response, user_id: int):
    response.set_cookie(
        "session",
        token_for(user_id),
        httponly=True,
        samesite="strict",
        secure=settings().cookie_secure,
        max_age=43200,
        path="/",
    )


def public_user(user):
    return {
        "id": user["id"],
        "display_name": user["display_name"],
        "is_superuser": user["is_superuser"],
    }


@router.post("/api/auth/login")
def login(body: Login, request: Request, response: Response):
    key = request.client.host if request.client else "unknown"
    enforce_rate_limit(login_attempts, key, 10)
    user = active_user_by_name(body.username)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "用户名或密码错误")
    set_session_cookie(response, user["id"])
    return public_user(user)


@router.post("/api/auth/register", status_code=201)
def register(body: Register, request: Request, response: Response):
    if not settings().registration_enabled:
        raise HTTPException(403, "当前未开放注册")
    key = request.client.host if request.client else "unknown"
    enforce_rate_limit(registration_attempts, key, 5)
    user = create_user(
        body.username,
        hash_password(body.password.get_secret_value()),
        body.display_name,
    )
    set_session_cookie(response, user["id"])
    return public_user(user)


@router.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("session", path="/")
    return {"ok": True}


@router.get("/api/auth/me")
def me(user: User):
    return {k: user[k] for k in ["id", "display_name", "is_superuser"]}
