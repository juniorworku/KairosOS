"""User-owned integration state; credentials and bearer values never stored in plaintext."""

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def new_id() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class CalendarConnection(Base):
    __tablename__ = "calendar_connections"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    token_enc: Mapped[bytes] = mapped_column(LargeBinary)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    app_calendar_id: Mapped[str | None] = mapped_column(String(512))
    sync_token: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[str] = mapped_column(String(30), default="active")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    details_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    details_from: Mapped[date | None] = mapped_column(Date)
    details_to: Mapped[date | None] = mapped_column(Date)
    details_timezone: Mapped[str | None] = mapped_column(String(80))
    details_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    details_error: Mapped[str | None] = mapped_column(String(300))


class CalendarBusy(Base):
    __tablename__ = "calendar_busy_intervals"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CalendarState(Base):
    __tablename__ = "calendar_oauth_states"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    verifier: Mapped[str] = mapped_column(String(128))
    write_access: Mapped[bool] = mapped_column(default=False)
    details_access: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExtensionPair(Base):
    __tablename__ = "extension_pair_codes"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE")
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExtensionToken(Base):
    __tablename__ = "extension_tokens"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    label: Mapped[str] = mapped_column(String(120), default="Chrome")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AICall(Base):
    __tablename__ = "ai_calls"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    task: Mapped[str] = mapped_column(String(50))
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(200))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="reserved")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class GoogleEventCache(Base):
    """Consented primary-calendar instances; titles and notes are encrypted at rest."""

    __tablename__ = "google_event_cache"
    __table_args__ = (
        UniqueConstraint("user_id", "calendar_id", "provider_event_id"),
        Index("ix_google_event_cache_owner_time", "user_id", "start_at", "end_at"),
        Index("ix_google_event_cache_owner_date", "user_id", "start_date", "end_date"),
    )
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    calendar_id: Mapped[str] = mapped_column(String(512), default="primary")
    provider_event_id: Mapped[str] = mapped_column(String(1024))
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    all_day: Mapped[bool] = mapped_column(Boolean)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    timezone: Mapped[str] = mapped_column(String(80))
    recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    occurrence_date: Mapped[date | None] = mapped_column(Date)
    details_enc: Mapped[bytes] = mapped_column(LargeBinary)
