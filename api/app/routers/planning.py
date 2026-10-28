"""Authenticated, ownership-scoped goal-to-action core."""

from datetime import UTC, date, datetime, time, timedelta
from math import ceil
from typing import Annotated, Any, Literal
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
    BlockCreate,
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
    PlanChangeInput,
    PlanChangeResponse,
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


async def goal_response(
    db: AsyncSession,
    user: User,
    row: PlanningRecord,
    checkins: list[PlanningRecord] | None = None,
) -> GoalResponse:
    if checkins is None:
        checkins = list(
            (
                await db.scalars(
                    select(PlanningRecord)
                    .where(
                        PlanningRecord.user_id == user.id,
                        PlanningRecord.kind == "checkin",
                        PlanningRecord.payload["goal_id"].as_string() == row.id,
                    )
                    .order_by(PlanningRecord.created_at, PlanningRecord.id)
                )
            ).all()
        )
    return GoalResponse.model_validate(
        {**unpack(row), "checkins": [unpack(check) for check in checkins]}
    )


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
    rows = await records(db, user, "goal")
    if not rows:
        return []
    checks = await db.scalars(
        select(PlanningRecord)
        .where(
            PlanningRecord.user_id == user.id,
            PlanningRecord.kind == "checkin",
            PlanningRecord.payload["goal_id"].as_string().in_([row.id for row in rows]),
        )
        .order_by(PlanningRecord.created_at, PlanningRecord.id)
    )
    by_goal: dict[str, list[PlanningRecord]] = {}
    for check in checks:
        by_goal.setdefault(check.payload["goal_id"], []).append(check)
    return [await goal_response(db, user, row, by_goal.get(row.id, [])) for row in rows]


@router.post("/goals", response_model=GoalResponse, status_code=201)
async def add_goal(body: GoalInput, db: DB, user: Owner) -> GoalResponse:
    await lock_owner(db, user)
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
    action_ids = {action["id"] for action in row.payload["actions"]}
    for block in await records(db, user, "block"):
        if (
            block.payload.get("goal_id") == identifier
            and block.payload["status"] == "proposed"
            and (row.payload["status"] != "active" or block.payload["action_id"] not in action_ids)
        ):
            block.payload = {**block.payload, "status": "cancelled"}
    await db.commit()
    return await goal_response(db, user, row)


@router.delete("/goals/{identifier}", status_code=204)
async def delete_goal(identifier: str, db: DB, user: Owner) -> Response:
    await lock_owner(db, user)
    row = await owned(db, user, "goal", identifier)
    await require_no_active_focus(db, user, goal_id=identifier)
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
    for task in await records(db, user, "task"):
        if task.payload.get("goal_id") == identifier:
            task.payload = {**task.payload, "goal_id": None}
    for change in await records(db, user, "plan_change"):
        if change.payload["before"]["goal_id"] == identifier:
            await db.delete(change)
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
                if (
                    prior.payload["metric_value"] != body.metric_value
                    or prior.payload.get("note", "") != body.note
                ):
                    raise fail("conflict", "Event ID already used for a different check-in", 409)
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
    await lock_owner(db, user)
    row = create(db, user, "busy", body.model_dump(mode="json"))
    await db.commit()
    return unpack(row)


@router.delete("/busy/{identifier}", status_code=204)
async def delete_busy(identifier: str, db: DB, user: Owner) -> Response:
    await lock_owner(db, user)
    await db.delete(await owned(db, user, "busy", identifier))
    await db.commit()
    return Response(status_code=204)


def protect_app_domains(body: BlocklistInput, config: Settings, request: Request) -> None:
    hosts = {
        urlsplit(value).hostname
        for value in (
            config.app_base_url,
            config.google_redirect_uri,
            str(request.base_url),
        )
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
    identifier: str,
    body: BlocklistInput,
    request: Request,
    config: Config,
    db: DB,
    user: Owner,
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


def pending_reservations(
    changes: list[PlanningRecord], timezone: str
) -> tuple[list[Interval], list[Interval]]:
    """Reserve pending destinations without charging an unchanged same-day budget twice."""
    occupied: list[Interval] = []
    capacity: list[Interval] = []
    zone = ZoneInfo(timezone)
    for change in changes:
        after, before = change.payload.get("after"), change.payload["before"]
        if change.payload["status"] != "pending" or after is None:
            continue
        start, end = instant(after["start_at"]), instant(after["end_at"])
        occupied.append(Interval(start, end))
        same_day = (
            start.astimezone(zone).date() == instant(before["start_at"]).astimezone(zone).date()
        )
        extra = (
            max(0, after["planned_minutes"] - before["planned_minutes"])
            if same_day
            else after["planned_minutes"]
        )
        if extra:
            capacity.append(Interval(start, start + timedelta(minutes=extra)))
    return occupied, capacity


@router.post("/plan/draft", response_model=DraftResponse)
async def draft(body: DraftInput, db: DB, user: Owner) -> DraftResponse:
    if body.week_start > date.max - timedelta(days=7):
        raise fail("invalid_week", "Choose a week within the supported calendar range")
    if body.week_start.weekday() != 0:
        raise fail("invalid_week", "Choose a Monday as the week start")
    await lock_owner(db, user)
    today = datetime.now(UTC).astimezone(ZoneInfo(user.timezone)).date()
    if body.week_start + timedelta(days=7) <= today:
        return DraftResponse(
            blocks=[],
            message="This week has ended. Choose this week or a future week.",
            empty_reason="past_week",
        )
    focus_rows = await close_expired(db, user)
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
    # A local skip does not remove a live Google event or its calendar reservation.
    occupied.extend(
        Interval(instant(row.payload["start_at"]), instant(row.payload["end_at"]))
        for row in all_blocks
        if row.payload.get("google_event_id")
        and row.payload["status"] not in ("accepted", "published", "completed", "cancelled")
    )
    window_start = datetime.combine(
        body.week_start, datetime.min.time(), ZoneInfo(user.timezone)
    ).astimezone(UTC)
    occupied.extend(
        Interval(start, end)
        for start, end in await read_calendar_busy(
            db, user.id, window_start, window_start + timedelta(days=8)
        )
    )
    from app.routers.agenda import local_event_intervals

    occupied.extend(
        Interval(start, end)
        for start, end in await local_event_intervals(
            db, user, window_start, window_start + timedelta(days=8)
        )
    )
    pending_slots, pending_capacity = pending_reservations(
        await records(db, user, "plan_change"), user.timezone
    )
    occupied.extend(pending_slots)
    existing.extend(pending_capacity)
    calibration: dict[str, list[tuple[int, int]]] = {}
    for completed_block in all_blocks:
        if completed_block.payload["status"] != "completed":
            continue
        actual = sum(
            float(session.payload.get("actual_minutes", 0))
            for session in focus_rows
            if session.payload.get("ended_at")
            and session.payload.get("time_block_id") == completed_block.id
        )
        calibration.setdefault(completed_block.payload["action_id"], []).append(
            (completed_block.payload["planned_minutes"], int(actual))
        )
    existing_action_days: dict[str, set[date]] = {}
    for reserved in all_blocks:
        if reserved.payload["status"] in ("accepted", "published", "completed"):
            local_day = (
                instant(reserved.payload["start_at"]).astimezone(ZoneInfo(user.timezone)).date()
            )
            existing_action_days.setdefault(reserved.payload["action_id"], set()).add(local_day)
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
        completion_history[key] = (
            completed + int(p["status"] == "completed"),
            samples + 1,
        )
    actions: list[Action] = []
    goal_rows = await records(db, user, "goal")
    for goal in goal_rows:
        p = goal.payload
        if (
            p["status"] != "active"
            or date.fromisoformat(p["start_date"]) >= body.week_start + timedelta(days=7)
            or date.fromisoformat(p["target_date"]) < max(body.week_start, today)
        ):
            continue
        for a in p["actions"]:
            multiplier = duration_multiplier(calibration.get(a["id"], []))
            quota = a["weekly_minutes_target"]
            if a["kind"] == "project" and a["total_minutes_estimate"]:
                spent = sum(
                    float(f.payload.get("actual_minutes", 0))
                    for f in focus_rows
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
        existing_action_days=existing_action_days,
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
    changes = await suggest_plan_changes(db, user, body.week_start, output)
    await db.commit()
    empty_reason: (
        Literal[
            "no_goals", "no_actions", "outside_dates", "already_planned", "no_capacity", "past_week"
        ]
        | None
    ) = None
    if output:
        message = (
            f"{len(output)} proposed {'block' if len(output) == 1 else 'blocks'} ready to review."
        )
    elif changes:
        message = f"{len(changes)} proposed changes ready to review."
    elif not any(goal.payload["status"] == "active" for goal in goal_rows):
        empty_reason = "no_goals"
        message = "Add a goal and an action before drafting your week."
    elif not any(
        goal.payload["status"] == "active"
        and date.fromisoformat(goal.payload["start_date"]) < body.week_start + timedelta(days=7)
        and date.fromisoformat(goal.payload["target_date"]) >= max(body.week_start, today)
        for goal in goal_rows
    ):
        empty_reason = "outside_dates"
        message = "No active goals cover this week. Choose another week or update your goal dates."
    elif not any(action.weekly_minutes >= action.minimum for action in actions):
        already_planned = any(
            row.payload["week_start"] == body.week_start.isoformat()
            and row.payload["status"] in {"accepted", "published", "completed"}
            for row in all_blocks
        )
        empty_reason = "already_planned" if already_planned else "no_actions"
        message = (
            "This week's action time is already planned."
            if already_planned
            else "Set enough weekly time on an action to fit its minimum block length."
        )
    else:
        empty_reason = "no_capacity"
        message = (
            "No blocks fit the remaining availability. "
            "Review events, work hours, and daily capacity."
        )
    return DraftResponse(
        blocks=output,
        changes=changes,
        message=message,
        empty_reason=empty_reason,
        dropped_minutes=result.dropped_minutes,
        capacity_warning=f"{result.dropped_minutes} minutes could not fit. Review availability."
        if result.dropped_minutes
        else None,
    )


async def require_no_active_focus(
    db: AsyncSession,
    user: User,
    *,
    goal_id: str | None = None,
    block_id: str | None = None,
) -> None:
    now = datetime.now(UTC)
    if any(
        not row.payload.get("ended_at")
        and instant(row.payload["ends_at"]) > now
        and (
            (goal_id and row.payload.get("goal_id") == goal_id)
            or (block_id and row.payload.get("time_block_id") == block_id)
        )
        for row in await records(db, user, "focus")
    ):
        raise fail(
            "focus_active",
            "End the linked focus session before changing this plan.",
            409,
        )


async def block_action(
    db: AsyncSession, user: User, goal_id: str, action_id: str
) -> tuple[PlanningRecord, dict[str, Any]]:
    goal = await owned(db, user, "goal", goal_id)
    if goal.payload["status"] != "active":
        raise fail("inactive_goal", "Resume this goal before scheduling its actions.", 409)
    action = next((item for item in goal.payload["actions"] if item["id"] == action_id), None)
    if action is None:
        raise fail("not_found", "Action not found in this goal", 404)
    return goal, action


@router.post("/blocks", response_model=BlockResponse, status_code=201)
async def add_block(body: BlockCreate, db: DB, user: Owner) -> dict[str, Any]:
    """Explicit local scheduling never publishes an external calendar event."""
    await lock_owner(db, user)
    _, action = await block_action(db, user, body.goal_id, body.action_id)
    start, end = body.start_at.astimezone(UTC), body.end_at.astimezone(UTC)
    day = start.astimezone(ZoneInfo(user.timezone)).date()
    payload = {
        "goal_id": body.goal_id,
        "action_id": body.action_id,
        "title": action["title"],
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
        "planned_minutes": int((end - start).total_seconds() / 60),
        "status": body.status,
        "reason": "Scheduled by you within available work hours.",
        "week_start": (day - timedelta(days=day.weekday())).isoformat(),
        "moved_count": 0,
        "proposed_by": "user",
        "notes": body.notes,
    }
    identifier = str(uuid4())
    await validate_placements(db, user, [(identifier, payload)])
    row = PlanningRecord(id=identifier, user_id=user.id, kind="block", payload=payload)
    db.add(row)
    await db.commit()
    return unpack(row)


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
        and (
            row.payload["status"] in ("accepted", "published", "completed")
            or (row.payload.get("google_event_id") and row.payload["status"] != "cancelled")
        )
    ]
    all_blocks = fixed + candidates
    busy = [
        (instant(row.payload["start_at"]), instant(row.payload["end_at"]))
        for row in await records(db, user, "busy")
    ]
    for identifier, payload in candidates:
        start, end = instant(payload["start_at"]), instant(payload["end_at"])
        local_start, local_end = start.astimezone(zone), end.astimezone(zone)
        goal, action = await block_action(db, user, payload["goal_id"], payload["action_id"])
        if start < datetime.now(UTC):
            raise fail("past_time", "Choose a future time for this block.", 409)
        if (
            not goal.payload["start_date"]
            <= local_start.date().isoformat()
            <= goal.payload["target_date"]
        ):
            raise fail("goal_dates", "Choose a date within this goal's dates.", 409)
        seconds = (end - start).total_seconds()
        if (
            seconds % 60
            or not action["min_block_minutes"] <= seconds / 60 <= action["max_block_minutes"]
        ):
            raise fail(
                "block_duration",
                "Use whole minutes within this action's duration limits.",
                409,
            )
        if local_start.date() != local_end.date() or local_start.weekday() not in user.work_days:
            raise fail("outside_hours", "Choose a single working day", 409)
        if local_start.time() < time.fromisoformat(
            user.work_start
        ) or local_end.time() > time.fromisoformat(user.work_end):
            raise fail("outside_hours", "Choose a time inside your work hours", 409)
        if end <= start:
            raise fail("invalid_time", "End must follow start")
        padding = timedelta(minutes=10)
        from app.routers.agenda import local_event_intervals

        local_busy = await local_event_intervals(db, user, start - padding, end + padding)
        calendar_busy = await read_calendar_busy(db, user.id, start - padding, end + padding)
        if any(
            start < right + padding and end > left - padding
            for left, right in busy + calendar_busy + local_busy
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
    for row in selected:
        if row.payload["status"] not in ("proposed", "accepted", "published"):
            raise fail("invalid_state", "Only proposed blocks can be accepted", 409)
    await validate_placements(
        db,
        user,
        [(row.id, row.payload) for row in selected if row.payload["status"] == "proposed"],
    )
    for row in selected:
        if row.payload["status"] == "proposed":
            row.payload = {**row.payload, "status": "accepted"}
    await db.commit()
    return [unpack(row) for row in selected]


@router.patch("/blocks/{identifier}", response_model=BlockResponse)
async def edit_block(identifier: str, body: BlockPatch, db: DB, user: Owner) -> dict[str, Any]:
    await lock_owner(db, user)
    row = await owned(db, user, "block", identifier)
    linked_live = row.payload["status"] == "published" or (
        bool(row.payload.get("google_event_id")) and row.payload["status"] != "cancelled"
    )
    if linked_live and (body.start_at is not None or body.end_at is not None):
        raise fail("published_move", "Move this block in Google Calendar, then sync.", 409)
    if linked_live and body.status == "cancelled":
        raise fail("published_cancel", "Delete this block in Google Calendar, then sync.", 409)
    if row.payload["status"] == "published" and body.status == "accepted":
        raise fail("invalid_state", "This block is already published", 409)
    payload = {**row.payload, **body.model_dump(mode="json", exclude_none=True)}
    start, end = instant(payload["start_at"]), instant(payload["end_at"])
    if body.start_at and body.start_at.tzinfo is None or body.end_at and body.end_at.tzinfo is None:
        raise fail("invalid_time", "Timezone offsets are required")
    if end <= start or (end - start).total_seconds() > 14400:
        raise fail("invalid_time", "Choose a positive duration of at most four hours")
    if body.start_at or body.end_at:
        await require_no_active_focus(db, user, block_id=identifier)
        if row.payload["status"] == "completed":
            raise fail("completed_block", "Completed blocks keep their recorded times.", 409)
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
    elif body.status == "accepted":
        await validate_placements(db, user, [(row.id, payload)])
    row.payload = payload
    await db.commit()
    return unpack(row)


@router.delete("/blocks/{identifier}", status_code=204)
async def delete_block(identifier: str, db: DB, user: Owner) -> Response:
    await lock_owner(db, user)
    row = await owned(db, user, "block", identifier)
    await require_no_active_focus(db, user, block_id=identifier)
    if row.payload["status"] == "published" or (
        row.payload.get("google_event_id") and row.payload["status"] != "cancelled"
    ):
        raise fail("published_delete", "Delete this block in Google Calendar, then sync.", 409)
    for change in await records(db, user, "plan_change"):
        if change.payload["block_id"] == identifier:
            await db.delete(change)
    for focus in await records(db, user, "focus"):
        if focus.payload.get("time_block_id") == identifier:
            focus.payload = {**focus.payload, "time_block_id": None}
    await db.delete(row)
    await db.commit()
    return Response(status_code=204)


async def close_expired(db: AsyncSession, user: User) -> list[PlanningRecord]:
    rows = await records(db, user, "focus")
    now = datetime.now(UTC)
    linked_blocks: set[str] = set()
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
                linked_blocks.add(p["time_block_id"])
    for block_id in sorted(linked_blocks):
        await sync_focus_block(db, user, block_id, rows)
    return rows


async def sync_focus_block(
    db: AsyncSession,
    user: User,
    block_id: str,
    sessions: list[PlanningRecord] | None = None,
) -> None:
    """Reconcile completion from accumulated duration while the owner is locked.

    Short sessions contribute to a longer block. Manual skips/cancellations and
    manual completions remain user decisions. Only completion caused by focus
    can be undone when an offline early-end correction arrives later.
    """
    block = await db.scalar(
        select(PlanningRecord)
        .where(
            PlanningRecord.user_id == user.id,
            PlanningRecord.kind == "block",
            PlanningRecord.id == block_id,
        )
        .with_for_update()
    )
    if block is None or block.payload["status"] not in {"accepted", "published", "completed"}:
        return
    budget = float(block.payload["planned_minutes"])
    if budget <= 0:
        return
    rows = sessions if sessions is not None else await records(db, user, "focus")
    done = sum(
        float(row.payload["actual_minutes"])
        for row in rows
        if row.payload.get("time_block_id") == block_id and row.payload.get("ended_at")
    )
    payload = block.payload
    if done >= budget * 0.9 and payload["status"] in {"accepted", "published"}:
        block.payload = {
            **payload,
            "status": "completed",
            "completed_by_focus": True,
            "focus_previous_status": payload["status"],
        }
    elif (
        done < budget * 0.9
        and payload["status"] == "completed"
        and payload.get("completed_by_focus")
    ):
        previous = payload.get("focus_previous_status")
        if previous not in {"accepted", "published"}:
            previous = "published" if payload.get("google_event_id") else "accepted"
        block.payload = {**payload, "status": previous, "completed_by_focus": False}


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
    event_id = str(body.client_event_id) if body.client_event_id else None
    signature = {
        "ended_at": body.ended_at.isoformat() if body.ended_at else None,
        "self_rating": body.self_rating,
    }
    if event_id:
        for prior in await records(db, user, "focus"):
            prior_events = prior.payload.get("end_events", {})
            if event_id in prior_events:
                if prior.id != identifier or prior_events[event_id] != signature:
                    raise fail(
                        "conflict", "Event ID already used for a different session update", 409
                    )
                return unpack(row)
    events = dict(p.get("end_events", {}))
    if event_id and len(events) >= 100:
        raise fail("too_many_updates", "This session has too many saved updates", 429)
    now = datetime.now(UTC)
    start = instant(p["started_at"])
    if body.ended_at is not None and body.ended_at < start:
        raise fail("invalid_time", "Session end cannot be before its start")
    if body.ended_at is not None and body.ended_at > now + timedelta(seconds=30):
        raise fail("invalid_time", "Session end cannot be in the future")
    previous_end = instant(p["ended_at"]) if p.get("ended_at") else None
    requested_end = body.ended_at or previous_end or now
    end = max(start, min(requested_end, now, instant(p["ends_at"])))
    # Multiple devices and offline retries converge on the earliest end. A later
    # repeated request can never add time to an already ended session.
    if previous_end is None or end < previous_end:
        row.payload = {
            **p,
            "ended_at": end.isoformat(),
            "actual_minutes": max(0, (end - start).total_seconds() / 60),
            "self_rating": body.self_rating
            if body.self_rating is not None
            else p.get("self_rating"),
            "auto_closed": False,
        }
        if p.get("time_block_id"):
            await sync_focus_block(db, user, p["time_block_id"])
    elif body.self_rating is not None:
        row.payload = {**p, "self_rating": body.self_rating}
    if event_id:
        events[event_id] = signature
        row.payload = {**row.payload, "end_events": events}
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
    if from_date is not None and to_date is not None and to_date < from_date:
        raise fail("invalid_range", "End date must be on or after start date")
    await lock_owner(db, user)
    rows = await close_expired(db, user)
    await db.commit()
    timezone = ZoneInfo(user.timezone)

    def midnight(day: date) -> datetime:
        try:
            return datetime.combine(day, time.min, timezone).astimezone(UTC)
        except OverflowError:
            return (
                datetime.min.replace(tzinfo=UTC)
                if day.year == 1
                else datetime.max.replace(tzinfo=UTC)
            )

    left = midnight(from_date) if from_date is not None else None
    right = (
        midnight(to_date + timedelta(days=1))
        if to_date is not None and to_date < date.max
        else None
    )
    selected: list[dict[str, Any]] = []
    total = 0.0
    for row in rows:
        payload = row.payload
        if not payload.get("ended_at"):
            continue
        start = instant(payload["started_at"])
        end = instant(payload["ended_at"])
        overlap_start = max(start, left) if left is not None else start
        overlap_end = min(end, right) if right is not None else end
        overlap = max(0.0, (overlap_end - overlap_start).total_seconds() / 60)
        instant_session = (
            start == end and (left is None or start >= left) and (right is None or start < right)
        )
        if overlap > 0 or instant_session:
            selected.append(payload)
            total += min(float(payload["actual_minutes"]), overlap)
    ratings = [float(payload["self_rating"]) for payload in selected if payload.get("self_rating")]
    return FocusStats(
        completed_sessions=len(selected),
        total_minutes=total,
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
    if week_start.weekday() != 0:
        raise fail("invalid_week", "Week start must be a Monday")
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
    if week_start.weekday() != 0:
        raise fail("invalid_week", "Week start must be a Monday")
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


def block_snapshot(row: PlanningRecord) -> dict[str, Any]:
    return BlockResponse.model_validate(unpack(row)).model_dump(mode="json")


async def save_plan_change(
    db: AsyncSession, user: User, body: PlanChangeInput, block: PlanningRecord
) -> PlanningRecord:
    if block.payload["status"] != "accepted" or block.payload.get("google_event_id"):
        raise fail("local_plan_only", "Only accepted local blocks can be changed here.", 409)
    await require_no_active_focus(db, user, block_id=block.id)
    before = block_snapshot(block)
    after = None
    if body.operation == "move":
        assert body.start_at is not None and body.end_at is not None
        start, end = body.start_at.astimezone(UTC), body.end_at.astimezone(UTC)
        if start == instant(before["start_at"]) and end == instant(before["end_at"]):
            raise fail("unchanged", "Choose a different time for this move.", 409)
        local_date = start.astimezone(ZoneInfo(user.timezone)).date()
        after = {
            **before,
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
            "week_start": (local_date - timedelta(days=local_date.weekday())).isoformat(),
            "planned_minutes": int((end - start).total_seconds() / 60),
            "moved_count": before["moved_count"] + 1,
        }
        await validate_placements(db, user, [(block.id, after)])
    for prior in await records(db, user, "plan_change"):
        if prior.payload["block_id"] == block.id and prior.payload["status"] == "pending":
            if (
                prior.payload["before"] == before
                and prior.payload["after"] == after
                and prior.payload["operation"] == body.operation
            ):
                return prior
            raise fail(
                "pending_change", "Review or dismiss the existing change for this block.", 409
            )
    return create(
        db,
        user,
        "plan_change",
        {
            "block_id": block.id,
            "operation": body.operation,
            "status": "pending",
            "before": before,
            "after": after,
            "reason": body.reason
            or ("Move this block." if after else "Remove this block from the plan."),
            "created_at": stamp(),
            "applied_at": None,
        },
    )


@router.get("/plan/changes", response_model=list[PlanChangeResponse])
async def plan_changes(db: DB, user: Owner, start: date | None = None) -> list[dict[str, Any]]:
    return [
        unpack(row)
        for row in await records(db, user, "plan_change")
        if row.payload["status"] == "pending"
        and (
            start is None
            or row.payload["before"]["week_start"] == start.isoformat()
            or (row.payload["after"] and row.payload["after"]["week_start"] == start.isoformat())
        )
    ]


@router.post("/plan/changes", response_model=PlanChangeResponse, status_code=201)
async def propose_change(body: PlanChangeInput, db: DB, user: Owner) -> dict[str, Any]:
    await lock_owner(db, user)
    block = await owned(db, user, "block", body.block_id)
    change = await save_plan_change(db, user, body, block)
    await db.commit()
    return unpack(change)


@router.post("/plan/changes/{identifier}/accept", response_model=PlanChangeResponse)
async def apply_change(identifier: str, db: DB, user: Owner) -> dict[str, Any]:
    await lock_owner(db, user)
    change = await owned(db, user, "plan_change", identifier)
    if change.payload["status"] == "applied":
        return unpack(change)
    if change.payload["status"] != "pending":
        raise fail("invalid_state", "This change has been dismissed.", 409)
    block = await owned(db, user, "block", change.payload["block_id"])
    await require_no_active_focus(db, user, block_id=block.id)
    if block_snapshot(block) != change.payload["before"]:
        raise fail(
            "stale_change",
            "This block has changed. Dismiss this proposal and review it again.",
            409,
        )
    if block.payload["status"] != "accepted" or block.payload.get("google_event_id"):
        raise fail("local_plan_only", "This block can no longer be changed locally.", 409)
    if change.payload["operation"] == "move":
        after = change.payload["after"]
        await validate_placements(db, user, [(block.id, after)])
        block.payload = {**block.payload, **{k: v for k, v in after.items() if k != "id"}}
    else:
        block.payload = {**block.payload, "status": "cancelled"}
    change.payload = {**change.payload, "status": "applied", "applied_at": stamp()}
    await db.commit()
    return unpack(change)


@router.post("/plan/changes/{identifier}/dismiss", response_model=PlanChangeResponse)
async def dismiss_change(identifier: str, db: DB, user: Owner) -> dict[str, Any]:
    await lock_owner(db, user)
    row = await owned(db, user, "plan_change", identifier)
    if row.payload["status"] == "applied":
        raise fail("invalid_state", "This change has already been applied.", 409)
    row.payload = {**row.payload, "status": "dismissed"}
    await db.commit()
    return unpack(row)


async def suggest_plan_changes(
    db: AsyncSession, user: User, week_start: date, additions: list[BlockResponse]
) -> list[PlanChangeResponse]:
    """Offer repairs to conflicting local reservations; never mutate accepted blocks."""
    from app.routers.agenda import local_event_intervals

    all_blocks = await records(db, user, "block")
    pending = await records(db, user, "plan_change")
    targets = {row.payload["block_id"] for row in pending if row.payload["status"] == "pending"}
    now = datetime.now(UTC)
    zone = ZoneInfo(user.timezone)
    left = datetime.combine(week_start, time.min, zone).astimezone(UTC)
    right = datetime.combine(week_start + timedelta(days=7), time.min, zone).astimezone(UTC)
    busy = [
        Interval(instant(row.payload["start_at"]), instant(row.payload["end_at"]))
        for row in await records(db, user, "busy")
    ]
    busy += [Interval(a, b) for a, b in await read_calendar_busy(db, user.id, left, right)]
    busy += [Interval(a, b) for a, b in await local_event_intervals(db, user, left, right)]
    busy += [Interval(item.start_at, item.end_at) for item in additions]
    pending_slots, pending_capacity = pending_reservations(pending, user.timezone)
    busy.extend(pending_slots)
    for row in all_blocks:
        p = row.payload
        if (
            p["status"] != "accepted"
            or p.get("google_event_id")
            or row.id in targets
            or p["week_start"] != week_start.isoformat()
            or instant(p["start_at"]) <= now
        ):
            continue
        try:
            await require_no_active_focus(db, user, block_id=row.id)
        except HTTPException:
            continue
        try:
            await validate_placements(db, user, [(row.id, p)])
            continue
        except HTTPException as error:
            if error.status_code not in {404, 409}:
                raise
        operation: Literal["move", "remove"] = "remove"
        start_at = end_at = None
        reason = "This block no longer fits the goal or available time."
        try:
            goal, action = await block_action(db, user, p["goal_id"], p["action_id"])
            length = int(p["planned_minutes"])
            fixed = [
                Interval(instant(other.payload["start_at"]), instant(other.payload["end_at"]))
                for other in all_blocks
                if other.id != row.id
                and other.payload["status"] in {"accepted", "published", "completed"}
            ]
            candidate = make_plan(
                week_start,
                user.timezone,
                user.work_days,
                user.work_start,
                user.work_end,
                user.daily_max_focus_minutes,
                user.energy_peak,
                [
                    Action(
                        action["id"],
                        goal.id,
                        action["title"],
                        goal.payload["priority"],
                        length,
                        length,
                        length,
                        length,
                        action["preferred_time_of_day"],
                        action["requires_deep_focus"],
                        False,
                        date.fromisoformat(goal.payload["start_date"]),
                        date.fromisoformat(goal.payload["target_date"]),
                    )
                ],
                busy,
                fixed
                + pending_capacity
                + [Interval(item.start_at, item.end_at) for item in additions],
                multiplier=1,
                earliest=now,
            )
            if candidate.blocks:
                slot = candidate.blocks[0]
                operation, start_at, end_at = "move", slot.start, slot.end
                reason = "Move this block to avoid a conflict and keep its planned time."
        except HTTPException:
            pass
        body = PlanChangeInput(
            block_id=row.id, operation=operation, start_at=start_at, end_at=end_at, reason=reason
        )
        try:
            change = await save_plan_change(db, user, body, row)
        except HTTPException as error:
            if error.status_code in {404, 409}:
                continue
            raise
        if change.payload["after"]:
            after = change.payload["after"]
            busy.append(Interval(instant(after["start_at"]), instant(after["end_at"])))
            _, extra_capacity = pending_reservations([change], user.timezone)
            pending_capacity.extend(extra_capacity)
    return [
        PlanChangeResponse.model_validate(item) for item in await plan_changes(db, user, week_start)
    ]
