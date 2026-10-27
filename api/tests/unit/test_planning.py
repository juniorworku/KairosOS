from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.planning import GoalInput
from app.services.scheduler.plan import Action, Interval, duration_multiplier, free_slots, make_plan
from app.services.trajectory import compute


def test_duration_calibration() -> None:
    assert duration_multiplier([]) == 1.3
    assert duration_multiplier([(0, 10)] * 8) == 1.3
    assert duration_multiplier([(10, 50)] * 5) == 2
    assert duration_multiplier([(10, 5)] * 5) == 1


def test_dst_working_hours() -> None:
    slots = free_slots(date(2026, 3, 2), "America/New_York", [6], "01:00", "04:00", [], 0)
    assert len(slots) == 1
    assert slots[0].end - slots[0].start == timedelta(hours=2)
    assert slots[0].start.hour == 6
    assert slots[0].end.hour == 8


def test_overlapping_busy_and_buffer() -> None:
    start = datetime(2026, 10, 26, 9, tzinfo=UTC)
    busy = [
        Interval(start, start + timedelta(hours=1)),
        Interval(start + timedelta(minutes=30), start + timedelta(hours=2)),
    ]
    slots = free_slots(start.date(), "UTC", [0], "09:00", "12:00", busy)
    assert len(slots) == 1
    assert slots[0].start == start + timedelta(hours=2, minutes=10)


def test_deterministic_caps_capacity_priority_and_blackout() -> None:
    week = date(2026, 10, 26)
    start = datetime(2026, 10, 26, 9, tzinfo=UTC)
    high = Action("a", "g", "High", 5, 300)
    low = Action("b", "h", "Low", 1, 300)
    kwargs = dict(
        week=week,
        timezone="UTC",
        work_days=[0, 1],
        work_start="09:00",
        work_end="17:00",
        daily_cap=60,
        energy_peak="morning",
        actions=[low, high],
        busy=[],
        existing=[],
        blackouts=[Interval(start, start + timedelta(hours=2))],
        multiplier=1,
    )
    result = make_plan(**kwargs)
    assert result == make_plan(**kwargs)
    assert sum(int((b.end - b.start).total_seconds() / 60) for b in result.blocks) == 120
    assert all(b.action_id == "a" for b in result.blocks)
    assert result.blocks[0].start >= start + timedelta(hours=2)
    assert result.dropped_minutes == 480
    assert all(b.reason for b in result.blocks)
    assert all(b.start.minute in (0, 30) for b in result.blocks)


def test_empty_and_full_week() -> None:
    week = date(2026, 10, 26)
    args = (week, "UTC", [0], "09:00", "10:00", 60, "morning")
    assert make_plan(*args, [], [], []).blocks == []
    busy = [Interval(datetime(2026, 10, 26, tzinfo=UTC), datetime(2026, 10, 27, tzinfo=UTC))]
    result = make_plan(*args, [Action("a", "g", "x", 1, 60)], busy, [], multiplier=1)
    assert not result.blocks
    assert result.dropped_minutes == 60


def test_accepted_blocks_consume_cap() -> None:
    start = datetime(2026, 10, 26, 9, tzinfo=UTC)
    result = make_plan(
        start.date(),
        "UTC",
        [0],
        "09:00",
        "17:00",
        60,
        "morning",
        [Action("a", "g", "x", 1, 60)],
        [],
        [Interval(start, start + timedelta(hours=1))],
        multiplier=1,
    )
    assert not result.blocks


def test_trajectory_decrease_and_insufficient() -> None:
    args = ("g", date(2026, 1, 1), date(2026, 1, 21), 100, 0)
    result = compute(*args, 50, 30, 60, date(2026, 1, 11))
    assert result["actual_fraction"] == 0.5
    assert result["status"] == "on_track"
    assert result["effort_ratio"] == 0.5
    assert result["projected_finish"] == "2026-01-21"
    assert compute(*args, None, 0, 0, date(2026, 1, 11))["status"] == "insufficient_data"
    assert compute(*args, 50, 0, 0, date(2026, 1, 3))["status"] == "insufficient_data"
    assert (
        compute("g", date(2026, 1, 1), date(2026, 1, 1), 0, 0, 0, 0, 0, date(2026, 1, 11))[
            "projected_finish"
        ]
        is None
    )


def test_goal_action_cap_and_metric_range() -> None:
    base = dict(title="Goal", start_date="2026-01-01", target_date="2026-04-01")
    with pytest.raises(ValidationError):
        GoalInput.model_validate({**base, "actions": [{"title": "a"}] * 6})
    with pytest.raises(ValidationError):
        GoalInput.model_validate({**base, "actions": [{"title": "a"}], "metric_target": 0})
    with pytest.raises(ValidationError):
        GoalInput.model_validate({**base, "actions": []})


def test_fall_dst_never_places_before_free_slot() -> None:
    # 01:00 occurs twice; busy time ends in the second occurrence.
    week = date(2026, 10, 26)
    occupied = [
        Interval(datetime(2026, 11, 1, 4, tzinfo=UTC), datetime(2026, 11, 1, 5, 50, tzinfo=UTC))
    ]
    result = make_plan(
        week,
        "America/New_York",
        [6],
        "00:00",
        "04:00",
        60,
        "morning",
        [Action("a", "g", "x", 1, 60)],
        occupied,
        [],
        multiplier=1,
    )
    assert result.blocks
    assert result.blocks[0].start >= datetime(2026, 11, 1, 6, tzinfo=UTC)


def test_earliest_date_bounds_and_alignment() -> None:
    week = date(2026, 10, 26)
    earliest = datetime(2026, 10, 26, 9, 30, 1, tzinfo=UTC)
    result = make_plan(
        week,
        "UTC",
        [0, 1],
        "09:00",
        "17:00",
        60,
        "morning",
        [Action("a", "g", "x", 1, 60)],
        [],
        [],
        multiplier=1,
        earliest=earliest,
    )
    assert result.blocks[0].start == datetime(2026, 10, 26, 10, tzinfo=UTC)
    restricted = make_plan(
        week,
        "UTC",
        [0, 1],
        "09:00",
        "17:00",
        60,
        "morning",
        [Action("a", "g", "x", 1, 60, starts_on=week + timedelta(days=1))],
        [],
        [],
        multiplier=1,
    )
    assert restricted.blocks[0].start.date() == week + timedelta(days=1)


def test_completion_history_neutral_until_ten_samples() -> None:
    week = date(2026, 10, 26)
    arguments = (
        week,
        "UTC",
        [0, 1],
        "09:00",
        "12:00",
        60,
        "morning",
        [Action("a", "g", "x", 1, 60)],
        [],
        [],
    )
    neutral = make_plan(
        *arguments, multiplier=1, completion_history={(0, 9): (0, 9), (1, 9): (9, 9)}
    )
    experienced = make_plan(
        *arguments, multiplier=1, completion_history={(0, 9): (0, 10), (1, 9): (10, 10)}
    )
    assert neutral.blocks[0].start.weekday() == 0
    assert experienced.blocks[0].start.weekday() == 1


def test_blocklist_domains_normalize_and_reject_unsafe_values() -> None:
    from app.schemas.planning import BlocklistInput

    assert BlocklistInput(
        name="Focus", domains=[" YOUTUBE.com ", "youtube.com", "bücher.de"]
    ).domains == ["youtube.com", "xn--bcher-kva.de"]
    for domain in [
        "https://youtube.com",
        "*.example.com",
        "example.com/path",
        "a\n.example.com",
        "localhost",
        "127.0.0.1",
        "-bad.example",
        "a..example.com",
    ]:
        with pytest.raises(ValidationError):
            BlocklistInput(name="Focus", domains=[domain])
