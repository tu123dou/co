"""应用配置模块：从项目根目录 .env 读取数据库、模型和安全参数。"""

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """集中定义后端所有可通过环境变量覆盖的配置项。"""
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    database_url: str = "postgresql+psycopg://app:app@127.0.0.1:5432/jingguan"
    query_database_url: str = (
        "postgresql+psycopg://analyst:analyst@127.0.0.1:5432/jingguan"
    )
    jwt_secret: str
    admin_password: str
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen3.8-max"
    llm_api_key: str = ""
    llm_timeout: int = 90
    embedding_base_url: str = ""
    embedding_model: str = "qwen3.7-text-embedding-flash"
    embedding_api_key: str = ""
    embedding_dimensions: int = 1024
    retrieval_top_k: int = 12
    # 语音接口与主模型共用百炼 API Key；如使用业务空间专属域名可单独覆盖。
    audio_base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    audio_api_key: str = ""
    asr_model: str = "qwen-audio-3.0-asr-flash"
    tts_model: str = "qwen-audio-3.0-tts-flash"
    tts_voice: str = "longanhuan_v3.6"
    audio_timeout: int = 90
    query_timeout_ms: int = 10000
    cookie_secure: bool = False
    # 多个来源使用英文逗号分隔；保留本地正式页面和前端开发页面。
    allowed_origin: str = (
        "http://127.0.0.1:5178,http://127.0.0.1:5881,http://localhost:5881"
    )

    @property
    def allowed_origins(self) -> list[str]:
        """把环境变量中的来源列表转换为 CORS 和来源校验共用的数组。"""
        return [origin.strip().rstrip("/") for origin in self.allowed_origin.split(",") if origin.strip()]


@lru_cache
def settings():
    """缓存配置对象，避免每次请求重复读取环境文件。"""
    return Settings()
