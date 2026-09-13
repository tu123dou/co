"""百炼语音能力：把浏览器录音转成文字，并把 AI 回答合成为语音。"""

import base64

import httpx

from .config import settings


class AudioModelError(Exception):
    """隐藏上游返回中的敏感信息，只向接口层提供可展示的错误。"""


def _credentials():
    cfg = settings()
    api_key = cfg.audio_api_key.strip() or cfg.llm_api_key.strip()
    if not api_key:
        raise AudioModelError("语音服务尚未配置 API Key")
    return cfg, api_key


async def transcribe(audio: bytes, content_type: str) -> str:
    """使用 Qwen-Audio ASR 识别一段不超过 10MB 的短录音。"""
    cfg, api_key = _credentials()
    mime = content_type.split(";", 1)[0].lower()
    formats = {
        "audio/webm": "webm",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/ogg": "ogg",
        "audio/mp4": "mp4",
    }
    audio_format = formats.get(mime)
    if not audio_format:
        raise AudioModelError("当前浏览器生成的录音格式暂不支持")
    data_uri = f"data:{mime};base64,{base64.b64encode(audio).decode()}"
    payload = {
        "model": cfg.asr_model,
        "input": {
            "messages": [{
                "role": "user",
                "content": [{"type": "input_audio", "input_audio": {"data": data_uri}}],
            }]
        },
        "parameters": {
            "format": audio_format,
            "language_hints": ["zh", "en"],
            # 经营分析常用词作为即时热词，减少产品线和财务口径的识别错误。
            "vocabulary": {
                "经营单元": 5,
                "产品线": 5,
                "签约额": 5,
                "回款额": 5,
                "应收": 4,
                "毛利率": 5,
                "同比": 4,
                "环比": 4,
            },
        },
    }
    try:
        async with httpx.AsyncClient(timeout=cfg.audio_timeout) as client:
            response = await client.post(
                cfg.audio_base_url.rstrip("/")
                + "/services/aigc/multimodal-generation/generation",
                headers={"Authorization": f"Bearer {api_key}", "X-DashScope-SSE": "disable"},
                json=payload,
            )
            response.raise_for_status()
            text = response.json().get("output", {}).get("text", "").strip()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise AudioModelError("语音识别失败，请稍后重试") from exc
    if not text:
        raise AudioModelError("没有识别到有效内容，请靠近麦克风后重试")
    return text


async def synthesize(text: str) -> tuple[bytes, str]:
    """使用 Qwen-Audio TTS 合成语音，并由后端下载临时音频后返回浏览器。"""
    cfg, api_key = _credentials()
    payload = {
        "model": cfg.tts_model,
        "input": {
            "text": text,
            "voice": cfg.tts_voice,
            "format": "wav",
            "sample_rate": 24000,
        },
    }
    try:
        async with httpx.AsyncClient(timeout=cfg.audio_timeout) as client:
            response = await client.post(
                cfg.audio_base_url.rstrip("/") + "/services/audio/tts/SpeechSynthesizer",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            response.raise_for_status()
            audio_url = response.json().get("output", {}).get("audio", {}).get("url")
            if not audio_url:
                raise ValueError("missing audio url")
            audio_response = await client.get(audio_url)
            audio_response.raise_for_status()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise AudioModelError("语音合成失败，请稍后重试") from exc
    return audio_response.content, audio_response.headers.get("content-type", "audio/wav")
