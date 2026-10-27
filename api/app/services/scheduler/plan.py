"""Deterministic, I/O-free weekly planning in a user's local timezone."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from math import ceil
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class Action:
    id: str
    goal_id: str
    title: str
    priority: int
    weekly_minutes: int
    preferred: int = 60
    minimum: int = 30
    maximum: int = 120
    preference: str = "any"
    deep: bool = True
    habit: bool = True
    starts_on: date | None = None
    ends_on: date | None = None


@dataclass(frozen=True)
class Block:
    action_id: str
    goal_id: str
    title: str
    start: datetime
    end: datetime
    reason: str


@dataclass(frozen=True)
class Draft:
    blocks: list[Block]
    dropped_minutes: int


def duration_multiplier(history: list[tuple[int, int]]) -> float:
    ratios = sorted(actual / planned for planned, actual in history if planned > 0 and actual > 0)
    return 1.3 if len(ratios) < 5 else max(1.0, min(2.0, ratios[len(ratios) // 2]))


def free_slots(
    week: date,
    timezone: str,
    work_days: list[int],
    work_start: str,
    work_end: str,
    busy: list[Interval],
    buffer: int = 10,
) -> list[Interval]:
    zone = ZoneInfo(timezone)
    result: list[Interval] = []
    padding = timedelta(minutes=buffer)
    for offset in range(7):
        day = week + timedelta(days=offset)
        if day.weekday() not in work_days:
            continue
        start = datetime.combine(day, time.fromisoformat(work_start), zone).astimezone(UTC)
        end = datetime.combine(day, time.fromisoformat(work_end), zone).astimezone(UTC)
        if end <= start:
            continue
        intervals = [Interval(start, end)]
        for occupied in sorted(busy, key=lambda item: item.start):
            next_intervals: list[Interval] = []
            left, right = occupied.start - padding, occupied.end + padding
            for slot in intervals:
                if right <= slot.start or left >= slot.end:
                    next_intervals.append(slot)
                else:
                    if left > slot.start:
                        next_intervals.append(Interval(slot.start, left))
                    if right < slot.end:
                        next_intervals.append(Interval(right, slot.end))
            intervals = next_intervals
        result.extend(intervals)
    return result


def make_plan(
    week: date,
    timezone: str,
    work_days: list[int],
    work_start: str,
    work_end: str,
    daily_cap: int,
    energy_peak: str,
    actions: list[Action],
    busy: list[Interval],
    existing: list[Interval],
    blackouts: list[Interval] | None = None,
    multiplier: float = 1.3,
    earliest: datetime | None = None,
    completion_history: dict[tuple[int, int], tuple[int, int]] | None = None,
) -> Draft:
    zone = ZoneInfo(timezone)
    slots = free_slots(week, timezone, work_days, work_start, work_end, busy + (blackouts or []))
    if earliest is not None:
        slots = [
            Interval(max(slot.start, earliest), slot.end) for slot in slots if slot.end > earliest
        ]
    # Accepted blocks consume capacity and slots without adding event buffers.
    for accepted in existing:
        split: list[Interval] = []
        for slot in slots:
            if accepted.end <= slot.start or accepted.start >= slot.end:
                split.append(slot)
            else:
                if accepted.start > slot.start:
                    split.append(Interval(slot.start, accepted.start))
                if accepted.end < slot.end:
                    split.append(Interval(accepted.end, slot.end))
        slots = split
    used: dict[date, int] = {}
    for block in existing:
        day = block.start.astimezone(zone).date()
        used[day] = used.get(day, 0) + int((block.end - block.start).total_seconds() / 60)
    blocks: list[Block] = []
    dropped = 0
    for action in sorted(
        actions, key=lambda a: (-a.priority, -a.weekly_minutes, -int(a.deep), a.id)
    ):
        need = int(ceil(action.weekly_minutes * multiplier))
        spread: set[date] = set()
        while need >= action.minimum:
            candidates: list[tuple[float, datetime, int, int, date]] = []
            for index, slot in enumerate(slots):
                local = slot.start.astimezone(zone)
                minute = (
                    (local.minute + 29 + int(bool(local.second or local.microsecond))) // 30 * 30
                )
                aligned = local.replace(minute=0, second=0, microsecond=0) + timedelta(
                    minutes=minute
                )
                aligned = aligned.replace(fold=local.fold)
                start = aligned.astimezone(UTC)
                if start < slot.start:
                    continue
                day = aligned.date()
                if (action.starts_on and day < action.starts_on) or (
                    action.ends_on and day > action.ends_on
                ):
                    continue
                available = int((slot.end - start).total_seconds() // 60)
                length = min(
                    action.preferred,
                    action.maximum,
                    available,
                    need,
                    max(0, daily_cap - used.get(day, 0)),
                )
                if length < action.minimum:
                    continue
                period = (
                    "morning"
                    if aligned.hour < 12
                    else "afternoon"
                    if aligned.hour < 17
                    else "evening"
                )
                preference = energy_peak if action.preference == "any" else action.preference
                score = float((4 if period == preference else 0) * (2 if action.deep else 1))
                completed, samples = (completion_history or {}).get(
                    (aligned.weekday(), aligned.hour), (0, 0)
                )
                if samples >= 10:
                    score += 4 * (completed / samples - 0.5)
                score += 3 if action.habit and day not in spread else 0
                if 0 < available - length < action.minimum:
                    score -= 2
                candidates.append((score, start, index, length, day))
            if not candidates:
                break
            _, start, index, length, day = min(candidates, key=lambda x: (-x[0], x[1], x[2]))
            end = start + timedelta(minutes=length)
            slot = slots.pop(index)
            if slot.start < start:
                slots.append(Interval(slot.start, start))
            if end < slot.end:
                slots.append(Interval(end, slot.end))
            slots.sort(key=lambda x: x.start)
            used[day] = used.get(day, 0) + length
            spread.add(day)
            need -= length
            blocks.append(
                Block(
                    action.id,
                    action.goal_id,
                    action.title,
                    start,
                    end,
                    "Fits work hours and daily capacity, with priority and focus time considered.",
                )
            )
        dropped += need
    return Draft(sorted(blocks, key=lambda b: (b.start, b.action_id)), dropped)
