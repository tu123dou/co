"""workbench HTTP 接口。"""

import time

from fastapi import APIRouter, HTTPException

from ..repositories import workbench as repository
from ..repositories.models import add_model, edit_model, delete_model, edited_connection
from ..model_connections import ModelConnection, resolve_request_url
from starlette.concurrency import run_in_threadpool
from ..llm import call_model, ModelError
from .dependencies import User
from .schemas import CustomModelCreate, CustomModelEdit, Favorite, WorkbenchSettingsEdit

router = APIRouter()


@router.post("/api/models", status_code=201)
def create_model(body: CustomModelCreate, user: User):
    return add_model(user["id"], body.request_url, body.api_key.get_secret_value(), body.model_name, body.api_format, body.display_name, body.full_url)


def model_edit_values(body: CustomModelEdit) -> dict:
    return {**body.model_dump(exclude={"api_key"}, exclude_unset=True), "api_key": body.api_key.get_secret_value() if body.api_key else None}


@router.patch("/api/models/{model_id}")
def update_model(model_id: str, body: CustomModelEdit, user: User):
    return edit_model(user["id"], model_id, model_edit_values(body))


@router.delete("/api/models/{model_id}")
def remove_model(model_id: str, user: User):
    delete_model(user["id"], model_id)
    return repository.get_workbench_settings(user["id"])


@router.post("/api/models/{model_id}/test")
async def test_edited_model(model_id: str, body: CustomModelEdit, user: User):
    connection = await run_in_threadpool(edited_connection, user["id"], model_id, model_edit_values(body))
    return await check_connection(body.model_name, connection)


async def check_connection(model_name: str, connection: ModelConnection):
    start = time.monotonic()
    try:
        await call_model([{"role": "user", "content": "请只回复 OK"}], model=model_name,
                         connection=connection, max_tokens=64)
    except ModelError as exc:
        raise HTTPException(502, str(exc)) from None
    return {"model": model_name, "duration_ms": round((time.monotonic() - start) * 1000)}


@router.post("/api/models/test")
async def test_custom_model(body: CustomModelCreate, user: User):
    request_url = resolve_request_url(body.request_url, body.api_format, body.full_url)
    return await check_connection(body.model_name, ModelConnection(request_url, body.api_key.get_secret_value(), body.api_format))


@router.get("/api/workbench/settings")
def get_workbench_settings(user: User):
    return repository.get_workbench_settings(user["id"])


@router.patch("/api/workbench/settings")
def edit_workbench_settings(body: WorkbenchSettingsEdit, user: User):
    return repository.edit_workbench_settings(
        body.model_dump(exclude_none=True), user["id"]
    )


@router.get("/api/common-questions")
def common_questions(user: User):
    return repository.common_questions(user["id"])


@router.delete("/api/common-questions/{question_id}")
def delete_common_question(question_id: int, user: User):
    """删除当前用户的问题频次记录，使其从常见问题中消失。"""
    return repository.delete_common_question(question_id, user["id"])


@router.get("/api/favorites")
def favorites(user: User):
    return repository.favorites(user["id"])


@router.post("/api/favorites")
def add_favorite(body: Favorite, user: User):
    return repository.add_favorite(body.question, user["id"])


@router.delete("/api/favorites/{fid}")
def delete_favorite(fid: int, user: User):
    return repository.delete_favorite(fid, user["id"])
