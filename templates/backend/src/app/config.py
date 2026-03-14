"""Application settings via Pydantic BaseSettings + .env file."""

from __future__ import annotations

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated configuration — reads from environment and .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "myapp"
    debug: bool = False
    database_url: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/app"
    )


settings = Settings()
