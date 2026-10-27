import json
from datetime import date

import pytest

from app.services.trajectory import compute


def test_large_finite_metrics_do_not_overflow_progress() -> None:
    result = compute(
        "goal", date(2026, 1, 1), date(2026, 1, 21), -1e308, 1e308, 0, 10, 20, date(2026, 1, 11)
    )
    assert result["actual_fraction"] == 0.5
    assert result["status"] == "on_track"
    assert result["projected_finish"] == "2026-01-21"


def test_tiny_metric_range_clamps_without_infinite_ratio() -> None:
    result = compute(
        "goal",
        date(2026, 1, 1),
        date(2026, 1, 21),
        0,
        1e-308,
        1e308,
        1e308,
        1e-308,
        date(2026, 1, 11),
    )
    assert result["actual_fraction"] == 1.2
    assert result["effort_ratio"] is None
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_invalid_legacy_metrics_are_insufficient_and_json_safe(value: float) -> None:
    result = compute(
        "goal", date(2026, 1, 1), date(2026, 1, 21), 0, 100, value, 0, 0, date(2026, 1, 11)
    )
    assert result["status"] == "insufficient_data"
    assert result["projected_finish"] is None
    json.dumps(result, allow_nan=False)


def test_first_week_never_implies_a_reliable_finish_prediction() -> None:
    result = compute(
        "goal", date(2026, 1, 1), date(2026, 1, 21), 0, 100, 50, 1000, 10, date(2026, 1, 3)
    )
    assert result["status"] == "insufficient_data"
    assert result["projected_finish"] is None
    assert result["actual_fraction"] == 0.5


def test_effort_never_creates_outcome_progress() -> None:
    result = compute(
        "goal", date(2026, 1, 1), date(2026, 1, 21), 0, 100, None, 10000, 10, date(2026, 1, 11)
    )
    assert result["actual_fraction"] == 0
    assert result["status"] == "insufficient_data"
    assert result["effort_ratio"] == 1000
