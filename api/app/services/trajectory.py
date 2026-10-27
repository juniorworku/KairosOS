"""Outcome progress is deterministic; time spent is separate evidence."""

from datetime import date, timedelta
from fractions import Fraction
from math import isfinite
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
    valid_metric = all(isfinite(value) for value in (metric_start, metric_target))
    valid_metric = valid_metric and metric_target != metric_start
    valid_latest = latest_metric is not None and isfinite(latest_metric)
    actual = 0.0
    if valid_metric and valid_latest and latest_metric is not None:
        # Subtracting finite floats can overflow, and a tiny span can overflow a ratio.
        # Exact fractions avoid both before we clamp the result to the public range.
        progress = (Fraction(latest_metric) - Fraction(metric_start)) / (
            Fraction(metric_target) - Fraction(metric_start)
        )
        actual = float(max(Fraction(0), min(Fraction(6, 5), progress)))
    insufficient = elapsed < 7 or not valid_latest or not valid_metric or total <= 0
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
    if not insufficient and actual > 0 and elapsed > 0:
        projected_days = elapsed / actual
        if isfinite(projected_days) and projected_days <= (date.max - start).days:
            projected = start + timedelta(days=projected_days)
    effort_ratio = None
    if isfinite(done) and isfinite(planned) and done >= 0 and planned > 0:
        ratio_value = done / planned
        if isfinite(ratio_value):
            effort_ratio = ratio_value
    if total <= 0:
        reason = "Set a target date after the goal's start date."
    elif not valid_metric:
        reason = "Use finite, different starting and target values for the outcome measure."
    elif not valid_latest:
        reason = "Add an outcome progress check-in."
    elif elapsed < 7:
        reason = "A full week of outcome evidence is needed before estimating progress."
    else:
        reason = "Outcome progress compared with elapsed time; focus effort is reported separately."
    return {
        "goal_id": goal_id,
        "status": status,
        "expected_fraction": expected,
        "actual_fraction": actual,
        "effort_ratio": effort_ratio,
        "projected_finish": projected.isoformat() if projected else None,
        "reasons": [reason],
    }
