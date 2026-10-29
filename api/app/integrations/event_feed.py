"""Consented, bounded primary-calendar read model. External events are never editable here."""

from datetime import UTC, date, datetime, time
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.calendar import (
    DETAIL_SCOPE,
    EDIT_SCOPE,
    CalendarUnavailable,
    GoogleCalendar,
    decrypt_token,
    encrypt_token,
    event_bounds,
    parse_timestamp,
)
from app.integrations.config import IntegrationSettings
from app.integrations.jsonutil import Json, object_value, string_value
from app.integrations.models import CalendarConnection, CalendarSelection, GoogleEventCache
from app.models.auth import User
from app.models.planning import PlanningRecord


class AgendaItem(BaseModel):
    id: str
    source: Literal["block", "local", "google"]
    source_id: str
    title: str
    notes: str = ""
    start_at: str
    end_at: str
    all_day: bool
    timezone: str
    status: str
    editable: bool
    goal_id: str | None = None
    action_id: str | None = None
    task_id: str | None = None
    occurrence_date: str | None = None
    recurring: bool = False
    calendar_id: str | None = None
    calendar_name: str | None = None
    etag: str | None = None


def window_bounds(start: date, end: date, timezone: str) -> tuple[datetime, datetime]:
    if end <= start or (end - start).days > 366:
        raise ValueError("Choose a calendar range of 1 to 366 days.")
    zone = ZoneInfo(timezone)
    try:
        return (
            datetime.combine(start, time.min, zone).astimezone(UTC),
            datetime.combine(end, time.min, zone).astimezone(UTC),
        )
    except OverflowError as exc:
        raise ValueError("Agenda dates are outside the supported range.") from exc


def details_allowed(connection: CalendarConnection | None) -> bool:
    return bool(
        connection
        and connection.details_enabled
        and bool({DETAIL_SCOPE, EDIT_SCOPE} & set(connection.scopes))
    )


def cache_record(
    user_id: str,
    event: dict[str, Json],
    timezone: str,
    calendar_name: str,
    key: str,
    *,
    calendar_id: str = "primary",
) -> GoogleEventCache:
    identifier = string_value(event.get("id"))
    if not 1 <= len(identifier) <= 1024:
        raise CalendarUnavailable("Calendar event identifier is invalid")
    start, end, all_day = event_bounds(event, timezone)
    left, right = object_value(event.get("start")), object_value(event.get("end"))
    event_timezone = left.get("timeZone", timezone)
    if not isinstance(event_timezone, str):
        raise CalendarUnavailable("Calendar timezone is invalid")
    try:
        zone = ZoneInfo(event_timezone)
    except ZoneInfoNotFoundError as exc:
        raise CalendarUnavailable("Calendar timezone is invalid") from exc
    original = event.get("originalStartTime")
    occurrence_date = start.astimezone(zone).date()
    if isinstance(original, dict):
        if isinstance(original.get("date"), str):
            occurrence_date = date.fromisoformat(string_value(original["date"]))
        elif isinstance(original.get("dateTime"), str):
            occurrence_date = (
                parse_timestamp(string_value(original["dateTime"])).astimezone(zone).date()
            )
    title = event.get("summary", "")
    notes = event.get("description", "")
    if not isinstance(title, str) or not isinstance(notes, str):
        raise CalendarUnavailable("Calendar event details are invalid")
    return GoogleEventCache(
        user_id=user_id,
        calendar_id=calendar_id,
        provider_event_id=identifier,
        start_at=start,
        end_at=end,
        all_day=all_day,
        start_date=date.fromisoformat(string_value(left.get("date"))) if all_day else None,
        end_date=date.fromisoformat(string_value(right.get("date"))) if all_day else None,
        timezone=event_timezone,
        recurring=bool(event.get("recurringEventId")),
        occurrence_date=occurrence_date,
        details_enc=encrypt_token(
            {
                "etag": string_value(event.get("etag", "")),
                "title": title,
                "notes": notes,
                "calendar_name": calendar_name,
                "status": string_value(event.get("status", "confirmed")),
            },
            key,
        ),
    )


async def refresh_details(
    db: AsyncSession,
    user: User,
    connection: CalendarConnection,
    google: GoogleCalendar,
    access: str,
    start: date,
    end: date,
    config: IntegrationSettings,
) -> None:
    if not details_allowed(connection):
        return
    left, right = window_bounds(start, end, user.timezone)
    from app.integrations.multi_calendar import selections

    sources = [("primary", True)]
    if connection.selection_enabled:
        sources = [
            (row.calendar_id, row.access_role == "owner")
            for row in await selections(db, user.id)
            if row.selected
        ]
    rows_by_id: dict[tuple[str, str], GoogleEventCache] = {}
    for calendar_id, readable in sources:
        if not readable:
            continue
        if calendar_id == "primary":
            events, timezone, calendar_name = await google.event_instances(
                access, left, right, user.timezone
            )
        else:
            events, timezone, calendar_name = await google.event_instances(
                access, left, right, user.timezone, calendar_id
            )
        for event in events:
            row = cache_record(
                user.id,
                event,
                timezone,
                calendar_name,
                config.token_encryption_key,
                calendar_id=calendar_id,
            )
            rows_by_id[(calendar_id, row.provider_event_id)] = row
    await db.execute(delete(GoogleEventCache).where(GoogleEventCache.user_id == user.id))
    db.add_all(list(rows_by_id.values()))
    connection.details_from = start
    connection.details_to = end
    connection.details_timezone = user.timezone
    connection.details_synced_at = datetime.now(UTC)
    connection.details_error = None
    await db.flush()


async def cached_details(
    db: AsyncSession, user: User, start: date, end: date, config: IntegrationSettings
) -> list[AgendaItem]:
    left, right = window_bounds(start, end, user.timezone)
    rows = (
        await db.scalars(
            select(GoogleEventCache)
            .where(
                GoogleEventCache.user_id == user.id,
                or_(
                    (GoogleEventCache.all_day.is_(True))
                    & (GoogleEventCache.start_date < end)
                    & (GoogleEventCache.end_date > start),
                    (GoogleEventCache.all_day.is_(False))
                    & (GoogleEventCache.start_at < right)
                    & (GoogleEventCache.end_at > left),
                ),
            )
            .order_by(GoogleEventCache.start_at, GoogleEventCache.provider_event_id)
        )
    ).all()
    blocks = (
        await db.scalars(
            select(PlanningRecord).where(
                PlanningRecord.user_id == user.id, PlanningRecord.kind == "block"
            )
        )
    ).all()
    connection = await db.scalar(
        select(CalendarConnection).where(CalendarConnection.user_id == user.id)
    )
    choices = list(
        (
            await db.scalars(select(CalendarSelection).where(CalendarSelection.user_id == user.id))
        ).all()
    )
    allowed = {row.calendar_id for row in choices if row.selected and row.access_role == "owner"}
    writable = (
        allowed
        if connection and connection.editing_enabled and EDIT_SCOPE in connection.scopes
        else set()
    )
    linked = {
        (
            str(
                row.payload.get(
                    "google_calendar_id",
                    (connection.app_calendar_id or "primary") if connection else "primary",
                )
            ),
            str(row.payload["google_event_id"]),
        )
        for row in blocks
        if row.payload.get("google_event_id")
    }

    result: list[AgendaItem] = []
    for row in rows:
        if (row.calendar_id, row.provider_event_id) in linked or (
            connection and connection.selection_enabled and row.calendar_id not in allowed
        ):
            continue
        details = decrypt_token(row.details_enc, config.token_encryption_key)
        result.append(
            AgendaItem(
                id=f"google:{row.calendar_id}:{row.provider_event_id}",
                source="google",
                source_id=row.provider_event_id,
                title=string_value(details.get("title")),
                notes=string_value(details.get("notes", "")),
                start_at=row.start_date.isoformat()
                if row.all_day and row.start_date
                else row.start_at.isoformat(),
                end_at=row.end_date.isoformat()
                if row.all_day and row.end_date
                else row.end_at.isoformat(),
                all_day=row.all_day,
                timezone=row.timezone,
                status=string_value(details.get("status", "confirmed")),
                editable=row.calendar_id in writable,
                etag=string_value(details.get("etag", "")) or None,
                recurring=row.recurring,
                occurrence_date=row.occurrence_date.isoformat() if row.occurrence_date else None,
                calendar_id=row.calendar_id,
                calendar_name=string_value(details.get("calendar_name", "Google Calendar")),
            )
        )
    return result
