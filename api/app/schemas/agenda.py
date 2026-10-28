"""Typed local task, event-series and occurrence-edit contracts."""

from datetime import UTC, date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.recurrence import Rule, series_occurrences


class AgendaModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class TaskInput(AgendaModel):
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=10000)
    due_date: date | None = None
    status: Literal["todo", "done"] = "todo"
    goal_id: str | None = Field(default=None, min_length=1, max_length=36)
    estimated_minutes: int = Field(default=30, ge=5, le=1440)


class TaskPatch(AgendaModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=10000)
    due_date: date | None = None
    status: Literal["todo", "done"] | None = None
    goal_id: str | None = Field(default=None, min_length=1, max_length=36)
    estimated_minutes: int | None = Field(default=None, ge=5, le=1440)


class TaskResponse(TaskInput):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")
    id: str


class RecurrenceInput(AgendaModel):
    frequency: Literal["daily", "weekly", "monthly", "yearly"]
    interval: int = Field(default=1, ge=1, le=52)
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    until: date | None = None
    count: int | None = Field(default=None, ge=1, le=500)

    @field_validator("weekdays")
    @classmethod
    def valid_days(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)) or any(day < 0 or day > 6 for day in value):
            raise ValueError("Choose each weekday once, from Monday 0 through Sunday 6")
        return sorted(value)

    def rule(self) -> Rule:
        return Rule(self.frequency, self.interval, tuple(self.weekdays), self.until, self.count)


class EventInput(AgendaModel):
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=10000)
    start_at: datetime
    end_at: datetime
    timezone: str = "UTC"
    all_day: bool = False
    task_id: str | None = Field(default=None, min_length=1, max_length=36)
    recurrence: RecurrenceInput | None = None

    @field_validator("start_at", "end_at")
    @classmethod
    def aware_times(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Event times require timezone offsets")
        try:
            return value.astimezone(UTC)
        except OverflowError as exc:
            raise ValueError("Event time is outside the supported calendar range") from exc

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Choose an IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def valid_event(self) -> "EventInput":
        if self.end_at <= self.start_at:
            raise ValueError("Event end must follow its start")
        zone = ZoneInfo(self.timezone)
        local_start, local_end = self.start_at.astimezone(zone), self.end_at.astimezone(zone)
        if self.all_day and (
            local_start.time() != datetime.min.time() or local_end.time() != datetime.min.time()
        ):
            raise ValueError(
                "All-day events start and end at local midnight; end date is exclusive"
            )
        if self.all_day and local_end.date() <= local_start.date():
            raise ValueError("All-day events must span at least one calendar day")
        if (local_end.date() - local_start.date()).days > 366:
            raise ValueError("An event may span at most 366 calendar days")
        series_occurrences(
            self.start_at,
            self.end_at,
            self.timezone,
            self.recurrence.rule() if self.recurrence else None,
        )
        return self


class EventPatch(AgendaModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=10000)
    start_at: datetime | None = None
    end_at: datetime | None = None
    timezone: str | None = None
    all_day: bool | None = None
    task_id: str | None = Field(default=None, min_length=1, max_length=36)
    recurrence: RecurrenceInput | None = None


class OccurrencePatch(EventPatch):
    recurrence: None = None


class EventResponse(EventInput):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")
    id: str


class AgendaItem(AgendaModel):
    id: str
    source: Literal["block", "local", "google"]
    source_id: str
    title: str
    notes: str
    start_at: str
    end_at: str
    all_day: bool
    timezone: str
    status: str
    editable: bool
    goal_id: str | None = None
    action_id: str | None = None
    task_id: str | None = None
    occurrence_date: date | None = None
    recurring: bool
