"""Selected calendars and conditional, explicitly consented owned-event editing."""

import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, time, timedelta
from typing import Annotated, cast
from urllib.parse import quote
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import AwareDatetime, BaseModel, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import current_user, get_db
from app.integrations.calendar import (
    EDIT_SCOPE,
    LIST_SCOPE,
    CalendarHTTPError,
    CalendarReauth,
    CalendarUnavailable,
    GoogleCalendar,
    decrypt_token,
    encrypt_token,
    replace_busy,
)
from app.integrations.event_feed import AgendaItem, cache_record, details_allowed
from app.integrations.jsonutil import Json, list_value, object_value, string_value
from app.integrations.models import (
    CalendarBusy,
    CalendarConnection,
    CalendarSelection,
    GoogleEventCache,
)
from app.models.auth import User
from app.models.planning import PlanningRecord

router = APIRouter(tags=["Calendar"])
DB = Annotated[AsyncSession, Depends(get_db)]
Owner = Annotated[User, Depends(current_user)]


class SelectionInput(BaseModel):
    calendar_ids: list[str] = Field(max_length=50)


class EventInput(BaseModel):
    calendar_id: str = Field(min_length=1, max_length=512)
    title: str = Field(min_length=1, max_length=500)
    notes: str = Field(default="", max_length=10000)
    start_at: AwareDatetime
    end_at: AwareDatetime
    timezone: str
    all_day: bool = False

    @model_validator(mode="after")
    def valid(self) -> "EventInput":
        try:
            zone = ZoneInfo(self.timezone)
        except (KeyError, ValueError) as exc:
            raise ValueError("Choose a valid timezone.") from exc
        if self.end_at <= self.start_at:
            raise ValueError("End must follow start.")
        if self.all_day and any(
            value.astimezone(zone).timetz().replace(tzinfo=None) != time.min
            for value in (self.start_at, self.end_at)
        ):
            raise ValueError("All-day events must start and end at local midnight.")
        return self

    def provider_body(self) -> dict[str, Json]:
        zone = ZoneInfo(self.timezone)

        def bound(value: datetime) -> dict[str, Json]:
            return (
                {"date": value.astimezone(zone).date().isoformat()}
                if self.all_day
                else {"dateTime": value.isoformat(), "timeZone": self.timezone}
            )

        return {
            "summary": self.title,
            "description": self.notes,
            "start": bound(self.start_at),
            "end": bound(self.end_at),
        }


class EventCreate(EventInput):
    client_event_id: UUID


class EventUpdate(EventInput):
    etag: str = Field(min_length=1, max_length=1024)


async def selections(db: AsyncSession, user_id: str) -> list[CalendarSelection]:
    return list(
        (
            await db.scalars(select(CalendarSelection).where(CalendarSelection.user_id == user_id))
        ).all()
    )


async def selected_ids(db: AsyncSession, connection: CalendarConnection) -> list[str]:
    if not connection.selection_enabled:
        return ["primary"]
    return [row.calendar_id for row in await selections(db, connection.user_id) if row.selected]


async def refresh_calendars(
    db: AsyncSession, connection: CalendarConnection, google: GoogleCalendar, access: str
) -> list[CalendarSelection]:
    from app.integrations.router import require_calendar

    if LIST_SCOPE not in connection.scopes:
        raise HTTPException(
            409,
            detail={
                "code": "calendar_list_consent",
                "message": "Connect calendar selection first.",
            },
        )
    entries: dict[str, dict[str, Json]] = {}
    params = {"maxResults": "250", "showHidden": "true"}
    pages: set[str] = set()
    while True:
        body = await google.request("GET", "/users/me/calendarList", access, params=params)
        for item in list_value(body.get("items", [])):
            value = object_value(item)
            identifier = string_value(value.get("id"))
            if not identifier or len(identifier) > 512:
                raise CalendarUnavailable("Calendar list contains an invalid identifier")
            if not value.get("deleted"):
                entries[identifier] = value
        token = body.get("nextPageToken")
        if not isinstance(token, str) or not token:
            break
        if token in pages or len(pages) >= 20:
            raise CalendarUnavailable("Calendar list pagination did not complete")
        pages.add(token)
        params["pageToken"] = token
    old = {row.calendar_id: row for row in await selections(db, connection.user_id)}
    result = []
    key = require_calendar().token_encryption_key
    for identifier, value in entries.items():
        row = old.pop(identifier, None)
        if row is None:
            row = CalendarSelection(
                user_id=connection.user_id,
                calendar_id=identifier,
                selected=bool(value.get("primary")) and not connection.selection_enabled,
            )
            db.add(row)
        row.access_role = string_value(value.get("accessRole", "none"))
        row.metadata_enc = encrypt_token(
            {
                "name": string_value(value.get("summary", "Google Calendar")),
                "timezone": string_value(value.get("timeZone", "UTC")),
                "primary": bool(value.get("primary")),
            },
            key,
        )
        result.append(row)
    for row in old.values():
        await db.delete(row)
    await db.flush()
    return result


async def context(db: AsyncSession, user: User) -> CalendarConnection:
    from app.integrations.router import connection_for
    from app.routers.planning import lock_owner

    await lock_owner(db, user)
    connection = await connection_for(db, user.id, lock=True)
    if connection.status != "active":
        raise HTTPException(
            409, detail={"code": "calendar_reauth", "message": "Reconnect Google Calendar."}
        )
    return connection


@asynccontextmanager
async def provider_guard(db: AsyncSession, user: User) -> AsyncIterator[None]:
    from app.integrations.router import mark_calendar_reauth

    try:
        yield
    except CalendarReauth as exc:
        await mark_calendar_reauth(db, user.id)
        raise HTTPException(409, detail="Reconnect Google Calendar.") from exc
    except (CalendarUnavailable, httpx.HTTPError, ValueError) as exc:
        await db.rollback()
        raise HTTPException(503, detail="Google Calendar is unavailable. Try again.") from exc


@router.get("/calendars")
async def calendar_list(db: DB, user: Owner) -> dict[str, object]:
    from app.integrations.config import IntegrationSettings

    config = IntegrationSettings()
    connection = await db.scalar(
        select(CalendarConnection).where(CalendarConnection.user_id == user.id)
    )
    envelope: dict[str, object] = {
        "configured": config.calendar_configured,
        "connected": bool(connection and connection.status == "active"),
        "selection_enabled": bool(connection and connection.selection_enabled),
        "write_enabled": bool(
            connection and connection.editing_enabled and EDIT_SCOPE in connection.scopes
        ),
        "calendars": [],
    }
    if (
        not config.calendar_configured
        or connection is None
        or connection.status != "active"
        or LIST_SCOPE not in connection.scopes
    ):
        return envelope
    connection = await context(db, user)
    async with provider_guard(db, user), httpx.AsyncClient(timeout=20) as client:
        google = GoogleCalendar(config, client)
        access = await google.access_token(connection, db)
        rows = await refresh_calendars(db, connection, google, access)
    result = []
    for row in rows:
        meta = decrypt_token(row.metadata_enc, config.token_encryption_key)
        owner = row.access_role == "owner"
        result.append(
            {
                "id": row.calendar_id,
                **meta,
                "access_role": row.access_role,
                "selected": row.selected,
                "can_select": row.access_role != "none",
                "can_read": owner,
                "can_write": owner
                and connection.editing_enabled
                and EDIT_SCOPE in connection.scopes,
            }
        )
    await db.commit()
    return {
        "configured": True,
        "connected": True,
        "selection_enabled": connection.selection_enabled,
        "write_enabled": connection.editing_enabled and EDIT_SCOPE in connection.scopes,
        "calendars": result,
    }


@router.put("/calendars")
async def calendar_selection(body: SelectionInput, db: DB, user: Owner) -> dict[str, object]:
    from app.integrations.router import require_calendar

    connection = await context(db, user)
    async with provider_guard(db, user), httpx.AsyncClient(timeout=20) as client:
        google = GoogleCalendar(require_calendar(), client)
        access = await google.access_token(connection, db)
        rows = await refresh_calendars(db, connection, google, access)
        identifiers = set(body.calendar_ids)
        if identifiers - {row.calendar_id for row in rows if row.access_role != "none"}:
            raise HTTPException(422, detail="Choose accessible calendars from the current list.")
        start = datetime.now(UTC)
        end = start + timedelta(days=21)
        intervals = (
            await google.busy(access, start, end, sorted(identifiers)) if identifiers else []
        )
    for row in rows:
        row.selected = row.calendar_id in identifiers
    connection.selection_enabled = True
    connection.details_from = connection.details_to = None
    connection.details_synced_at = None
    connection.details_error = None
    # Old source availability/details must never survive a changed selection.
    await db.execute(delete(CalendarBusy).where(CalendarBusy.user_id == user.id))
    await replace_busy(db, user.id, start, end, intervals)
    await db.execute(delete(GoogleEventCache).where(GoogleEventCache.user_id == user.id))
    await db.commit()
    return {"calendar_ids": sorted(identifiers)}


async def writable(
    db: AsyncSession,
    connection: CalendarConnection,
    google: GoogleCalendar,
    access: str,
    calendar_id: str,
) -> CalendarSelection:
    if not connection.editing_enabled or EDIT_SCOPE not in connection.scopes:
        raise HTTPException(
            403,
            detail={
                "code": "calendar_write_consent",
                "message": "Enable Google event editing first.",
            },
        )
    rows = await refresh_calendars(db, connection, google, access)
    row = next((row for row in rows if row.calendar_id == calendar_id), None)
    if row is None or row.access_role != "owner" or not row.selected:
        raise HTTPException(
            403,
            detail={"code": "calendar_read_only", "message": "Choose a selected calendar you own."},
        )
    return row


async def save_event(
    db: AsyncSession,
    user: User,
    connection: CalendarConnection,
    row: CalendarSelection,
    event: dict[str, Json],
) -> AgendaItem:
    from app.integrations.router import apply_calendar_event, require_calendar

    config = require_calendar()
    meta = decrypt_token(row.metadata_enc, config.token_encryption_key)
    timezone = string_value(meta.get("timezone", user.timezone))
    cached = cache_record(
        user.id,
        event,
        timezone,
        string_value(meta.get("name")),
        config.token_encryption_key,
        calendar_id=row.calendar_id,
    )
    await db.execute(
        delete(GoogleEventCache).where(
            GoogleEventCache.user_id == user.id,
            GoogleEventCache.calendar_id == row.calendar_id,
            GoogleEventCache.provider_event_id == cached.provider_event_id,
        )
    )
    if details_allowed(connection):
        db.add(cached)
    blocks = (
        await db.scalars(
            select(PlanningRecord)
            .where(PlanningRecord.user_id == user.id, PlanningRecord.kind == "block")
            .with_for_update()
        )
    ).all()
    for block in blocks:
        if (
            block.payload.get("google_event_id") == cached.provider_event_id
            and block.payload.get("google_calendar_id", connection.app_calendar_id)
            == row.calendar_id
        ):
            apply_calendar_event(block, event, user.timezone, timezone)
    connection.details_from = connection.details_to = None
    await db.flush()
    return AgendaItem(
        id=f"google:{row.calendar_id}:{cached.provider_event_id}",
        source="google",
        source_id=cached.provider_event_id,
        title=string_value(event.get("summary", "")),
        notes=string_value(event.get("description", "")),
        start_at=cached.start_date.isoformat()
        if cached.all_day and cached.start_date
        else cached.start_at.isoformat(),
        end_at=cached.end_date.isoformat()
        if cached.all_day and cached.end_date
        else cached.end_at.isoformat(),
        all_day=cached.all_day,
        timezone=cached.timezone,
        status=string_value(event.get("status", "confirmed")),
        editable=True,
        recurring=cached.recurring,
        occurrence_date=cached.occurrence_date.isoformat() if cached.occurrence_date else None,
        calendar_id=row.calendar_id,
        calendar_name=string_value(meta.get("name")),
        etag=string_value(event.get("etag", "")),
    )


async def refresh_selected_busy(
    db: AsyncSession,
    user: User,
    connection: CalendarConnection,
    google: GoogleCalendar,
    access: str,
) -> None:
    identifiers = await selected_ids(db, connection)
    start = datetime.now(UTC)
    end = start + timedelta(days=21)
    intervals = await google.busy(access, start, end, identifiers) if identifiers else []
    await replace_busy(db, user.id, start, end, intervals)


async def event_operation(
    db: AsyncSession,
    user: User,
    calendar_id: str,
    event_id: str,
    operation: str,
    body: EventInput | None = None,
    etag: str | None = None,
    client_id: str | None = None,
) -> AgendaItem | None:
    from app.integrations.router import mark_calendar_reauth, require_calendar

    connection = await context(db, user)
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            google = GoogleCalendar(require_calendar(), client)
            access = await google.access_token(connection, db)
            row = await writable(db, connection, google, access, calendar_id)
            path = f"/calendars/{quote(calendar_id, safe='')}/events"
            if operation == "POST":
                assert body is not None and client_id is not None
                identifier = "k" + hashlib.sha256((user.id + client_id).encode()).hexdigest()[:40]
                payload = body.provider_body()
                payload.update(
                    {
                        "id": identifier,
                        "extendedProperties": {"private": {"kairos_client_event_id": client_id}},
                    }
                )
                try:
                    event = await google.request("POST", path, access, payload)
                except CalendarHTTPError as exc:
                    if exc.status_code != 409:
                        raise
                    event = await google.request("GET", path + "/" + identifier, access)
                    private = object_value(
                        object_value(event.get("extendedProperties")).get("private")
                    )
                    if (
                        private.get("kairos_client_event_id") != client_id
                        or event.get("status") == "cancelled"
                    ):
                        raise HTTPException(
                            409, detail="The event request conflicts with an existing event."
                        ) from exc
            else:
                path += "/" + quote(event_id, safe="")
                event = await google.request("GET", path, access)
                if event.get("recurrence"):
                    raise HTTPException(
                        422, detail="Choose a single occurrence; series editing is not supported."
                    )
                if operation != "GET":
                    if event.get("etag") != etag:
                        raise HTTPException(
                            409,
                            detail={
                                "code": "calendar_stale",
                                "message": "This event changed. Refresh before editing.",
                            },
                        )
                    event = await google.request(
                        operation,
                        path,
                        access,
                        body.provider_body() if body else None,
                        headers={"If-Match": cast(str, etag)},
                        retry_safe=False,
                    )
                    if operation == "DELETE":
                        await db.execute(
                            delete(GoogleEventCache).where(
                                GoogleEventCache.user_id == user.id,
                                GoogleEventCache.calendar_id == calendar_id,
                                GoogleEventCache.provider_event_id == event_id,
                            )
                        )
                        blocks = (
                            await db.scalars(
                                select(PlanningRecord)
                                .where(
                                    PlanningRecord.user_id == user.id,
                                    PlanningRecord.kind == "block",
                                )
                                .with_for_update()
                            )
                        ).all()
                        for block in blocks:
                            if (
                                block.payload.get("google_event_id") == event_id
                                and block.payload.get(
                                    "google_calendar_id", connection.app_calendar_id
                                )
                                == calendar_id
                            ):
                                block.payload = {**block.payload, "status": "cancelled"}
                        connection.details_from = connection.details_to = None
                        await refresh_selected_busy(db, user, connection, google, access)
                        await db.commit()
                        return None
            result = await save_event(db, user, connection, row, event)
            if operation != "GET":
                await refresh_selected_busy(db, user, connection, google, access)
            await db.commit()
            return result
    except CalendarReauth as exc:
        await mark_calendar_reauth(db, user.id)
        raise HTTPException(409, detail="Reconnect Google Calendar.") from exc
    except CalendarHTTPError as exc:
        await db.rollback()
        raise HTTPException(
            409 if exc.status_code in {404, 410, 412} else 503,
            detail={
                "code": "calendar_stale"
                if exc.status_code in {404, 410, 412}
                else "calendar_unavailable",
                "message": "Refresh the calendar and try again.",
            },
        ) from exc
    except (CalendarUnavailable, httpx.HTTPError, ValueError) as exc:
        await db.rollback()
        raise HTTPException(503, detail="Google Calendar could not complete this request.") from exc


@router.post("/events", response_model=AgendaItem)
async def create_event(body: EventCreate, db: DB, user: Owner) -> AgendaItem | None:
    return await event_operation(
        db, user, body.calendar_id, "", "POST", body, client_id=str(body.client_event_id)
    )


@router.get("/events/{event_id}", response_model=AgendaItem)
async def get_event(event_id: str, calendar_id: str, db: DB, user: Owner) -> AgendaItem | None:
    return await event_operation(db, user, calendar_id, event_id, "GET")


@router.patch("/events/{event_id}", response_model=AgendaItem)
async def update_event(event_id: str, body: EventUpdate, db: DB, user: Owner) -> AgendaItem | None:
    return await event_operation(
        db, user, body.calendar_id, event_id, "PATCH", body, etag=body.etag
    )


@router.delete("/events/{event_id}", status_code=204)
async def delete_event(event_id: str, calendar_id: str, etag: str, db: DB, user: Owner) -> Response:
    await event_operation(db, user, calendar_id, event_id, "DELETE", etag=etag)
    return Response(status_code=204)
