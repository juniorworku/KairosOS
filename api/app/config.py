"""Validated environment configuration; no platform secrets are required at M0."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["dev", "test", "staging", "production"] = "dev"
    app_base_url: str = "http://localhost:5173"
    database_url: str = "postgresql+asyncpg://kairos:kairos@localhost:5432/kairos"
    redis_url: str = "redis://localhost:6379/0"
    signup_mode: Literal["closed", "invite", "open"] = "closed"
    readiness_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    owner_email: str = ""
    cookie_domain: str = ""
    secret_key: str = ""
    token_encryption_key: str = ""
    magic_link_ttl_min: int = Field(default=15, ge=1, le=60)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"
    email_provider: Literal["smtp", "resend"] = "smtp"
    email_api_key: str = ""
    email_from: str = "Kairos <login@localhost.test>"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False

    @model_validator(mode="after")
    def validate_hosted_settings(self) -> "Settings":
        if self.app_env in {"staging", "production"}:
            if not self.app_base_url.startswith("https://"):
                raise ValueError("Hosted APP_BASE_URL must use HTTPS")
            if len(self.secret_key) < 32:
                raise ValueError("Hosted SECRET_KEY must contain at least 32 characters")
            if self.email_provider == "smtp" and not self.smtp_starttls:
                raise ValueError("Hosted SMTP requires STARTTLS")
        self.owner_email = self.owner_email.strip().lower()
        return self

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
