"""Optional provider boundary. Suggestions never mutate planning data."""

import json
import re
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal, Protocol, TypeVar, cast

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import current_user, get_db
from app.integrations.config import IntegrationSettings
from app.integrations.jsonutil import Json, list_value, object_value, string_value
from app.integrations.models import AICall
from app.models.auth import Plan, User

coach_router = APIRouter(prefix="/api/v1/coach", tags=["Coach"])
DB = Annotated[AsyncSession, Depends(get_db)]
Owner = Annotated[User, Depends(current_user)]
Schema = TypeVar("Schema", bound=BaseModel)
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "coach.md").read_text()


class AIUnavailable(Exception):
    pass


class ProviderResult(BaseModel):
    text: str
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


def token_count(value: Json) -> int | None:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    raise ValueError("Invalid provider usage")


class LLMProvider(Protocol):
    def stream_text(
        self, *, system: str, user: str, max_tokens: int
    ) -> AsyncIterator[ProviderResult]: ...

    async def generate(
        self, *, system: str, user: str, schema: dict[str, Json] | None, max_tokens: int
    ) -> ProviderResult: ...


class AnthropicProvider:
    def __init__(self, config: IntegrationSettings, client: httpx.AsyncClient) -> None:
        self.config, self.client = config, client

    async def generate(
        self, *, system: str, user: str, schema: dict[str, Json] | None, max_tokens: int
    ) -> ProviderResult:
        body: dict[str, Json] = {
            "model": self.config.anthropic_model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if schema:
            body["tools"] = [
                {
                    "name": "suggestion",
                    "description": "Return the requested suggestion",
                    "input_schema": schema,
                }
            ]
            body["tool_choice"] = {"type": "tool", "name": "suggestion"}
        response = await self.client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.config.anthropic_api_key, "anthropic-version": "2023-06-01"},
            json=body,
        )
        if response.status_code != 200:
            raise AIUnavailable("Coaching is unavailable. Try again later.")
        data = object_value(cast(Json, response.json()))
        parts: list[str] = []
        for item in list_value(data.get("content", [])):
            part = object_value(item)
            if part.get("type") == "tool_use":
                parts.append(json.dumps(part.get("input")))
            elif part.get("type") == "text":
                parts.append(string_value(part.get("text")))
        usage = object_value(data.get("usage", {}))
        return ProviderResult(
            text="".join(parts),
            input_tokens=token_count(usage.get("input_tokens")),
            output_tokens=token_count(usage.get("output_tokens")),
        )

    async def stream_text(
        self, *, system: str, user: str, max_tokens: int
    ) -> AsyncIterator[ProviderResult]:
        async with self.client.stream(
            "POST",
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": self.config.anthropic_api_key, "anthropic-version": "2023-06-01"},
            json={
                "model": self.config.anthropic_model,
                "max_tokens": max_tokens,
                "stream": True,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        ) as response:
            if response.status_code != 200:
                raise AIUnavailable("Coaching is unavailable. Try again later.")
            input_tokens: int | None = None
            output_tokens: int | None = None
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = object_value(cast(Json, json.loads(line[6:])))
                kind = data.get("type")
                if kind == "error":
                    raise AIUnavailable("Coaching was interrupted. Try again.")
                if kind == "message_start":
                    usage = object_value(object_value(data.get("message")).get("usage", {}))
                    input_tokens = token_count(usage.get("input_tokens"))
                elif kind == "message_delta":
                    usage = object_value(data.get("usage", {}))
                    output_tokens = token_count(usage.get("output_tokens", output_tokens))
                elif kind == "content_block_delta":
                    delta = object_value(data.get("delta"))
                    if delta.get("type") == "text_delta":
                        yield ProviderResult(text=string_value(delta.get("text")))
            if output_tokens is None:
                raise AIUnavailable("Coaching was interrupted before usage was confirmed.")
            yield ProviderResult(text="", input_tokens=input_tokens, output_tokens=output_tokens)


class GeminiProvider:
    def __init__(self, config: IntegrationSettings, client: httpx.AsyncClient) -> None:
        self.config, self.client = config, client

    async def generate(
        self, *, system: str, user: str, schema: dict[str, Json] | None, max_tokens: int
    ) -> ProviderResult:
        generation: dict[str, Json] = {"maxOutputTokens": max_tokens}
        if schema:
            generation.update(responseMimeType="application/json", responseJsonSchema=schema)
        response = await self.client.post(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + self.config.gemini_model
            + ":generateContent",
            headers={"x-goog-api-key": self.config.gemini_api_key},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": generation,
            },
        )
        if response.status_code != 200:
            raise AIUnavailable("Coaching is unavailable. Try again later.")
        data = object_value(cast(Json, response.json()))
        candidates = list_value(data.get("candidates", []))
        if not candidates:
            raise AIUnavailable("No suggestion was returned.")
        content = object_value(object_value(candidates[0]).get("content"))
        parts = list_value(content.get("parts", []))
        answer = "".join(string_value(object_value(part).get("text", "")) for part in parts)
        usage = object_value(data.get("usageMetadata", {}))
        return ProviderResult(
            text=answer,
            input_tokens=token_count(usage.get("promptTokenCount")),
            output_tokens=token_count(usage.get("candidatesTokenCount")),
        )

    async def stream_text(
        self, *, system: str, user: str, max_tokens: int
    ) -> AsyncIterator[ProviderResult]:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + self.config.gemini_model
            + ":streamGenerateContent?alt=sse"
        )
        async with self.client.stream(
            "POST",
            url,
            headers={"x-goog-api-key": self.config.gemini_api_key},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"maxOutputTokens": max_tokens},
            },
        ) as response:
            if response.status_code != 200:
                raise AIUnavailable("Coaching is unavailable. Try again later.")
            input_tokens: int | None = None
            output_tokens: int | None = None
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = object_value(cast(Json, json.loads(line[6:])))
                if data.get("error"):
                    raise AIUnavailable("Coaching was interrupted. Try again.")
                usage = object_value(data.get("usageMetadata", {}))
                input_tokens = token_count(usage.get("promptTokenCount", input_tokens))
                output_tokens = token_count(usage.get("candidatesTokenCount", output_tokens))
                for candidate in list_value(data.get("candidates", [])):
                    content = object_value(object_value(candidate).get("content", {}))
                    for part in list_value(content.get("parts", [])):
                        value = object_value(part).get("text")
                        if isinstance(value, str):
                            yield ProviderResult(text=value)
            if output_tokens is None:
                raise AIUnavailable("Coaching was interrupted before usage was confirmed.")
            yield ProviderResult(text="", input_tokens=input_tokens, output_tokens=output_tokens)


def get_provider(config: IntegrationSettings, client: httpx.AsyncClient) -> LLMProvider:
    if config.llm_provider == "anthropic":
        return AnthropicProvider(config, client)
    if config.llm_provider == "gemini":
        return GeminiProvider(config, client)
    raise AIUnavailable("No coach provider is configured.")


def redact(value: str) -> str:
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", value)
    return re.sub(r"https?://\S+", "[link]", value)


async def structured(
    provider: LLMProvider, prompt: str, schema: type[Schema], max_tokens: int
) -> tuple[Schema, ProviderResult]:
    for attempt in range(2):
        result = await provider.generate(
            system=SYSTEM_PROMPT,
            user=prompt,
            schema=cast(dict[str, Json], schema.model_json_schema()),
            max_tokens=max_tokens,
        )
        try:
            return schema.model_validate_json(result.text), result
        except ValidationError as exc:
            if attempt:
                raise AIUnavailable("The suggestion could not be checked. Try again.") from exc
            prompt += "\nReturn valid JSON matching the schema. Do not add other text."
    raise AIUnavailable("The suggestion could not be checked.")


async def reserve(db: AsyncSession, user: User, task: str, config: IntegrationSettings) -> AICall:
    # Serialize reservations globally: no quota overshoot under concurrent requests.
    # Release the short reservation lock before provider I/O.
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(92034001)"))
    await db.scalar(select(User).where(User.id == user.id).with_for_update())
    plan = await db.get(Plan, user.plan_id)
    quotas = plan.quotas if plan else {}
    now = datetime.now(UTC)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month = day.replace(day=1)
    global_calls = (
        await db.scalar(select(func.count()).select_from(AICall).where(AICall.created_at >= day))
        or 0
    )
    if global_calls >= config.global_ai_daily_call_cap:
        raise HTTPException(
            503, detail={"code": "ai_unavailable", "message": "The coach is unavailable today."}
        )
    calls = (
        await db.scalar(
            select(func.count())
            .select_from(AICall)
            .where(AICall.user_id == user.id, AICall.created_at >= day)
        )
        or 0
    )
    output = (
        await db.scalar(
            select(func.coalesce(func.sum(AICall.output_tokens), 0)).where(
                AICall.user_id == user.id, AICall.created_at >= month
            )
        )
        or 0
    )
    checks = [
        ("ai.calls", calls, 1, int(quotas.get("ai.calls", 10))),
        (
            "ai.output_tokens",
            int(output),
            config.llm_max_output_tokens,
            int(quotas.get("ai.output_tokens", 20000)),
        ),
    ]
    if task == "chat":
        chat_calls = (
            await db.scalar(
                select(func.count())
                .select_from(AICall)
                .where(AICall.user_id == user.id, AICall.task == task, AICall.created_at >= day)
            )
            or 0
        )
        checks.append(("ai.chat_messages", chat_calls, 1, int(quotas.get("ai.chat_messages", 10))))
    if task == "weekly-review":
        reviews = (
            await db.scalar(
                select(func.count())
                .select_from(AICall)
                .where(AICall.user_id == user.id, AICall.task == task, AICall.created_at >= month)
            )
            or 0
        )
        checks.append(("ai.retro", reviews, 1, int(quotas.get("ai.retro", 4))))
    for metric, used, cost, limit in checks:
        if used + cost > limit:
            resets = (
                (month + timedelta(days=32)).replace(day=1)
                if metric in {"ai.output_tokens", "ai.retro"}
                else day + timedelta(days=1)
            )
            raise HTTPException(
                429,
                detail={
                    "code": "quota_exceeded",
                    "metric": metric,
                    "limit": limit,
                    "used": used,
                    "resets_at": resets.isoformat(),
                    "message": (
                        "Your monthly coaching allowance has been used."
                        if metric in {"ai.output_tokens", "ai.retro"}
                        else "Your daily coaching allowance has been used."
                    ),
                },
            )
    call = AICall(
        user_id=user.id,
        task=task,
        provider=config.llm_provider,
        model=config.anthropic_model if config.llm_provider == "anthropic" else config.gemini_model,
        output_tokens=config.llm_max_output_tokens,
    )
    db.add(call)
    await db.commit()
    return call


async def finish_call(
    db: AsyncSession, call: AICall, result: ProviderResult | None, elapsed: float
) -> None:
    # Missing usage includes cancellation, partial streams, and provider failures. Keep the
    # committed maximum reservation: releasing it would let repeated aborts evade quotas.
    # These conservative counts are quota reservations, not claims about actual billing.
    usage_known = result is not None and result.output_tokens is not None
    call.status = "success" if usage_known else "failed" if result is None else "usage_unknown"
    call.latency_ms = round(elapsed * 1000)
    if result is not None:
        if result.input_tokens is not None:
            call.input_tokens = result.input_tokens
        if result.output_tokens is not None:
            call.output_tokens = result.output_tokens
    await db.commit()


async def server_context(db: AsyncSession, user: User) -> str:
    from app.models.planning import PlanningRecord
    from app.routers.planning import trajectory

    positions = await trajectory(db, user)
    goals = (
        await db.scalars(
            select(PlanningRecord)
            .where(PlanningRecord.user_id == user.id, PlanningRecord.kind == "goal")
            .order_by(PlanningRecord.created_at)
            .limit(20)
        )
    ).all()
    positions_by_id = {position.goal_id: position for position in positions}
    context: list[dict[str, Json]] = []
    for index, goal in enumerate(goals):
        position = positions_by_id.get(goal.id)
        if not position:
            continue
        context.append(
            {
                "goal": f"Goal {index + 1}",
                "title": redact(str(goal.payload.get("title", ""))),
                "outcome": redact(str(goal.payload.get("outcome_statement", ""))),
                "status": position.status,
                "expected_fraction": position.expected_fraction,
                "actual_fraction": position.actual_fraction,
                "effort_ratio": position.effort_ratio,
            }
        )
    return json.dumps({"goals": context})


class CoachInput(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    include_context: bool = False


class GoalSuggestion(BaseModel):
    outcome_statement: str = Field(max_length=1000)
    metric_name: str = Field(min_length=1, max_length=100)
    metric_unit: str = Field(max_length=60)
    suggested_target: float = Field(allow_inf_nan=False)
    clarifying_questions: list[str] = Field(max_length=5)


class ActionSuggestion(BaseModel):
    title: str = Field(max_length=200)
    kind: Literal["habit", "project"]
    weekly_minutes: int = Field(ge=30, le=2400)
    rationale: str = Field(max_length=1000)


class ActionSuggestions(BaseModel):
    actions: list[ActionSuggestion] = Field(min_length=1, max_length=5)


class ObstacleSuggestion(BaseModel):
    risk: str = Field(max_length=1000)
    if_cue: str = Field(max_length=1000)
    then_response: str = Field(max_length=1000)


class ObstacleSuggestions(BaseModel):
    obstacles: list[ObstacleSuggestion] = Field(min_length=1, max_length=5)


class ReviewSuggestion(BaseModel):
    text: str = Field(max_length=1000)
    type: Literal["planning", "focus", "goal", "reflection"]


class WeeklyReview(BaseModel):
    summary: str = Field(max_length=3000)
    wins: list[str] = Field(max_length=10)
    risks: list[str] = Field(max_length=10)
    suggestions: list[ReviewSuggestion] = Field(max_length=5)


def require_ai(user: User) -> IntegrationSettings:
    config = IntegrationSettings()
    if not config.ai_configured:
        raise HTTPException(
            503, detail={"code": "ai_unavailable", "message": "Coaching is not set up."}
        )
    if not getattr(user, "ai_enabled", True):
        raise HTTPException(
            403, detail={"code": "ai_disabled", "message": "Coaching is turned off in settings."}
        )
    return config


@coach_router.get("/status")
async def coach_status(user: Owner) -> dict[str, Json]:
    config = IntegrationSettings()
    return {
        "configured": config.ai_configured,
        "provider": config.llm_provider,
        "enabled": bool(getattr(user, "ai_enabled", True)),
    }


async def suggest(
    task: str, body: CoachInput, schema: type[Schema], db: AsyncSession, user: User
) -> Schema:
    config = require_ai(user)
    prompt = f"Task: {task}\n<user_data>{redact(body.text)}</user_data>"
    if body.include_context:
        prompt += "\n<computed_context>" + await server_context(db, user) + "</computed_context>"
    async with httpx.AsyncClient(timeout=45) as client:
        provider = get_provider(config, client)
        for attempt in range(2):
            # Meter validation retries as separate provider attempts.
            call = await reserve(db, user, task, config)
            started = time.monotonic()
            result: ProviderResult | None = None
            try:
                result = await provider.generate(
                    system=SYSTEM_PROMPT,
                    user=prompt,
                    schema=cast(dict[str, Json], schema.model_json_schema()),
                    max_tokens=config.llm_max_output_tokens,
                )
                try:
                    return schema.model_validate_json(result.text)
                except ValidationError:
                    if attempt:
                        raise AIUnavailable("The suggestion could not be checked.") from None
                    prompt += "\nReturn valid JSON matching the schema. Do not add other text."
            except (AIUnavailable, httpx.HTTPError, ValueError) as exc:
                raise HTTPException(
                    503,
                    detail={
                        "code": "ai_unavailable",
                        "message": (
                            "Coaching is unavailable. This attempt still counts toward your allowance."
                        ),
                    },
                ) from exc
            finally:
                await finish_call(db, call, result, time.monotonic() - started)
    raise HTTPException(
        503, detail={"code": "ai_unavailable", "message": "The suggestion could not be checked."}
    )


@coach_router.post("/goal-refine", response_model=GoalSuggestion)
async def refine(body: CoachInput, db: DB, user: Owner) -> GoalSuggestion:
    return await suggest("goal-refine", body, GoalSuggestion, db, user)


@coach_router.post("/suggest-actions", response_model=ActionSuggestions)
async def actions(body: CoachInput, db: DB, user: Owner) -> ActionSuggestions:
    return await suggest("suggest-actions", body, ActionSuggestions, db, user)


@coach_router.post("/suggest-obstacles", response_model=ObstacleSuggestions)
async def obstacles(body: CoachInput, db: DB, user: Owner) -> ObstacleSuggestions:
    return await suggest("suggest-obstacles", body, ObstacleSuggestions, db, user)


@coach_router.post("/weekly-review", response_model=WeeklyReview)
async def review(body: CoachInput, db: DB, user: Owner) -> WeeklyReview:
    return await suggest("weekly-review", body, WeeklyReview, db, user)


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatInput(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=20)
    include_context: bool = False


@coach_router.post("/chat")
async def chat(body: ChatInput, db: DB, user: Owner) -> StreamingResponse:
    config = require_ai(user)
    context = await server_context(db, user) if body.include_context else None
    call = await reserve(db, user, "chat", config)
    prompt = "\n".join(f"{m.role}: {redact(m.content)}" for m in body.messages)
    prompt = "<user_data>" + prompt + "</user_data>"
    if context is not None:
        prompt += "\n<computed_context>" + context + "</computed_context>"

    async def events() -> AsyncIterator[str]:
        started = time.monotonic()
        result: ProviderResult | None = None
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                provider = get_provider(config, client)
                async for chunk in provider.stream_text(
                    system=SYSTEM_PROMPT, user=prompt, max_tokens=config.llm_max_output_tokens
                ):
                    if chunk.text:
                        yield "data: " + json.dumps({"text": chunk.text}) + "\n\n"
                    else:
                        result = chunk
            yield "event: done\ndata: {}\n\n"
        except (AIUnavailable, httpx.HTTPError, ValueError):
            yield (
                "event: error\ndata: "
                + json.dumps(
                    {
                        "code": "ai_unavailable",
                        "message": (
                            "Coaching stopped. This request still counts toward your allowance."
                        ),
                    }
                )
                + "\n\n"
            )
        finally:
            await finish_call(db, call, result, time.monotonic() - started)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@coach_router.get("/usage")
async def usage(db: DB, user: Owner) -> dict[str, Json]:
    now = datetime.now(UTC)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month = day.replace(day=1)
    plan = await db.get(Plan, user.plan_id)
    calls = (
        await db.scalar(
            select(func.count())
            .select_from(AICall)
            .where(AICall.user_id == user.id, AICall.created_at >= day)
        )
        or 0
    )
    tokens = (
        await db.scalar(
            select(func.coalesce(func.sum(AICall.output_tokens), 0)).where(
                AICall.user_id == user.id, AICall.created_at >= month
            )
        )
        or 0
    )
    quotas = plan.quotas if plan else {}
    return {
        "plan": plan.name if plan else "",
        "calls_used": calls,
        "calls_limit": int(quotas.get("ai.calls", 10)),
        "output_tokens_used": int(tokens),
        "output_tokens_limit": int(quotas.get("ai.output_tokens", 20000)),
        "resets_at": (day + timedelta(days=1)).isoformat(),
    }
