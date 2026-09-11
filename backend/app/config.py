from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
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
    query_timeout_ms: int = 10000
    cookie_secure: bool = False
    allowed_origin: str = "http://127.0.0.1:5178"


@lru_cache
def settings():
    return Settings()
