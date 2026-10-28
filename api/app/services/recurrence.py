"""Bounded local calendar recurrence; no persistence, provider or network calls."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

MAX_OCCURRENCES = 500


@dataclass(frozen=True)
class Rule:
    frequency: Literal["daily", "weekly", "monthly", "yearly"]
    interval: int = 1
    weekdays: tuple[int, ...] = ()
    until: date | None = None
    count: int | None = None


@dataclass(frozen=True)
class Occurrence:
    original_date: date
    start: datetime
    end: datetime


def _dates(start: date, rule: Rule) -> Iterator[date]:
    if (
        rule.frequency not in {"daily", "weekly", "monthly", "yearly"}
        or not 1 <= rule.interval <= 52
    ):
        raise ValueError("Choose a repeat interval between 1 and 52")
    if rule.count is None and rule.until is None:
        raise ValueError("Repeating events need an end date or occurrence count")
    if rule.count is not None and not 1 <= rule.count <= MAX_OCCURRENCES:
        raise ValueError("Repeating events support at most 500 occurrences")
    if rule.until is not None and (rule.until < start or (rule.until - start).days > 5 * 366):
        raise ValueError("Repeat end must be within five years of the first event")
    weekdays = tuple(sorted(set(rule.weekdays or (start.weekday(),))))
    if any(day < 0 or day > 6 for day in weekdays):
        raise ValueError("Weekdays run from Monday 0 through Sunday 6")
    if rule.frequency == "weekly" and start.weekday() not in weekdays:
        raise ValueError("Repeating weekdays must include the first event's weekday")
    anchor = start - timedelta(days=start.weekday())
    # Include skipped month-end dates, leap years and isolated DST gaps.
    # The explicit bound also protects callers from malformed persisted rules.
    for index in range(MAX_OCCURRENCES * 8 + 2):
        try:
            if rule.frequency == "daily":
                candidates = [start + timedelta(days=index * rule.interval)]
            elif rule.frequency == "weekly":
                monday = anchor + timedelta(weeks=index * rule.interval)
                candidates = [monday + timedelta(days=day) for day in weekdays]
            else:
                if rule.frequency == "monthly":
                    offset = start.year * 12 + start.month - 1 + index * rule.interval
                    year, zero_month = divmod(offset, 12)
                    month = zero_month + 1
                else:
                    year, month = start.year + index * rule.interval, start.month
                if year > 9999:
                    return
                # Anchor to the original day. Jan 31 skips February instead of drifting
                # to Feb 28, and Feb 29 skips non-leap years instead of changing dates.
                try:
                    candidates = [date(year, month, start.day)]
                except ValueError:
                    continue
        except OverflowError:
            return
        for candidate in candidates:
            if candidate < start:
                continue
            if rule.until is not None and candidate > rule.until:
                return
            yield candidate


def _instant(wall: datetime, zone: ZoneInfo, fold: int) -> datetime | None:
    candidate = wall.replace(tzinfo=zone, fold=fold).astimezone(UTC)
    # A spring-forward gap has no such local instant. Do not silently move it.
    if candidate.astimezone(zone).replace(tzinfo=None) != wall:
        return None
    return candidate


def series_occurrences(
    start: datetime,
    end: datetime,
    timezone: str,
    rule: Rule | None,
) -> list[Occurrence]:
    if (
        start.utcoffset() is None
        or end.utcoffset() is None
        or end.astimezone(UTC) <= start.astimezone(UTC)
    ):
        raise ValueError("Events need timezone-aware, increasing timestamps")
    zone = ZoneInfo(timezone)
    local_start, local_end = start.astimezone(zone), end.astimezone(zone)
    if rule is None:
        return [Occurrence(local_start.date(), start.astimezone(UTC), end.astimezone(UTC))]
    if rule.frequency != "weekly" and rule.weekdays:
        raise ValueError("Weekday selections are for weekly repeats")
    wall_start = local_start.replace(tzinfo=None)
    wall_duration = local_end.replace(tzinfo=None) - wall_start
    if wall_duration <= timedelta():
        raise ValueError("Repeating events need an increasing local wall-clock duration")
    result: list[Occurrence] = []
    for day in _dates(local_start.date(), rule):
        try:
            beginning = datetime.combine(day, wall_start.time())
            finishing = beginning + wall_duration
            first = _instant(beginning, zone, local_start.fold)
            last = _instant(finishing, zone, local_end.fold)
        except (OverflowError, ValueError):
            break
        if first is None or last is None or last <= first:
            continue
        result.append(Occurrence(day, first, last))
        if rule.count is not None and len(result) >= rule.count:
            return result
        if len(result) > MAX_OCCURRENCES:
            raise ValueError("Repeat range exceeds 500 occurrences; choose an earlier end date")
    if rule.count is not None and rule.until is None and len(result) < rule.count:
        raise ValueError("The repeat count extends beyond the supported calendar range")
    return result
