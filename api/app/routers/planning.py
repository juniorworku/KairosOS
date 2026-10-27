"""Authenticated, ownership-scoped goal-to-action core."""

from datetime import UTC, date, datetime, time, timedelta
from math import ceil
from typing import Annotated, Any
from urllib.parse import urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.deps import current_user, get_db, get_settings
from app.integrations.calendar import read_calendar_busy
from app.models.auth import User
from app.models.planning import PlanningRecord
from app.schemas.planning import (
    AcceptInput,
    BlocklistInput,
    BlocklistResponse,
    BlockPatch,
    BlockResponse,
    BusyInput,
    BusyResponse,
    CheckinInput,
    CheckinResponse,
    DraftInput,
    DraftResponse,
    FocusEnd,
    FocusHistory,
    FocusInput,
    FocusResponse,
    FocusStats,
    GoalInput,
    GoalResponse,
    ReflectionInput,
    ReflectionResponse,
    SeasonInput,
    SeasonResponse,
    TrajectoryResponse,
)
from app.services.scheduler.plan import Action, Interval, duration_multiplier, make_plan
from app.services.trajectory import compute

router = APIRouter(prefix="/api/v1", tags=["planning"])
DB = Annotated[AsyncSession, Depends(get_db)]
Owner = Annotated[User, Depends(current_user)]
Config = Annotated[Settings, Depends(get_settings)]


def fail(code: str, message: str, status: int = 422) -> HTTPException:
    return HTTPException(status, detail={"code": code, "message": message, "details": {}})


def stamp() -> str:
    return datetime.now(UTC).isoformat()


def instant(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


async def records(db: AsyncSession, user: User, kind: str) -> list[PlanningRecord]:
    return list(
        (
            await db.scalars(
                select(PlanningRecord)
                .where(PlanningRecord.user_id == user.id, PlanningRecord.kind == kind)
                .order_by(PlanningRecord.created_at, PlanningRecord.id)
            )
        ).all()
    )


async def owned(db: AsyncSession, user: User, kind: str, identifier: str) -> PlanningRecord:
    row = await db.scalar(
        select(PlanningRecord)
        .where(
            PlanningRecord.user_id == user.id,
            PlanningRecord.kind == kind,
            PlanningRecord.id == identifier,
        )
        .with_for_update()
    )
    if row is None:
        raise fail("not_found", "Record not found", 404)
    return row


async def lock_owner(db: AsyncSession, user: User) -> None:
    locked = await db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked is None or locked.disabled_at is not None:
        raise fail("unauthorized", "Your session ended. Sign in again.", 401)


def create(db: AsyncSession, user: User, kind: str, payload: dict[str, Any]) -> PlanningRecord:
    row = PlanningRecord(id=str(uuid4()), user_id=user.id, kind=kind, payload=payload)
    db.add(row)
    return row


def unpack(row: PlanningRecord) -> dict[str, Any]:
    return {**row.payload, "id": row.id}


async def goal_response(db: AsyncSession, user: User, row: PlanningRecord) -> GoalResponse:
    checks = [
        unpack(check)
        for check in await records(db, user, "checkin")
        if check.payload["goal_id"] == row.id
    ]
    return GoalResponse.model_validate({**unpack(row), "checkins": checks})


async def validate_goal(
    db: AsyncSession, user: User, body: GoalInput, old: PlanningRecord | None = None
) -> dict[str, Any]:
    if body.season_id:
        await owned(db, user, "season", body.season_id)
    payload = body.model_dump(mode="json")
    allowed = {a["id"] for a in old.payload["actions"]} if old else set()
    assigned: set[str] = set()
    for action in payload["actions"]:
        if action["id"] and action["id"] not in allowed:
            raise fail("invalid_action", "Action does not belong to this goal")
        action["id"] = action["id"] or str(uuid4())
        if action["id"] in assigned:
            raise fail("invalid_action", "Action IDs must be unique")
        assigned.add(action["id"])
    return payload


@router.get("/seasons", response_model=list[SeasonResponse])
async def seasons(db: DB, user: Owner) -> list[dict[str, Any]]:
    return [unpack(row) for row in await records(db, user, "season")]


@router.post("/seasons", response_model=SeasonResponse, status_code=201)
async def add_season(body: SeasonInput, db: DB, user: Owner) -> dict[str, Any]:
    row = create(db, user, "season", body.model_dump(mode="json"))
    await db.commit()
    return unpack(row)


@router.get("/goals", response_model=list[GoalResponse])
async def goals(db: DB, user: Owner) -> list[GoalResponse]:
    return [await goal_response(db, user, row) for row in await records(db, user, "goal")]


@router.post("/goals", response_model=GoalResponse, status_code=201)
async def add_goal(body: GoalInput, db: DB, user: Owner) -> GoalResponse:
    row = create(db, user, "goal", await validate_goal(db, user, body))
    await db.commit()
    return await goal_response(db, user, row)


@router.get("/goals/{identifier}", response_model=GoalResponse)
async def get_goal(identifier: str, db: DB, user: Owner) -> GoalResponse:
    return await goal_response(db, user, await owned(db, user, "goal", identifier))


@router.patch("/goals/{identifier}", response_model=GoalResponse)
async def edit_goal(identifier: str, body: GoalInput, db: DB, user: Owner) -> GoalResponse:
    await lock_owner(db, user)
    row = await owned(db, user, "goal", identifier)
    row.payload = await validate_goal(db, user, body, row)
    await db.commit()
    return await goal_response(db, user, row)


@router.delete("/goals/{identifier}", status_code=204)
async def delete_goal(identifier: str, db: DB, user: Owner) -> Response:
    await lock_owner(db, user)
    row = await owned(db, user, "goal", identifier)
    blocks = await records(db, user, "block")
    if any(
        block.payload.get("goal_id") == identifier
        and (
            block.payload["status"] == "published"
            or (block.payload.get("google_event_id") and block.payload["status"] != "cancelled")
        )
        for block in blocks
    ):
        raise fail(
            "published_blocks",
            "Delete this goal's blocks in Google Calendar, then sync before deleting the goal.",
            409,
        )
    for kind in ("checkin", "block", "focus"):
        for child in await records(db, user, kind):
            if child.payload.get("goal_id") == identifier:
                await db.delete(child)
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)


@router.post("/goals/{identifier}/checkins", response_model=CheckinResponse, status_code=201)
async def checkin(identifier: str, body: CheckinInput, db: DB, user: Owner) -> dict[str, Any]:
    await lock_owner(db, user)
    await owned(db, user, "goal", identifier)
    if body.client_event_id:
        for prior in await records(db, user, "checkin"):
            if prior.payload.get("client_event_id") == str(body.client_event_id):
                if prior.payload["goal_id"] != identifier:
                    raise fail("conflict", "Event ID already used for another goal", 409)
                return unpack(prior)
    row = create(
        db,
        user,
        "checkin",
        {**body.model_dump(mode="json"), "goal_id": identifier, "recorded_at": stamp()},
    )
    await db.commit()
    return unpack(row)


@router.get("/busy", response_model=list[BusyResponse])
async def busy(db: DB, user: Owner) -> list[dict[str, Any]]:
    return [unpack(row) for row in await records(db, user, "busy")]


@router.post("/busy", response_model=BusyResponse, status_code=201)
async def add_busy(body: BusyInput, db: DB, user: Owner) -> dict[str, Any]:
    row = create(db, user, "busy", body.model_dump(mode="json"))
    await db.commit()
    return unpack(row)


@router.delete("/busy/{identifier}", status_code=204)
async def delete_busy(identifier: str, db: DB, user: Owner) -> Response:
    await db.delete(await owned(db, user, "busy", identifier))
    await db.commit()
    return Response(status_code=204)


def protect_app_domains(body: BlocklistInput, config: Settings, request: Request) -> None:
    hosts = {
        urlsplit(value).hostname
        for value in (config.app_base_url, config.google_redirect_uri, str(request.base_url))
    }
    for domain in body.domains:
        if any(host and (host == domain or host.endswith("." + domain)) for host in hosts):
            raise fail("protected_domain", "Kairos application domains cannot be blocked")


@router.get("/blocklists", response_model=list[BlocklistResponse])
async def blocklists(db: DB, user: Owner) -> list[dict[str, Any]]:
    return [unpack(row) for row in await records(db, user, "blocklist")]


@router.post("/blocklists", response_model=BlocklistResponse, status_code=201)
async def add_blocklist(
    body: BlocklistInput, request: Request, config: Config, db: DB, user: Owner
) -> dict[str, Any]:
    protect_app_domains(body, config, request)
    await lock_owner(db, user)
    others = await records(db, user, "blocklist")
    payload = body.model_dump()
    if not others:
        payload["is_default"] = True
    if payload["is_default"]:
        for row in others:
            row.payload = {**row.payload, "is_default": False}
    created = create(db, user, "blocklist", payload)
    await db.commit()
    return unpack(created)


@router.patch("/blocklists/{identifier}", response_model=BlocklistResponse)
async def edit_blocklist(
    identifier: str, body: BlocklistInput, request: Request, config: Config, db: DB, user: Owner
) -> dict[str, Any]:
    protect_app_domains(body, config, request)
    await lock_owner(db, user)
    row = await owned(db, user, "blocklist", identifier)
    if body.is_default:
        for other in await records(db, user, "blocklist"):
            if other.id != row.id:
                other.payload = {**other.payload, "is_default": False}
    row.payload = body.model_dump()
    await db.commit()
    return unpack(row)


@router.delete("/blocklists/{identifier}", status_code=204)
async def delete_blocklist(identifier: str, db: DB, user: Owner) -> Response:
    await lock_owner(db, user)
    row = await owned(db, user, "blocklist", identifier)
    if row.payload.get("is_default"):
        next_default = next(
            (other for other in await records(db, user, "blocklist") if other.id != identifier),
            None,
        )
        if next_default:
            next_default.payload = {**next_default.payload, "is_default": True}
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)


@router.get("/plan/week", response_model=list[BlockResponse])
async def week(db: DB, user: Owner, start: date) -> list[dict[str, Any]]:
    return [
        unpack(row)
        for row in await records(db, user, "block")
        if row.payload["week_start"] == start.isoformat()
    ]


@router.post("/plan/draft", response_model=DraftResponse)
async def draft(body: DraftInput, db: DB, user: Owner) -> DraftResponse:
    if body.week_start.weekday() != 0:
        raise fail("invalid_week", "Choose a Monday as the week start")
    await lock_owner(db, user)
    all_blocks = await records(db, user, "block")
    for row in all_blocks:
        if (
            row.payload["week_start"] == body.week_start.isoformat()
            and row.payload["status"] == "proposed"
        ):
            await db.delete(row)
    existing = [
        Interval(instant(row.payload["start_at"]), instant(row.payload["end_at"]))
        for row in all_blocks
        if row.payload["status"] in ("accepted", "published", "completed")
    ]
    occupied = [
        Interval(instant(row.payload["start_at"]), instant(row.payload["end_at"]))
        for row in await records(db, user, "busy")
    ]
    window_start = datetime.combine(
        body.week_start, datetime.min.time(), ZoneInfo(user.timezone)
    ).astimezone(UTC)
    occupied.extend(
        Interval(start, end)
        for start, end in await read_calendar_busy(
            db, user.id, window_start, window_start + timedelta(days=8)
        )
    )
    history = [
        (f.payload["planned_minutes"], int(f.payload["actual_minutes"]))
        for f in await records(db, user, "focus")
        if f.payload.get("ended_at")
    ]
    multiplier = duration_multiplier(history)
    completion_history: dict[tuple[int, int], tuple[int, int]] = {}
    now = datetime.now(UTC)
    for past in all_blocks:
        p = past.payload
        if (
            p["status"] not in ("accepted", "published", "completed", "skipped")
            or instant(p["end_at"]) > now
        ):
            continue
        local = instant(p["start_at"]).astimezone(ZoneInfo(user.timezone))
        key = (local.weekday(), local.hour)
        completed, samples = completion_history.get(key, (0, 0))
        completion_history[key] = (completed + int(p["status"] == "completed"), samples + 1)
    actions: list[Action] = []
    for goal in await records(db, user, "goal"):
        p = goal.payload
        if p["status"] != "active":
            continue
        for a in p["actions"]:
            quota = a["weekly_minutes_target"]
            if a["kind"] == "project" and a["total_minutes_estimate"]:
                spent = sum(
                    float(f.payload.get("actual_minutes", 0))
                    for f in await records(db, user, "focus")
                    if f.payload.get("action_id") == a["id"]
                )
                weeks_left = max(
                    1, (date.fromisoformat(p["target_date"]) - body.week_start).days / 7
                )
                quota = int(max(0, a["total_minutes_estimate"] - spent) / weeks_left)
            already = sum(
                int(b.payload["planned_minutes"])
                for b in all_blocks
                if b.payload["week_start"] == body.week_start.isoformat()
                and b.payload["action_id"] == a["id"]
                and b.payload["status"] in ("accepted", "published", "completed")
            )
            actions.append(
                Action(
                    a["id"],
                    goal.id,
                    a["title"],
                    p["priority"],
                    max(0, ceil(quota * multiplier) - already),
                    a["preferred_block_minutes"],
                    a["min_block_minutes"],
                    a["max_block_minutes"],
                    a["preferred_time_of_day"],
                    a["requires_deep_focus"],
                    a["kind"] == "habit",
                    date.fromisoformat(p["start_date"]),
                    date.fromisoformat(p["target_date"]),
                )
            )
    result = make_plan(
        body.week_start,
        user.timezone,
        user.work_days,
        user.work_start,
        user.work_end,
        user.daily_max_focus_minutes,
        user.energy_peak,
        actions,
        occupied,
        existing,
        multiplier=1,
        earliest=datetime.now(UTC),
        completion_history=completion_history,
    )
    output: list[BlockResponse] = []
    for block in result.blocks:
        row = create(
            db,
            user,
            "block",
            {
                "action_id": block.action_id,
                "goal_id": block.goal_id,
                "title": block.title,
                "start_at": block.start.isoformat(),
                "end_at": block.end.isoformat(),
                "planned_minutes": int((block.end - block.start).total_seconds() / 60),
                "status": "proposed",
                "reason": block.reason,
                "week_start": body.week_start.isoformat(),
                "moved_count": 0,
            },
        )
        output.append(BlockResponse.model_validate(unpack(row)))
    await db.commit()
    return DraftResponse(
        blocks=output,
        dropped_minutes=result.dropped_minutes,
        capacity_warning=f"{result.dropped_minutes} minutes could not fit. Review availability."
        if result.dropped_minutes
        else None,
    )


async def validate_placements(
    db: AsyncSession, user: User, candidates: list[tuple[str, dict[str, Any]]]
) -> None:
    """Recheck edits and acceptance against current availability under the owner lock."""
    zone = ZoneInfo(user.timezone)
    identifiers = {identifier for identifier, _ in candidates}
    fixed = [
        (row.id, row.payload)
        for row in await records(db, user, "block")
        if row.id not in identifiers
        and row.payload["status"] in ("accepted", "published", "completed")
    ]
    all_blocks = fixed + candidates
    busy = [
        (instant(row.payload["start_at"]), instant(row.payload["end_at"]))
        for row in await records(db, user, "busy")
    ]
    for identifier, payload in candidates:
        start, end = instant(payload["start_at"]), instant(payload["end_at"])
        local_start, local_end = start.astimezone(zone), end.astimezone(zone)
        if local_start.date() != local_end.date() or local_start.weekday() not in user.work_days:
            raise fail("outside_hours", "Choose a single working day", 409)
        if local_start.time() < time.fromisoformat(
            user.work_start
        ) or local_end.time() > time.fromisoformat(user.work_end):
            raise fail("outside_hours", "Choose a time inside your work hours", 409)
        if end <= start:
            raise fail("invalid_time", "End must follow start")
        padding = timedelta(minutes=10)
        calendar_busy = await read_calendar_busy(db, user.id, start - padding, end + padding)
        if any(
            start < right + padding and end > left - padding for left, right in busy + calendar_busy
        ):
            raise fail("busy_conflict", "This time overlaps busy time or its buffer", 409)
        if any(
            other_id != identifier
            and start < instant(other["end_at"])
            and end > instant(other["start_at"])
            for other_id, other in all_blocks
        ):
            raise fail("conflict", "This time overlaps another block", 409)
        minutes = sum(
            float(other["planned_minutes"])
            for _, other in all_blocks
            if instant(other["start_at"]).astimezone(zone).date() == local_start.date()
        )
        if minutes > user.daily_max_focus_minutes:
            raise fail("daily_capacity", "This day exceeds your focus capacity", 409)


@router.post("/plan/accept", response_model=list[BlockResponse])
async def accept(body: AcceptInput, db: DB, user: Owner) -> list[dict[str, Any]]:
    await lock_owner(db, user)
    selected = [
        await owned(db, user, "block", identifier) for identifier in dict.fromkeys(body.block_ids)
    ]
    await validate_placements(db, user, [(row.id, row.payload) for row in selected])
    for row in selected:
        if row.payload["status"] not in ("proposed", "accepted", "published"):
            raise fail("invalid_state", "Only proposed blocks can be accepted", 409)
        if row.payload["status"] == "proposed":
            row.payload = {**row.payload, "status": "accepted"}
    await db.commit()
    return [unpack(row) for row in selected]


@router.patch("/blocks/{identifier}", response_model=BlockResponse)
async def edit_block(identifier: str, body: BlockPatch, db: DB, user: Owner) -> dict[str, Any]:
    await lock_owner(db, user)
    row = await owned(db, user, "block", identifier)
    if row.payload["status"] == "published" and body.status == "accepted":
        raise fail("invalid_state", "This block is already published", 409)
    payload = {**row.payload, **body.model_dump(mode="json", exclude_none=True)}
    start, end = instant(payload["start_at"]), instant(payload["end_at"])
    if body.start_at and body.start_at.tzinfo is None or body.end_at and body.end_at.tzinfo is None:
        raise fail("invalid_time", "Timezone offsets are required")
    if end <= start or (end - start).total_seconds() > 14400:
        raise fail("invalid_time", "Choose a positive duration of at most four hours")
    if body.start_at or body.end_at:
        payload["moved_count"] = payload.get("moved_count", 0) + 1
        payload["planned_minutes"] = int((end - start).total_seconds() / 60)
        local_date = start.astimezone(ZoneInfo(user.timezone)).date()
        payload["week_start"] = (local_date - timedelta(days=local_date.weekday())).isoformat()
        await validate_placements(db, user, [(row.id, payload)])
        for other in await records(db, user, "block"):
            if (
                other.id != row.id
                and other.payload["status"] in ("accepted", "published")
                and start < instant(other.payload["end_at"])
                and end > instant(other.payload["start_at"])
            ):
                raise fail("conflict", "This move overlaps an accepted block", 409)
        if row.payload["status"] == "published":
            raise fail(
                "published_move",
                "Move this published block in Google Calendar",
                409,
            )
    elif body.status == "accepted":
        await validate_placements(db, user, [(row.id, payload)])
    row.payload = payload
    await db.commit()
    return unpack(row)


@router.delete("/blocks/{identifier}", status_code=204)
async def delete_block(identifier: str, db: DB, user: Owner) -> Response:
    await lock_owner(db, user)
    row = await owned(db, user, "block", identifier)
    if row.payload["status"] == "published":
        raise fail("published_delete", "Delete this block in Google Calendar", 409)
    for focus in await records(db, user, "focus"):
        if focus.payload.get("time_block_id") == identifier:
            focus.payload = {**focus.payload, "time_block_id": None}
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)


async def close_expired(db: AsyncSession, user: User) -> list[PlanningRecord]:
    rows = await records(db, user, "focus")
    now = datetime.now(UTC)
    for row in rows:
        p = row.payload
        if not p.get("ended_at") and instant(p["ends_at"]) <= now:
            row.payload = {
                **p,
                "ended_at": p["ends_at"],
                "actual_minutes": float(p["planned_minutes"]),
                "auto_closed": True,
            }
            if p.get("time_block_id"):
                block = await owned(db, user, "block", p["time_block_id"])
                block.payload = {**block.payload, "status": "completed"}
    return rows


@router.post("/focus/start", response_model=FocusResponse, status_code=201)
async def start_focus(body: FocusInput, db: DB, user: Owner) -> dict[str, Any]:
    await lock_owner(db, user)
    if any(not row.payload.get("ended_at") for row in await close_expired(db, user)):
        raise fail("focus_active", "End your active focus session first", 409)
    action_id, goal_id = body.action_id, None
    title = "Focus"
    selected_list: PlanningRecord | None = None
    if body.blocklist_id:
        selected_list = await owned(db, user, "blocklist", body.blocklist_id)
    else:
        for candidate in await records(db, user, "blocklist"):
            if candidate.payload.get("is_default"):
                selected_list = candidate
                break
    if body.time_block_id:
        block = await owned(db, user, "block", body.time_block_id)
        if block.payload["status"] not in ("accepted", "published"):
            raise fail("invalid_block", "Accept this block before starting focus", 409)
        action_id, goal_id = block.payload["action_id"], block.payload["goal_id"]
        title = block.payload["title"]
    elif action_id:
        for goal in await records(db, user, "goal"):
            if any(a["id"] == action_id for a in goal.payload["actions"]):
                goal_id = goal.id
                title = next(a["title"] for a in goal.payload["actions"] if a["id"] == action_id)
                break
        if goal_id is None:
            raise fail("not_found", "Action not found", 404)
    now = datetime.now(UTC)
    row = create(
        db,
        user,
        "focus",
        {
            "time_block_id": body.time_block_id,
            "action_id": action_id,
            "goal_id": goal_id,
            "started_at": now.isoformat(),
            "ends_at": (now + timedelta(minutes=body.planned_minutes)).isoformat(),
            "ended_at": None,
            "planned_minutes": body.planned_minutes,
            "actual_minutes": 0,
            "self_rating": None,
            "blocklist_id": selected_list.id if selected_list else None,
            "blocklist_snapshot": list(selected_list.payload["domains"]) if selected_list else [],
            "title": title,
        },
    )
    await db.commit()
    return unpack(row)


@router.post("/focus/{identifier}/end", response_model=FocusResponse)
async def end_focus(identifier: str, body: FocusEnd, db: DB, user: Owner) -> dict[str, Any]:
    await lock_owner(db, user)
    row = await owned(db, user, "focus", identifier)
    p = row.payload
    if not p.get("ended_at") or (p.get("auto_closed") and body.ended_at is not None):
        requested_end = body.ended_at or datetime.now(UTC)
        if requested_end.tzinfo is None:
            raise fail("invalid_time", "Timezone offset is required")
        end = max(
            instant(p["started_at"]), min(requested_end, datetime.now(UTC), instant(p["ends_at"]))
        )
        row.payload = {
            **p,
            "ended_at": end.isoformat(),
            "actual_minutes": max(0, (end - instant(p["started_at"])).total_seconds() / 60),
            "self_rating": body.self_rating,
            "auto_closed": False,
        }
        if p.get("time_block_id") and row.payload["actual_minutes"] >= p["planned_minutes"] * 0.9:
            block = await owned(db, user, "block", p["time_block_id"])
            block.payload = {**block.payload, "status": "completed"}
        elif p.get("time_block_id") and p.get("auto_closed"):
            block = await owned(db, user, "block", p["time_block_id"])
            block.payload = {
                **block.payload,
                "status": "published" if block.payload.get("google_event_id") else "accepted",
            }
    elif body.self_rating is not None:
        row.payload = {**p, "self_rating": body.self_rating}
    await db.commit()
    return unpack(row)


@router.get("/focus/active", response_model=FocusResponse | None)
async def active_focus(db: DB, user: Owner) -> dict[str, Any] | None:
    await lock_owner(db, user)
    rows = await close_expired(db, user)
    await db.commit()
    return next((unpack(row) for row in rows if not row.payload.get("ended_at")), None)


@router.get("/focus/stats", response_model=FocusStats)
async def focus_stats(
    db: DB,
    user: Owner,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> FocusStats:
    await lock_owner(db, user)
    rows = await close_expired(db, user)
    await db.commit()
    selected = [
        row.payload
        for row in rows
        if row.payload.get("ended_at")
        and (from_date is None or instant(row.payload["started_at"]).date() >= from_date)
        and (to_date is None or instant(row.payload["started_at"]).date() <= to_date)
    ]
    ratings = [float(p["self_rating"]) for p in selected if p.get("self_rating")]
    return FocusStats(
        completed_sessions=len(selected),
        total_minutes=sum(float(p["actual_minutes"]) for p in selected),
        average_rating=sum(ratings) / len(ratings) if ratings else None,
    )


@router.get("/focus/sessions", response_model=FocusHistory)
async def focus_history(
    db: DB, user: Owner, limit: int = Query(default=50, ge=1, le=200), cursor: str | None = None
) -> FocusHistory:
    await lock_owner(db, user)
    rows = list(reversed(await close_expired(db, user)))
    await db.commit()
    if cursor:
        index = next((i for i, row in enumerate(rows) if row.id == cursor), None)
        if index is None:
            raise fail("invalid_cursor", "Session cursor not found")
        rows = rows[index + 1 :]
    selected = rows[:limit]
    return FocusHistory(
        items=[FocusResponse.model_validate(unpack(row)) for row in selected],
        next_cursor=selected[-1].id if len(rows) > limit else None,
    )


@router.get("/trajectory", response_model=list[TrajectoryResponse])
async def trajectory(db: DB, user: Owner) -> list[TrajectoryResponse]:
    await lock_owner(db, user)
    await close_expired(db, user)
    await db.commit()
    now = datetime.now(UTC)
    today = now.astimezone(ZoneInfo(user.timezone)).date()
    checks = await records(db, user, "checkin")
    sessions = await records(db, user, "focus")
    blocks = await records(db, user, "block")
    output: list[TrajectoryResponse] = []
    for goal in await records(db, user, "goal"):
        p = goal.payload
        latest = next(
            (
                c.payload["metric_value"]
                for c in reversed(checks)
                if c.payload["goal_id"] == goal.id
            ),
            None,
        )
        done = sum(
            float(f.payload["actual_minutes"])
            for f in sessions
            if f.payload.get("goal_id") == goal.id
        )
        planned = sum(
            float(b.payload["planned_minutes"])
            for b in blocks
            if b.payload["goal_id"] == goal.id
            and b.payload["status"] in ("accepted", "published", "completed", "skipped")
            and instant(b.payload["end_at"]) <= now
        )
        output.append(
            TrajectoryResponse.model_validate(
                compute(
                    goal.id,
                    date.fromisoformat(p["start_date"]),
                    date.fromisoformat(p["target_date"]),
                    p["metric_start"],
                    p["metric_target"],
                    latest,
                    done,
                    planned,
                    today,
                )
            )
        )
    return output


@router.get("/reflection/{week_start}", response_model=ReflectionResponse | None)
async def get_reflection(week_start: date, db: DB, user: Owner) -> dict[str, Any] | None:
    return next(
        (
            unpack(row)
            for row in await records(db, user, "reflection")
            if row.payload["week_start"] == week_start.isoformat()
        ),
        None,
    )


@router.post("/reflection/{week_start}", response_model=ReflectionResponse)
async def save_reflection(
    week_start: date, body: ReflectionInput, db: DB, user: Owner
) -> dict[str, Any]:
    await lock_owner(db, user)
    payload = {**body.model_dump(), "week_start": week_start.isoformat()}
    rows = [
        row
        for row in await records(db, user, "reflection")
        if row.payload["week_start"] == week_start.isoformat()
    ]
    row = rows[0] if rows else create(db, user, "reflection", payload)
    row.payload = payload
    await db.commit()
    return unpack(row)
