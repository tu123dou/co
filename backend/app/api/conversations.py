"""conversations HTTP 接口。"""

from fastapi import APIRouter

from ..repositories import conversations as repository
from .dependencies import User
from .schemas import ConversationEdit

router = APIRouter()


@router.get("/api/conversations")
def conversations(user: User):
    return repository.conversations(user["id"])


@router.post("/api/conversations")
def new_conversation(user: User):
    return repository.new_conversation(user["id"])


@router.get("/api/conversations/{cid}")
def conversation(cid: str, user: User):
    return repository.conversation(cid, user["id"])


@router.patch("/api/conversations/{cid}")
def edit_conversation(cid: str, body: ConversationEdit, user: User):
    return repository.edit_conversation(
        cid, body.model_dump(exclude_none=True), user["id"]
    )


@router.delete("/api/conversations/{cid}")
def remove_conversation(cid: str, user: User):
    return repository.remove_conversation(cid, user["id"])
