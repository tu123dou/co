"""用户模型配置；密文只留在仓储，公开响应使用明确字段白名单。"""

import uuid

from sqlalchemy import select, update, func

from .. import schema as s
from ..db import engine
from ..errors import InvalidRequest, ResourceNotFound
from ..model_connections import ModelConnection, resolve_request_url, decrypt_key, encrypt_key
from ..user_settings import ensure_user_settings, DEFAULT_USER_SETTINGS


def public_models(preferences: dict) -> list[dict[str, str | bool]]:
    return [{**{key: model[key] for key in ("id", "request_url", "model_name", "api_format", "display_name")}, "full_url": model.get("full_url", True)}
            for model in preferences.get("custom_models", [])]


def find_model(preferences: dict, model_id: str) -> dict:
    for model in preferences.get("custom_models", []):
        if model["id"] == model_id:
            return model
    raise ResourceNotFound("模型不存在或不属于当前用户")


def connection_for(preferences: dict, user_id: int) -> ModelConnection | None:
    model_id = preferences.get("custom_model_id")
    if not model_id:
        return None
    model = find_model(preferences, model_id)
    return ModelConnection(resolve_request_url(model["request_url"], model["api_format"], model.get("full_url", True)), decrypt_key(user_id, model["encrypted_key"]), model["api_format"])


def add_model(user_id: int, request_url: str, api_key: str, model_name: str, api_format: str, display_name: str = "", full_url: bool = True) -> dict:
    endpoint = resolve_request_url(request_url, api_format, full_url)
    request_url = request_url.strip()
    encrypted_key = encrypt_key(user_id, api_key)
    with engine.begin() as conn:
        ensure_user_settings(conn, user_id)
        preferences = dict(conn.execute(select(s.user_workbench_settings).where(
            s.user_workbench_settings.c.user_id == user_id
        ).with_for_update()).mappings().one())
        models = preferences["custom_models"]
        if len(models) >= 20:
            raise InvalidRequest("每名用户最多添加 20 个自定义模型")
        if any(resolve_request_url(m["request_url"], m["api_format"], m.get("full_url", True)) == endpoint and m["model_name"] == model_name and m["api_format"] == api_format for m in models):
            raise InvalidRequest("该地址和模型名称已存在")
        model = {"id": str(uuid.uuid4()), "request_url": request_url, "model_name": model_name,
                 "api_format": api_format, "display_name": display_name or model_name,
                 "full_url": full_url,
                 "encrypted_key": encrypted_key}
        conn.execute(update(s.user_workbench_settings).where(
            s.user_workbench_settings.c.user_id == user_id
        ).values(custom_models=[*models, model], updated_at=func.now()))
    return public_models({"custom_models": [model]})[0]


def edit_model(user_id: int, model_id: str, values: dict) -> dict:
    with engine.begin() as conn:
        preferences = dict(conn.execute(select(s.user_workbench_settings).where(
            s.user_workbench_settings.c.user_id == user_id
        ).with_for_update()).mappings().one_or_none() or {})
        old = find_model(preferences, model_id)
        values = {"full_url": True, **old, **values}
        resolve_request_url(values["request_url"], values["api_format"], values["full_url"])
        model = {**old, **{key: values[key] for key in ("request_url", "model_name", "api_format", "full_url")},
                 "display_name": values["display_name"] or values["model_name"]}
        if values.get("api_key"):
            model["encrypted_key"] = encrypt_key(user_id, values["api_key"])
        for other in preferences["custom_models"]:
            if other["id"] != model_id and other["model_name"] == model["model_name"] and other["api_format"] == model["api_format"] and resolve_request_url(other["request_url"], other["api_format"], other.get("full_url", True)) == resolve_request_url(model["request_url"], model["api_format"], model["full_url"]):
                raise InvalidRequest("该地址和模型名称已存在")
        updated = {"custom_models": [model if m["id"] == model_id else m for m in preferences["custom_models"]], "updated_at": func.now()}
        if preferences["custom_model_id"] == model_id:
            updated["llm_model"] = model["model_name"]
        conn.execute(update(s.user_workbench_settings).where(s.user_workbench_settings.c.user_id == user_id).values(**updated))
    return public_models({"custom_models": [model]})[0]


def delete_model(user_id: int, model_id: str) -> None:
    with engine.begin() as conn:
        preferences = dict(conn.execute(select(s.user_workbench_settings).where(
            s.user_workbench_settings.c.user_id == user_id
        ).with_for_update()).mappings().one_or_none() or {})
        find_model(preferences, model_id)
        values = {"custom_models": [m for m in preferences["custom_models"] if m["id"] != model_id], "updated_at": func.now()}
        if preferences["custom_model_id"] == model_id:
            values.update(custom_model_id=None, llm_model=DEFAULT_USER_SETTINGS["llm_model"])
        conn.execute(update(s.user_workbench_settings).where(s.user_workbench_settings.c.user_id == user_id).values(**values))


def edited_connection(user_id: int, model_id: str, values: dict) -> ModelConnection:
    with engine.begin() as conn:
        preferences = ensure_user_settings(conn, user_id)
    model = find_model(preferences, model_id)
    values = {"full_url": True, **model, **values}
    key = values.get("api_key") or decrypt_key(user_id, model["encrypted_key"])
    return ModelConnection(resolve_request_url(values["request_url"], values["api_format"], values["full_url"]), key, values["api_format"])


def selected_connection(
    user_id: int, model: str | None, custom_model_id: str | None,
) -> tuple[str, ModelConnection | None]:
    with engine.begin() as conn:
        preferences = ensure_user_settings(conn, user_id)
    if custom_model_id:
        selected = find_model(preferences, custom_model_id)
        preferences["custom_model_id"] = custom_model_id
        return selected["model_name"], connection_for(preferences, user_id)
    if model:
        return model, None
    return preferences["llm_model"], connection_for(preferences, user_id)
