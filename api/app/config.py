"""Validated environment configuration; no platform secrets are required at M0."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["dev", "test", "staging", "production"] = "dev"
    app_base_url: str = "http://localhost:5173"
    database_url: str = "postgresql+asyncpg://kairos:kairos@localhost:5432/kairos"
    redis_url: str = "redis://localhost:6379/0"
    signup_mode: Literal["closed", "invite", "open"] = "closed"
    readiness_timeout_seconds: float = Field(default=3.0, gt=0, le=30)

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return value.replace(prefix, "postgresql+asyncpg://", 1)
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must be a PostgreSQL asyncpg URL")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
