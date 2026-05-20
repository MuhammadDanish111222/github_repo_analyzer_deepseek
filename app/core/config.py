from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Live GitHub Repository Analyzer API"
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    allowed_origins: str = ""

    deepseek_api_key: SecretStr = Field(..., description="DeepSeek API key")
    deepseek_base_url: AnyHttpUrl = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-pro"
    deepseek_thinking_type: Literal["enabled", "disabled"] = "enabled"
    deepseek_reasoning_effort: Literal["high", "max"] = "high"

    github_token: SecretStr | None = None

    request_timeout_seconds: float = 60.0
    max_source_file_bytes: int = 200_000
    max_code_chars_for_llm: int = 80_000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
