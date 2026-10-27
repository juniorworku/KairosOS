"""Deterministic, I/O-free weekly planning in a user's local timezone."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from math import ceil
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("Intervals require timezone-aware, increasing timestamps")
        start, end = self.start.astimezone(UTC), self.end.astimezone(UTC)
        if end <= start:
            raise ValueError("Intervals require timezone-aware, increasing timestamps")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)


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

    def __post_init__(self) -> None:
        if not 0 < self.minimum <= self.preferred <= self.maximum or self.weekly_minutes < 0:
            raise ValueError("Action duration bounds and weekly quota must be valid")


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


def aligned_starts(slot: Interval, zone: ZoneInfo) -> Iterator[datetime]:
    """Walk real instants, preserving both occurrences of a repeated DST hour."""
    start = slot.start.astimezone(UTC)
    local = start.astimezone(zone)
    delta = (-local.minute) % 30
    if not delta and (local.second or local.microsecond):
        delta = 30
    candidate = start.replace(second=0, microsecond=0) + timedelta(minutes=delta)
    while candidate < slot.end:
        if candidate >= slot.start and candidate.astimezone(zone).minute in (0, 30):
            yield candidate
        candidate += timedelta(minutes=30)


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
    existing_action_days: dict[str, set[date]] | None = None,
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
        spread = set((existing_action_days or {}).get(action.id, set()))
        while need >= action.minimum:
            candidates: list[tuple[float, datetime, int, int, date]] = []
            for index, slot in enumerate(slots):
                first_start = next(aligned_starts(slot, zone), None)
                if first_start is None:
                    continue
                for start in aligned_starts(slot, zone):
                    aligned = start.astimezone(zone)
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
                    prefix = int((start - first_start).total_seconds() // 60)
                    for remainder in (prefix, available - length):
                        if 0 < remainder < action.minimum:
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
            local = start.astimezone(zone)
            period = "Morning" if local.hour < 12 else "Afternoon" if local.hour < 17 else "Evening"
            reason = f"{period} slot within work hours and daily capacity."
            completed, samples = (completion_history or {}).get(
                (local.weekday(), local.hour), (0, 0)
            )
            if samples >= 10:
                reason += (
                    f" Past completion here: {completed / samples:.0%} across {samples} blocks."
                )
            blocks.append(
                Block(
                    action.id,
                    action.goal_id,
                    action.title,
                    start,
                    end,
                    reason,
                )
            )
        dropped += need
    return Draft(sorted(blocks, key=lambda b: (b.start, b.action_id)), dropped)
