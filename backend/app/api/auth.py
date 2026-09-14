"""auth HTTP 接口。"""

import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, Response

from ..auth import token_for, verify_password
from ..config import settings
from ..repositories.users import active_user_by_name
from .dependencies import User
from .schemas import Login

login_attempts = defaultdict(deque)


router = APIRouter()


@router.post("/api/auth/login")
def login(body: Login, request: Request, response: Response):
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    queue = login_attempts[key]
    while queue and queue[0] < now - 60:
        queue.popleft()
    if len(queue) >= 10:
        raise HTTPException(429, "尝试过于频繁，请稍后再试")
    queue.append(now)
    user = active_user_by_name(body.username)
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
        "is_superuser": user["is_superuser"],
    }


@router.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("session", path="/")
    return {"ok": True}


@router.get("/api/auth/me")
def me(user: User):
    return {k: user[k] for k in ["id", "display_name", "is_superuser"]}
