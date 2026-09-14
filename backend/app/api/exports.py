"""历史回答 CSV 导出 HTTP 接口。"""

from fastapi import APIRouter, Response

from ..presentation.exports import render_csv
from ..repositories.messages import exportable_result
from .dependencies import User

router = APIRouter()


@router.get("/api/messages/{mid}/export")
def export(mid: str, user: User):
    content, filename = render_csv(exportable_result(mid, user["id"]))
    return Response(
        content,
        media_type="text/csv;charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
