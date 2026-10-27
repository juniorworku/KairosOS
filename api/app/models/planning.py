"""User-owned planning records."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PlanningRecord(Base):
    """An aggregate payload with explicit ownership and queryable record kind."""

    __tablename__ = "planning_records"
    __table_args__ = (
        CheckConstraint(
            "kind <> 'goal' OR COALESCE("
            "json_array_length(payload -> 'actions') BETWEEN 1 AND 5, false)",
            name="goal_actions_cap",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
