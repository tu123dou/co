"""workbench HTTP 接口。"""

from fastapi import APIRouter

from ..repositories import workbench as repository
from .dependencies import User
from .schemas import Favorite, WorkbenchSettingsEdit

router = APIRouter()


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
