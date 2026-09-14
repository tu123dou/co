"""自定义模型连接策略与凭据加密；不负责数据库或 HTTP 路由。"""

import base64
import hashlib
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from typing import Literal

from cryptography.fernet import Fernet, InvalidToken

from .config import settings
from .errors import InvalidRequest, ServiceUnavailable


@dataclass(frozen=True)
class ModelConnection:
    request_url: str
    api_key: str = field(repr=False)
    api_format: Literal["openai", "anthropic"] = "openai"


def normalize_request_url(value: str) -> str:
    value = value.strip()
    try:
        url = urlsplit(value)
        valid = (url.scheme == "https" and url.hostname and not url.username
                 and not url.password and not url.query and not url.fragment
                 and url.path not in ("", "/")
                 and not any(c.isspace() or ord(c) < 32 for c in value)
                 and "\\" not in value and "%" not in url.netloc)
        if valid:
            _ = url.port
    except ValueError:
        valid = False
    if not valid:
        raise InvalidRequest("请填写完整的 HTTPS 请求 URL，不得包含账号、查询参数或片段")
    return value


def cipher(user_id: int) -> Fernet:
    cfg = settings()
    secret = cfg.model_encryption_secret or cfg.jwt_secret
    if len(secret) < 32:
        raise ServiceUnavailable("模型凭据加密密钥需至少 32 个字符，请管理员配置 MODEL_ENCRYPTION_SECRET")
    # 独立用途和用户派生，防止密文跨账号复制；升级密钥须先迁移已有密文。
    key = hashlib.sha256(f"custom-model:v1:{user_id}:{secret}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def resolve_request_url(value: str, api_format: str, full_url: bool = True) -> str:
    if full_url:
        return normalize_request_url(value)
    base = value.strip().rstrip("/")
    suffix = "/chat/completions" if api_format == "openai" else (
        "/messages" if base.endswith("/v1") else "/v1/messages"
    )
    return normalize_request_url(base + suffix)


def encrypt_key(user_id: int, api_key: str) -> str:
    return cipher(user_id).encrypt(api_key.encode()).decode()


def decrypt_key(user_id: int, encrypted: str) -> str:
    try:
        return cipher(user_id).decrypt(encrypted.encode()).decode()
    except (InvalidToken, UnicodeError):
        raise ServiceUnavailable("模型凭据无法解密，请管理员检查加密密钥") from None
