"""Owner-scoped, expiring reports from an explicitly paired Linux companion.

Reports describe what a paired helper claimed; they do not grant process control to
web pages or prove an operating-system action. Executable paths stay on the device.
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select

from app.integrations.models import ExtensionToken
from app.integrations.router import DB, ExtUser, Owner, active_focus, digest
from app.models.auth import User
from app.models.planning import PlanningRecord

router = APIRouter(prefix="/api/v1", tags=["Native companion"])
FRESH_SECONDS = 30


class NativeReport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    device_id: UUID
    label: str = Field(default="Linux companion", min_length=1, max_length=120)
    mode: Literal["idle", "blocking", "paused", "error"]
    suspended_count: int = Field(ge=0, le=4096)
    session_id: UUID | None = None
    ends_at: datetime | None = None

    @field_validator("ends_at")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("A timezone is required")
        return value.astimezone(UTC) if value else None

    @model_validator(mode="after")
    def blocking_needs_session(self) -> "NativeReport":
        if self.mode == "blocking" and (not self.session_id or not self.ends_at):
            raise ValueError("A blocking report needs its session and deadline")
        if self.mode in {"idle", "paused"} and self.suspended_count:
            raise ValueError("Idle and paused reports cannot contain suspended processes")
        return self


class NativeDevice(NativeReport):
    credential_id: str
    last_seen_at: datetime
    connected: bool
    # This is explicitly a recent helper report, not independently measured activity.
    reporting: Literal["helper"] = "helper"


@router.post("/ext/native/status", response_model=NativeDevice)
async def report(body: NativeReport, request: Request, db: DB, user: ExtUser) -> NativeDevice:
    await db.scalar(select(User).where(User.id == user.id).with_for_update())
    credential = await db.scalar(
        select(ExtensionToken).where(
            ExtensionToken.user_id == user.id,
            ExtensionToken.token_hash == digest(request.headers["Authorization"][7:]),
        )
    )
    if credential is None:
        raise HTTPException(401, detail="Pair the companion again")
    if body.mode == "blocking":
        focus = await active_focus(db, user.id)
        if (
            focus is None
            or str(body.session_id) != focus.id
            or body.ends_at is None
            or body.ends_at <= datetime.now(UTC)
            or body.ends_at > datetime.fromisoformat(str(focus.payload["ends_at"]))
        ):
            raise HTTPException(409, detail="This focus session is no longer active")
    row = await db.scalar(
        select(PlanningRecord).where(
            PlanningRecord.user_id == user.id,
            PlanningRecord.kind == "native_device",
            PlanningRecord.payload["credential_id"].as_string() == credential.id,
        )
    )
    value = body.model_dump(mode="json") | {
        "credential_id": credential.id,
        "last_seen_at": datetime.now(UTC).isoformat(),
    }
    if row is None:
        db.add(PlanningRecord(user_id=user.id, kind="native_device", payload=value))
    else:
        row.payload = value
    await db.commit()
    return NativeDevice.model_validate(value | {"connected": True})


@router.get("/native/devices", response_model=list[NativeDevice])
async def devices(db: DB, user: Owner) -> list[NativeDevice]:
    credentials = set(
        (await db.scalars(select(ExtensionToken.id).where(ExtensionToken.user_id == user.id))).all()
    )
    rows = (
        await db.scalars(
            select(PlanningRecord).where(
                PlanningRecord.user_id == user.id,
                PlanningRecord.kind == "native_device",
            )
        )
    ).all()
    now = datetime.now(UTC)
    result = []
    for row in rows:
        if row.payload.get("credential_id") not in credentials:
            continue
        seen = datetime.fromisoformat(str(row.payload["last_seen_at"]))
        connected = 0 <= (now - seen).total_seconds() <= FRESH_SECONDS
        result.append(NativeDevice.model_validate(row.payload | {"connected": connected}))
    return sorted(result, key=lambda item: item.last_seen_at, reverse=True)
