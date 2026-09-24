from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    database_url: str = "sqlite+pysqlite:///./travel.db"
    redis_url: str = "redis://localhost:6379/0"
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen3.7-plus"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    amap_key: str = ""
    tavily_api_key: str = ""
    admin_username: str = "admin"
    admin_password: str = "admin123456"
    breaker_fail_threshold: int = 5
    breaker_window_seconds: int = 60
    breaker_cooldown_seconds: int = 30
    tool_timeout_seconds: float = 8
    model_connect_timeout: float = 10
    model_first_token_timeout: float = 30
    context_token_limit: int = 6000
    recent_turns: int = 6


def get_settings() -> Settings:
    return Settings()
