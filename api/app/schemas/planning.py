"""Planning request contracts."""

import re
from collections.abc import Sequence
from datetime import UTC, date, datetime
from math import isfinite
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PlanningModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, str_strip_whitespace=True)


class ActionInput(PlanningModel):
    id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    kind: Literal["habit", "project"] = "habit"
    weekly_minutes_target: int = Field(default=120, ge=0, le=10080)
    total_minutes_estimate: int | None = Field(default=None, ge=1, le=1000000)
    preferred_block_minutes: int = Field(default=60, ge=15, le=240)
    min_block_minutes: int = Field(default=30, ge=15, le=240)
    max_block_minutes: int = Field(default=120, ge=15, le=240)
    preferred_time_of_day: Literal["morning", "afternoon", "evening", "any"] = "any"
    requires_deep_focus: bool = True

    @model_validator(mode="after")
    def lengths(self) -> "ActionInput":
        if not self.min_block_minutes <= self.preferred_block_minutes <= self.max_block_minutes:
            raise ValueError("Block lengths must be min <= preferred <= max")
        return self


class ObstacleInput(PlanningModel):
    risk_text: str = Field(max_length=1000)
    if_cue: str = Field(max_length=1000)
    then_response: str = Field(max_length=1000)


class GoalInput(PlanningModel):
    title: str = Field(min_length=1, max_length=200)
    outcome_statement: str = Field(default="", max_length=2000)
    season_id: str | None = None
    metric_name: str = Field(default="Progress", max_length=100)
    metric_unit: str = Field(default="units", max_length=100)
    metric_start: float = 0
    metric_target: float = 100
    start_date: date
    target_date: date
    why_facts: str = Field(default="", max_length=10000)
    why_feelings: str = Field(default="", max_length=10000)
    why_function: str = Field(default="", max_length=10000)
    anti_goals: list[str] = Field(default_factory=list, max_length=20)
    confidence_pct: int = Field(default=80, ge=0, le=100)
    follow_through_pct: int = Field(default=80, ge=0, le=100)
    priority: int = Field(default=3, ge=1, le=5)
    status: Literal["active", "paused", "done", "dropped"] = "active"
    actions: Sequence[ActionInput] = Field(min_length=1, max_length=5)
    obstacles: list[ObstacleInput] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def dates(self) -> "GoalInput":
        if self.target_date <= self.start_date:
            raise ValueError("Target date must follow start date")
        if not isfinite(self.metric_target - self.metric_start):
            raise ValueError("Metric range must be finite")
        if self.metric_target == self.metric_start:
            raise ValueError("Metric target must differ from starting value")
        return self


class SeasonInput(PlanningModel):
    name: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: date
    status: Literal["planned", "active", "done"] = "active"

    @model_validator(mode="after")
    def dates(self) -> "SeasonInput":
        if self.end_date < self.start_date:
            raise ValueError("Season ends before it starts")
        return self


class BusyInput(PlanningModel):
    start_at: datetime
    end_at: datetime

    @model_validator(mode="after")
    def times(self) -> "BusyInput":
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("Times require timezone offsets")
        if self.end_at <= self.start_at:
            raise ValueError("End must follow start")
        return self


class CheckinInput(PlanningModel):
    client_event_id: UUID | None = None
    metric_value: float
    note: str = Field(default="", max_length=2000)


class DraftInput(PlanningModel):
    week_start: date


class AcceptInput(PlanningModel):
    block_ids: list[str] = Field(max_length=500)


class BlockPatch(PlanningModel):
    start_at: datetime | None = None
    end_at: datetime | None = None
    status: Literal["accepted", "skipped", "completed", "cancelled"] | None = None

    @model_validator(mode="after")
    def aware_timestamps(self) -> "BlockPatch":
        if any(
            value is not None and value.tzinfo is None for value in (self.start_at, self.end_at)
        ):
            raise ValueError("Times require timezone offsets")
        if self.start_at is not None and self.end_at is not None and self.end_at <= self.start_at:
            raise ValueError("End must follow start")
        return self


class BlockCreate(BusyInput):
    goal_id: str = Field(min_length=1, max_length=36)
    action_id: str = Field(min_length=1, max_length=36)
    status: Literal["proposed", "accepted"] = "accepted"


class FocusInput(PlanningModel):
    blocklist_id: str | None = None
    time_block_id: str | None = None
    action_id: str | None = None
    planned_minutes: int = Field(default=25, ge=1, le=240)


class FocusEnd(PlanningModel):
    ended_at: datetime | None = None
    client_event_id: UUID | None = None
    self_rating: int | None = Field(default=None, ge=1, le=5)

    @field_validator("ended_at")
    @classmethod
    def aware_end(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Session end time requires a timezone offset")
            return value.astimezone(UTC)
        return value


class ReflectionInput(PlanningModel):
    wins: str = Field(default="", max_length=10000)
    misses: str = Field(default="", max_length=10000)
    adjustments: str = Field(default="", max_length=10000)


class ActionResponse(ActionInput):
    id: str


class CheckinResponse(CheckinInput):
    id: str
    goal_id: str
    recorded_at: datetime


class GoalResponse(GoalInput):
    id: str
    actions: list[ActionResponse]
    checkins: list[CheckinResponse] = Field(default_factory=list)


class SeasonResponse(SeasonInput):
    id: str


class BusyResponse(BusyInput):
    id: str


class BlockResponse(PlanningModel):
    id: str
    action_id: str
    goal_id: str
    title: str
    start_at: datetime
    end_at: datetime
    planned_minutes: int
    status: Literal[
        "proposed", "accepted", "published", "completed", "skipped", "moved", "cancelled"
    ]
    reason: str
    week_start: date
    moved_count: int = 0
    google_event_id: str | None = None


class DraftResponse(PlanningModel):
    blocks: list[BlockResponse]
    capacity_warning: str | None = None
    dropped_minutes: int = 0


class FocusResponse(PlanningModel):
    blocklist_id: str | None = None
    blocklist_snapshot: list[str] = Field(default_factory=list)
    title: str = "Focus"
    id: str
    time_block_id: str | None
    action_id: str | None
    goal_id: str | None
    started_at: datetime
    ends_at: datetime
    ended_at: datetime | None = None
    planned_minutes: int
    actual_minutes: float = 0
    self_rating: int | None = None


class FocusStats(PlanningModel):
    completed_sessions: int
    total_minutes: float
    average_rating: float | None


class ReflectionResponse(ReflectionInput):
    id: str
    week_start: date


class TrajectoryResponse(PlanningModel):
    goal_id: str
    status: Literal["on_track", "adjust", "off_track", "insufficient_data"]
    expected_fraction: float
    actual_fraction: float
    effort_ratio: float | None
    projected_finish: date | None
    reasons: list[str]


class FocusHistory(PlanningModel):
    items: list[FocusResponse]
    next_cursor: str | None


class BlocklistInput(PlanningModel):
    name: str = Field(min_length=1, max_length=100)
    domains: list[str] = Field(default_factory=list, max_length=100)
    is_default: bool = False

    @field_validator("domains")
    @classmethod
    def normalize_domains(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        pattern = re.compile(
            r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
            r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
        )
        for value in values:
            try:
                domain = value.strip().rstrip(".").encode("idna").decode("ascii").lower()
            except UnicodeError as error:
                raise ValueError("Use valid domain names") from error
            if len(domain) > 253 or not pattern.fullmatch(domain):
                raise ValueError("Use domain names without paths, ports, or wildcards")
            if domain in {"localhost", "127.0.0.1", "0.0.0.0"} or domain.endswith(".localhost"):
                raise ValueError("Local application addresses cannot be blocked")
            if domain not in result:
                result.append(domain)
        return result


class BlocklistResponse(BlocklistInput):
    id: str
