"""Local tasks, calendar events and bounded occurrence exceptions."""

from datetime import UTC, date, datetime, time
from typing import Annotated, Any, TypeVar
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import current_user, get_db
from app.models.auth import User
from app.models.planning import PlanningRecord
from app.routers.planning import create, fail, lock_owner, owned, records, unpack
from app.schemas.agenda import (
    AgendaItem,
    EventInput,
    EventPatch,
    EventResponse,
    OccurrencePatch,
    TaskInput,
    TaskPatch,
    TaskResponse,
)
from app.services.recurrence import Occurrence, series_occurrences

router = APIRouter(prefix="/api/v1", tags=["Local agenda"])
DB = Annotated[AsyncSession, Depends(get_db)]
Owner = Annotated[User, Depends(current_user)]
Model = TypeVar("Model", bound=BaseModel)


def validated(model: type[Model], value: dict[str, Any]) -> Model:
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        message = "; ".join(str(item["msg"]) for item in exc.errors())
        raise fail("invalid_agenda", message) from exc


async def _task_goal(db: AsyncSession, user: User, body: TaskInput) -> None:
    if body.goal_id is not None:
        await owned(db, user, "goal", body.goal_id)


async def _event_task(db: AsyncSession, user: User, body: EventInput) -> None:
    if body.task_id is not None:
        await owned(db, user, "task", body.task_id)


@router.get("/tasks", response_model=list[TaskResponse])
async def tasks(db: DB, user: Owner) -> list[dict[str, Any]]:
    return [unpack(row) for row in await records(db, user, "task")]


@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def add_task(body: TaskInput, db: DB, user: Owner) -> dict[str, Any]:
    await lock_owner(db, user)
    await _task_goal(db, user, body)
    row = create(db, user, "task", body.model_dump(mode="json"))
    await db.commit()
    return unpack(row)


@router.get("/tasks/{identifier}", response_model=TaskResponse)
async def get_task(identifier: str, db: DB, user: Owner) -> dict[str, Any]:
    return unpack(await owned(db, user, "task", identifier))


@router.patch("/tasks/{identifier}", response_model=TaskResponse)
async def edit_task(identifier: str, body: TaskPatch, db: DB, user: Owner) -> dict[str, Any]:
    await lock_owner(db, user)
    row = await owned(db, user, "task", identifier)
    payload = validated(TaskInput, row.payload | body.model_dump(mode="json", exclude_unset=True))
    await _task_goal(db, user, payload)
    row.payload = payload.model_dump(mode="json")
    await db.commit()
    return unpack(row)


@router.delete("/tasks/{identifier}", status_code=204)
async def delete_task(identifier: str, db: DB, user: Owner) -> Response:
    await lock_owner(db, user)
    row = await owned(db, user, "task", identifier)
    # Calendar appointments survive deletion of a task; only the optional link is removed.
    for kind in ("event", "exception"):
        for event in await records(db, user, kind):
            if event.payload.get("task_id") == identifier:
                event.payload = {**event.payload, "task_id": None}
            if (
                kind == "exception"
                and event.payload.get("changes", {}).get("task_id") == identifier
            ):
                event.payload = {
                    **event.payload,
                    "changes": {**event.payload["changes"], "task_id": None},
                }
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)


@router.get("/events", response_model=list[EventResponse])
async def events(db: DB, user: Owner) -> list[dict[str, Any]]:
    return [unpack(row) for row in await records(db, user, "event")]


@router.post("/events", response_model=EventResponse, status_code=201)
async def add_event(body: EventInput, db: DB, user: Owner) -> dict[str, Any]:
    await lock_owner(db, user)
    await _event_task(db, user, body)
    row = create(db, user, "event", body.model_dump(mode="json"))
    await db.commit()
    return unpack(row)


@router.get("/events/{identifier}", response_model=EventResponse)
async def get_event(identifier: str, db: DB, user: Owner) -> dict[str, Any]:
    return unpack(await owned(db, user, "event", identifier))


@router.patch("/events/{identifier}", response_model=EventResponse)
async def edit_event(identifier: str, body: EventPatch, db: DB, user: Owner) -> dict[str, Any]:
    await lock_owner(db, user)
    row = await owned(db, user, "event", identifier)
    payload = validated(EventInput, row.payload | body.model_dump(mode="json", exclude_unset=True))
    await _event_task(db, user, payload)
    dates = {occurrence.original_date for occurrence in _occurrences(payload)}
    for exception in await records(db, user, "exception"):
        if exception.payload["event_id"] != identifier or exception.payload.get("cancelled"):
            continue
        day = date.fromisoformat(exception.payload["occurrence_date"])
        if day in dates:
            validated(
                EventInput, _base_occurrence(payload, day) | exception.payload.get("changes", {})
            )
    row.payload = payload.model_dump(mode="json")
    await db.commit()
    return unpack(row)


@router.delete("/events/{identifier}", status_code=204)
async def delete_event(identifier: str, db: DB, user: Owner) -> Response:
    await lock_owner(db, user)
    row = await owned(db, user, "event", identifier)
    for exception in await records(db, user, "exception"):
        if exception.payload["event_id"] == identifier:
            await db.delete(exception)
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)


def _occurrences(body: EventInput) -> list[Occurrence]:
    return series_occurrences(
        body.start_at,
        body.end_at,
        body.timezone,
        body.recurrence.rule() if body.recurrence else None,
    )


def _base_occurrence(body: EventInput, day: date) -> dict[str, Any]:
    original = next((item for item in _occurrences(body) if item.original_date == day), None)
    if original is None:
        raise fail("not_found", "This date is not an occurrence of the event", 404)
    return {
        **body.model_dump(mode="json"),
        "start_at": original.start.isoformat(),
        "end_at": original.end.isoformat(),
        "recurrence": None,
    }


async def _exception(
    db: AsyncSession, user: User, event_id: str, day: date
) -> PlanningRecord | None:
    result: PlanningRecord | None = await db.scalar(
        select(PlanningRecord)
        .where(
            PlanningRecord.user_id == user.id,
            PlanningRecord.kind == "exception",
            PlanningRecord.payload["event_id"].as_string() == event_id,
            PlanningRecord.payload["occurrence_date"].as_string() == day.isoformat(),
        )
        .with_for_update()
    )
    return result


def _event_item(
    identifier: str,
    body: EventInput,
    original_date: date,
    recurring: bool,
    task: dict[str, Any] | None = None,
) -> dict[str, Any]:
    zone = ZoneInfo(body.timezone)
    return {
        "id": f"local:{identifier}:{original_date.isoformat()}",
        "source": "local",
        "source_id": identifier,
        "title": body.title,
        "notes": body.notes,
        "start_at": body.start_at.astimezone(zone).date().isoformat()
        if body.all_day
        else body.start_at.isoformat(),
        "end_at": body.end_at.astimezone(zone).date().isoformat()
        if body.all_day
        else body.end_at.isoformat(),
        "all_day": body.all_day,
        "timezone": body.timezone,
        "status": "done" if task and task.get("status") == "done" else "confirmed",
        "editable": True,
        "goal_id": task.get("goal_id") if task else None,
        "action_id": None,
        "task_id": body.task_id,
        "occurrence_date": original_date.isoformat(),
        "recurring": recurring,
    }


@router.patch("/events/{identifier}/occurrences/{day}", response_model=AgendaItem)
async def edit_occurrence(
    identifier: str,
    day: date,
    body: OccurrencePatch,
    db: DB,
    user: Owner,
) -> dict[str, Any]:
    await lock_owner(db, user)
    row = await owned(db, user, "event", identifier)
    series = validated(EventInput, row.payload)
    existing = await _exception(db, user, identifier, day)
    payload = _base_occurrence(series, day)
    if existing:
        payload.update(existing.payload.get("changes", {}))
    changes = body.model_dump(mode="json", exclude_unset=True, exclude={"recurrence"})
    current = validated(EventInput, payload | changes)
    await _event_task(db, user, current)
    # Save only explicit field overrides, so future series title/note edits still apply
    # to occurrences whose exceptions change only their timing.
    overrides = dict(existing.payload.get("changes", {})) if existing else {}
    overrides.update(changes)
    exception_payload = {
        "event_id": identifier,
        "occurrence_date": day.isoformat(),
        "cancelled": False,
        "changes": overrides,
    }
    if existing:
        existing.payload = exception_payload
    else:
        create(db, user, "exception", exception_payload)
    await db.commit()
    task = (await owned(db, user, "task", current.task_id)).payload if current.task_id else None
    return _event_item(identifier, current, day, series.recurrence is not None, task)


@router.delete("/events/{identifier}/occurrences/{day}", status_code=204)
async def cancel_occurrence(identifier: str, day: date, db: DB, user: Owner) -> Response:
    await lock_owner(db, user)
    row = await owned(db, user, "event", identifier)
    _base_occurrence(validated(EventInput, row.payload), day)
    exception = await _exception(db, user, identifier, day)
    payload = {
        "event_id": identifier,
        "occurrence_date": day.isoformat(),
        "cancelled": True,
        "changes": exception.payload.get("changes", {}) if exception else {},
    }
    if exception:
        exception.payload = payload
    else:
        create(db, user, "exception", payload)
    await db.commit()
    return Response(status_code=204)


async def _local_events(db: AsyncSession, user: User) -> list[tuple[str, date, EventInput, bool]]:
    rows = list(
        await db.scalars(
            select(PlanningRecord)
            .where(
                PlanningRecord.user_id == user.id,
                PlanningRecord.kind.in_(["event", "exception"]),
            )
            .order_by(PlanningRecord.created_at, PlanningRecord.id)
        )
    )
    exceptions = {
        (row.payload["event_id"], row.payload["occurrence_date"]): row.payload
        for row in rows
        if row.kind == "exception"
    }
    result: list[tuple[str, date, EventInput, bool]] = []
    for row in rows:
        if row.kind != "event":
            continue
        body = validated(EventInput, row.payload)
        for occurrence in _occurrences(body):
            exception = exceptions.get((row.id, occurrence.original_date.isoformat()))
            if exception and exception.get("cancelled"):
                continue
            payload = {
                **body.model_dump(mode="json"),
                "recurrence": None,
                "start_at": occurrence.start.isoformat(),
                "end_at": occurrence.end.isoformat(),
            }
            if exception:
                payload.update(exception.get("changes", {}))
            effective = validated(EventInput, payload)
            result.append(
                (row.id, occurrence.original_date, effective, body.recurrence is not None)
            )
    return result


async def local_event_intervals(
    db: AsyncSession,
    user: User,
    start: datetime,
    end: datetime,
) -> list[tuple[datetime, datetime]]:
    if start.utcoffset() is None or end.utcoffset() is None or end <= start:
        raise fail("invalid_range", "Choose timezone-aware, increasing agenda bounds")
    return [
        (body.start_at, body.end_at)
        for _, _, body, _ in await _local_events(db, user)
        if body.start_at < end and body.end_at > start
    ]


async def local_agenda(
    db: AsyncSession,
    user: User,
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    if not 0 < (end - start).days <= 366:
        raise fail("invalid_range", "Agenda range must span one through 366 days")
    zone = ZoneInfo(user.timezone)
    try:
        first = datetime.combine(start, time.min, zone).astimezone(UTC)
        last = datetime.combine(end, time.min, zone).astimezone(UTC)
    except OverflowError as exc:
        raise fail("invalid_range", "Agenda dates are outside the supported range") from exc
    tasks_by_id = {row.id: row.payload for row in await records(db, user, "task")}
    result: list[dict[str, Any]] = []
    for identifier, day, body, recurring in await _local_events(db, user):
        if body.all_day:
            overlaps = (
                body.start_at.astimezone(ZoneInfo(body.timezone)).date() < end
                and body.end_at.astimezone(ZoneInfo(body.timezone)).date() > start
            )
        else:
            overlaps = body.start_at < last and body.end_at > first
        if overlaps:
            result.append(
                _event_item(identifier, body, day, recurring, tasks_by_id.get(body.task_id or ""))
            )
    for row in await records(db, user, "block"):
        payload = row.payload
        if payload.get("status") == "cancelled":
            continue
        left = datetime.fromisoformat(payload["start_at"]).astimezone(UTC)
        right = datetime.fromisoformat(payload["end_at"]).astimezone(UTC)
        all_day = bool(payload.get("calendar_all_day"))
        calendar_zone = str(payload.get("calendar_timezone") or user.timezone)
        if all_day:
            local_left = str(
                payload.get("calendar_start_date")
                or left.astimezone(ZoneInfo(calendar_zone)).date().isoformat()
            )
            local_right = str(
                payload.get("calendar_end_date")
                or right.astimezone(ZoneInfo(calendar_zone)).date().isoformat()
            )
            overlaps = (
                date.fromisoformat(local_left) < end and date.fromisoformat(local_right) > start
            )
        else:
            local_left, local_right = left.isoformat(), right.isoformat()
            overlaps = left < last and right > first
        if overlaps:
            result.append(
                {
                    "id": f"block:{row.id}",
                    "source": "block",
                    "source_id": row.id,
                    "title": payload.get("title", "Focus"),
                    "notes": payload.get("notes", ""),
                    "start_at": local_left,
                    "end_at": local_right,
                    "all_day": all_day,
                    "timezone": calendar_zone,
                    "status": payload["status"],
                    "editable": payload["status"] in {"proposed", "accepted"}
                    and not payload.get("google_event_id"),
                    "goal_id": payload.get("goal_id"),
                    "action_id": payload.get("action_id"),
                    "task_id": None,
                    "occurrence_date": None,
                    "recurring": False,
                }
            )
    return sorted(result, key=lambda item: (str(item["start_at"]), str(item["id"])))
