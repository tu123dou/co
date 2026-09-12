"""用户认证模块：负责密码哈希、会话令牌签发和当前用户校验。"""

import base64, hashlib, hmac, secrets
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import HTTPException, Request
from sqlalchemy import select
from .config import settings
from .db import engine
from .schema import users


def hash_password(password):
    """使用随机盐和 scrypt 生成可持久化的密码摘要。"""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return base64.b64encode(salt + digest).decode()


def verify_password(password, stored):
    """以恒定时间比较用户输入和数据库中的密码摘要。"""
    try:
        raw = base64.b64decode(stored)
        return hmac.compare_digest(
            hashlib.scrypt(password.encode(), salt=raw[:16], n=16384, r=8, p=1),
            raw[16:],
        )
    except (ValueError, TypeError):
        return False


def token_for(user_id):
    """签发十二小时有效的登录会话 JWT。"""
    return jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(hours=12)},
        settings().jwt_secret,
        algorithm="HS256",
    )


def current_user(request: Request):
    """解析会话 Cookie，并确认对应数据库用户仍处于启用状态。"""
    try:
        payload = jwt.decode(
            request.cookies.get("session", ""),
            settings().jwt_secret,
            algorithms=["HS256"],
        )
        uid = int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "请先登录")
    with engine.connect() as conn:
        user = (
            conn.execute(
                select(users).where(users.c.id == uid, users.c.active.is_(True))
            )
            .mappings()
            .first()
        )
    if not user:
        raise HTTPException(401, "账号不可用")
    return dict(user)
