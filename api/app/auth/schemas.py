from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        local, separator, domain = value.rpartition("@")
        if (
            not separator
            or not local
            or "@" in local
            or "." not in domain
            or any(c.isspace() for c in value)
        ):
            raise ValueError("Enter a valid email address.")
        if any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise ValueError("Enter a valid email address.")
        return value


class MagicVerify(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class MessageResponse(BaseModel):
    message: str


class CSRFResponse(BaseModel):
    csrf_token: str


class AuthConfig(BaseModel):
    google_enabled: bool
    email_enabled: bool
    development_owner_email: str | None = None


class Profile(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    name: str
    avatar_url: str | None
    timezone: str
    work_days: list[int]
    work_start: str
    work_end: str
    daily_max_focus_minutes: int
    energy_peak: str
    ai_enabled: bool
    plan_id: str
    role: str
    disabled_at: datetime | None
    onboarding_completed_at: datetime | None


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    timezone: str | None = None
    work_days: list[int] | None = Field(default=None, min_length=1, max_length=7)
    work_start: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    work_end: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    daily_max_focus_minutes: int | None = Field(default=None, ge=30, le=720)
    energy_peak: Literal["morning", "afternoon", "evening"] | None = None
    ai_enabled: bool | None = None
    onboarding_completed: bool | None = None

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError("Choose a valid timezone.") from exc
        return value

    @field_validator("work_days")
    @classmethod
    def valid_days(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and (
            len(set(value)) != len(value) or any(d < 0 or d > 6 for d in value)
        ):
            raise ValueError("Choose each work day once, from Monday through Sunday.")
        return sorted(value) if value is not None else value

    @model_validator(mode="after")
    def valid_hours(self) -> "ProfileUpdate":
        if self.work_start and self.work_end and self.work_end <= self.work_start:
            raise ValueError("Work hours must end after they start.")
        return self


class AdminProfile(Profile):
    last_seen_at: datetime | None = None
    ai_calls_today: int = 0
    ai_output_tokens_this_month: int = 0


class SessionInfo(BaseModel):
    id: str
    user_agent: str
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    current: bool


class AdminUserUpdate(BaseModel):
    disabled: bool | None = None
    plan_id: str | None = None
    role: Literal["owner", "admin", "user"] | None = None

    @field_validator("plan_id")
    @classmethod
    def valid_plan(cls, value: str | None) -> str | None:
        return str(UUID(value)) if value is not None else None


class InviteRequest(EmailRequest):
    role: Literal["admin", "user"] = "user"
    plan_id: str | None = None
    expires_in_days: int = Field(default=7, ge=1, le=30)

    @field_validator("plan_id")
    @classmethod
    def valid_plan(cls, value: str | None) -> str | None:
        return str(UUID(value)) if value is not None else None
