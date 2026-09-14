"""audio HTTP 接口。"""

from fastapi import APIRouter, HTTPException, Request, Response

from ..audio import AudioModelError, synthesize, transcribe
from .dependencies import User
from .schemas import SpeechRequest

router = APIRouter()


@router.post("/api/audio/transcribe")
async def transcribe_audio(request: Request, user: User):
    """接收浏览器 MediaRecorder 的原始音频并返回识别文字。"""
    content_type = request.headers.get("content-type", "").split(";", 1)[0]
    audio = await request.body()
    if not audio:
        raise HTTPException(400, "录音内容为空")
    if len(audio) > 10 * 1024 * 1024:
        raise HTTPException(413, "单次录音不能超过 10MB")
    try:
        return {"text": await transcribe(audio, content_type)}
    except AudioModelError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/api/audio/speech")
async def text_to_speech(body: SpeechRequest, user: User):
    """合成 AI 回答并直接代理音频，避免浏览器访问百炼临时地址。"""
    try:
        audio, media_type = await synthesize(body.text.strip())
    except AudioModelError as exc:
        raise HTTPException(502, str(exc)) from exc
    return Response(content=audio, media_type=media_type)
