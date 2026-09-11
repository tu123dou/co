import base64, hashlib, hmac, secrets
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import HTTPException, Request
from sqlalchemy import select
from .config import settings
from .db import engine
from .schema import users


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return base64.b64encode(salt + digest).decode()


def verify_password(password, stored):
    try:
        raw = base64.b64decode(stored)
        return hmac.compare_digest(
            hashlib.scrypt(password.encode(), salt=raw[:16], n=16384, r=8, p=1),
            raw[16:],
        )
    except (ValueError, TypeError):
        return False


def token_for(user_id):
    return jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(hours=12)},
        settings().jwt_secret,
        algorithm="HS256",
    )


def current_user(request: Request):
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
