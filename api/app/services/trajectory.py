"""Outcome progress is deterministic; time spent is separate evidence."""

from datetime import date, timedelta
from typing import TypedDict


class Trajectory(TypedDict):
    goal_id: str
    status: str
    expected_fraction: float
    actual_fraction: float
    effort_ratio: float | None
    projected_finish: str | None
    reasons: list[str]


def compute(
    goal_id: str,
    start: date,
    target: date,
    metric_start: float,
    metric_target: float,
    latest_metric: float | None,
    done: float,
    planned: float,
    today: date,
) -> Trajectory:
    elapsed = max(0, (today - start).days)
    total = (target - start).days
    expected = max(0.0, min(1.0, elapsed / total)) if total > 0 else 1.0
    span = metric_target - metric_start
    actual = (
        max(0.0, min(1.2, (latest_metric - metric_start) / span))
        if latest_metric is not None and span != 0
        else 0.0
    )
    insufficient = elapsed < 7 or latest_metric is None or span == 0 or total <= 0
    ratio = actual / expected if expected > 0 else 1.0
    status = (
        "insufficient_data"
        if insufficient
        else "on_track"
        if ratio >= 0.9
        else "adjust"
        if ratio >= 0.7
        else "off_track"
    )
    projected = None
    if actual > 0 and elapsed > 0:
        projected_days = elapsed / actual
        if projected_days <= (date.max - start).days:
            projected = start + timedelta(days=projected_days)
    return {
        "goal_id": goal_id,
        "status": status,
        "expected_fraction": expected,
        "actual_fraction": actual,
        "effort_ratio": done / planned if planned > 0 else None,
        "projected_finish": projected.isoformat() if projected else None,
        "reasons": [
            "Add a progress check-in after the first week."
            if insufficient
            else "Outcome progress compared with elapsed time; focus effort is reported separately."
        ],
    }
