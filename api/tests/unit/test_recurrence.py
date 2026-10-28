from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.schemas.agenda import EventInput
from app.services.recurrence import Rule, series_occurrences


def test_weekly_recurrence_keeps_local_time_across_dst() -> None:
    zone = ZoneInfo("America/New_York")
    first = datetime(2026, 3, 6, 9, tzinfo=zone)
    last = datetime(2026, 3, 6, 10, tzinfo=zone)
    result = series_occurrences(first, last, zone.key, Rule("weekly", count=3))
    assert [item.start.hour for item in result] == [14, 13, 13]
    assert all(item.start.astimezone(zone).hour == 9 for item in result)
    assert all((item.end - item.start).total_seconds() == 3600 for item in result)


def test_nonexistent_spring_wall_time_is_skipped_not_shifted() -> None:
    zone = ZoneInfo("America/New_York")
    result = series_occurrences(
        datetime(2026, 3, 7, 2, 30, tzinfo=zone),
        datetime(2026, 3, 7, 2, 45, tzinfo=zone),
        zone.key,
        Rule("daily", count=3),
    )
    assert [item.original_date for item in result] == [
        date(2026, 3, 7),
        date(2026, 3, 9),
        date(2026, 3, 10),
    ]
    assert all(item.start.astimezone(zone).hour == 2 for item in result)


def test_all_day_recurrence_preserves_calendar_days_and_dst_lengths() -> None:
    zone = ZoneInfo("America/New_York")
    result = series_occurrences(
        datetime(2026, 3, 7, tzinfo=zone),
        datetime(2026, 3, 8, tzinfo=zone),
        zone.key,
        Rule("daily", count=3),
    )
    assert [(item.end - item.start).total_seconds() / 3600 for item in result] == [24, 23, 24]
    assert all(
        item.start.astimezone(zone).hour == item.end.astimezone(zone).hour == 0 for item in result
    )


def test_weekly_interval_weekdays_and_inclusive_until() -> None:
    result = series_occurrences(
        datetime(2026, 1, 5, 9, tzinfo=UTC),
        datetime(2026, 1, 5, 10, tzinfo=UTC),
        "UTC",
        Rule("weekly", interval=2, weekdays=(0, 2), until=date(2026, 1, 21)),
    )
    assert [item.original_date.isoformat() for item in result] == [
        "2026-01-05",
        "2026-01-07",
        "2026-01-19",
        "2026-01-21",
    ]


@pytest.mark.parametrize(
    "rule",
    [
        Rule("daily"),
        Rule("daily", count=501),
        Rule("daily", interval=0, count=1),
        Rule("weekly", weekdays=(1,), count=2),
        Rule("daily", until=date(2036, 1, 1)),
        Rule("daily", until=date(2025, 1, 1)),
        Rule("daily", until=date(2028, 1, 1)),
    ],
)
def test_recurrence_is_bounded_and_rejects_invalid_rules(rule: Rule) -> None:
    with pytest.raises(ValueError):
        series_occurrences(
            datetime(2026, 1, 5, 9, tzinfo=UTC), datetime(2026, 1, 5, 10, tzinfo=UTC), "UTC", rule
        )


def test_event_validation_rejects_naive_or_non_midnight_all_day() -> None:
    for body in (
        {"start_at": "2026-01-05T09:00:00", "end_at": "2026-01-05T10:00:00"},
        {"start_at": "2026-01-05T09:00:00Z", "end_at": "2026-01-06T09:00:00Z", "all_day": True},
    ):
        with pytest.raises(ValidationError):
            EventInput.model_validate({"title": "Event", **body})
