"""feedback HTTP 接口。"""

from fastapi import APIRouter

from ..repositories import feedback as repository
from .dependencies import User
from .schemas import Feedback, FeedbackReview

router = APIRouter()


@router.post("/api/feedbacks")
def feedback(body: Feedback, user: User):
    return repository.feedback(body.message_id, body.comment, user["id"])


@router.get("/api/feedbacks")
def list_feedbacks(
    user: User,
    question: str = "",
    username: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 10,
):
    """分页查询回复校对列表，并找到每条助手回答之前最近的用户问题。"""
    return repository.list_feedbacks(
        user["id"], user["is_superuser"], question, username, status, page, page_size
    )


@router.patch("/api/feedbacks/{feedback_id}")
def review_feedback(feedback_id: int, body: FeedbackReview, user: User):
    """仅允许超管保存跨用户回复核查状态和处理说明。"""
    return repository.review_feedback(
        feedback_id, body.status, body.resolution_note, user["id"], user["is_superuser"]
    )
