from functools import lru_cache
from typing import Optional
from zoneinfo import ZoneInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable overrides."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General
    app_name: str = "MARY"
    app_env: str = "development"
    debug: bool = True
    port: int = 8000
    host: str = "0.0.0.0"
    timezone: str = "Asia/Bangkok"

    # Security
    secret_key: str = "change-this-to-a-secure-random-secret-key-in-production"

    # LINE Messaging API
    line_channel_secret: str = ""
    line_channel_access_token: str = ""
    line_bot_user_id: Optional[str] = None

    # Database
    database_url: str = "sqlite+aiosqlite:///./mary.db"

    # LLM Settings
    llm_provider: str = "gemini"
    llm_api_key: str = ""
    llm_model: str = "gemini-3.5-flash"

    # Custom / OpenAI-Compatible LLM Settings
    custom_llm_base_url: Optional[str] = None
    custom_llm_api_key: Optional[str] = None
    custom_llm_model: Optional[str] = None
    custom_llm_provider_name: Optional[str] = None
    custom_llm_enabled: bool = False

    # GitHub Integration
    github_token: Optional[str] = None

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def is_line_configured(self) -> bool:
        return bool(self.line_channel_secret and self.line_channel_access_token)


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()

