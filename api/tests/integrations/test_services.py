"""Provider contracts tested with transport fakes; never calls external services."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography.fernet import Fernet

from app.integrations.calendar import (
    FREEBUSY_SCOPE,
    WRITE_SCOPE,
    GoogleCalendar,
    challenge,
    decrypt_token,
    encrypt_token,
)
from app.integrations.coach import (
    AIUnavailable,
    AnthropicProvider,
    GoalSuggestion,
    ProviderResult,
    redact,
    structured,
)
from app.integrations.config import IntegrationSettings
from app.integrations.jsonutil import Json


def test_token_encryption_and_minimal_scopes() -> None:
    key = Fernet.generate_key().decode()
    value: dict[str, Json] = {"refresh_token": "sensitive-refresh-token"}
    encrypted = encrypt_token(value, key)
    assert b"sensitive-refresh-token" not in encrypted
    assert decrypt_token(encrypted, key) == value
    assert FREEBUSY_SCOPE.endswith("/calendar.events.freebusy")
    assert WRITE_SCOPE.endswith("/calendar.app.created")
    assert challenge("verifier") == challenge("verifier")
    assert "=" not in challenge("verifier")


def test_busy_read_never_requests_event_details() -> None:
    captured: list[httpx.Request] = []

    def transport(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "calendars": {
                    "primary": {
                        "busy": [{"start": "2026-10-28T09:00:00Z", "end": "2026-10-28T10:00:00Z"}]
                    }
                }
            },
        )

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            google = GoogleCalendar(IntegrationSettings(_env_file=None), client)
            intervals = await google.busy(
                "access", datetime(2026, 10, 28, tzinfo=UTC), datetime(2026, 10, 29, tzinfo=UTC)
            )
            assert len(intervals) == 1
            assert intervals[0][1] - intervals[0][0] == timedelta(hours=1)

    asyncio.run(run())
    assert captured[0].url.path.endswith("/freeBusy")
    assert "events" not in str(captured[0].url)
    assert json.loads(captured[0].content)["items"] == [{"id": "primary"}]


def test_publish_uses_stable_id_and_recovers_duplicate() -> None:
    seen: list[httpx.Request] = []

    def transport(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(409 if request.method == "POST" else 200, json={})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
            google = GoogleCalendar(IntegrationSettings(_env_file=None), client)
            first = await google.publish(
                "access",
                "app-calendar",
                "block-1",
                "Write",
                "2026-10-28T09:00:00Z",
                "2026-10-28T10:00:00Z",
            )
            second = await google.publish(
                "access",
                "app-calendar",
                "block-1",
                "Write",
                "2026-10-28T09:00:00Z",
                "2026-10-28T10:00:00Z",
            )
            assert first == second

    asyncio.run(run())
    assert [request.method for request in seen] == ["POST", "PUT", "POST", "PUT"]
    assert all("/calendars/app-calendar/events" in str(request.url) for request in seen)
    body = json.loads(seen[0].content)
    assert body["extendedProperties"]["private"]["kairos_block_id"] == "block-1"


class FakeProvider:
    def __init__(self, values: list[str]) -> None:
        self.values = values
        self.calls = 0

    async def generate(
        self, *, system: str, user: str, schema: dict[str, Json] | None, max_tokens: int
    ) -> ProviderResult:
        self.calls += 1
        assert "user_data" in user
        assert schema is not None
        return ProviderResult(text=self.values.pop(0), output_tokens=10)

    async def stream_text(self, *, system: str, user: str, max_tokens: int):  # type: ignore[no-untyped-def]
        yield ProviderResult(text="A useful next step.")


def test_structured_suggestion_retries_once_and_checks_schema() -> None:
    valid = json.dumps(
        {
            "outcome_statement": "Draft a chapter",
            "metric_name": "Pages",
            "metric_unit": "pages",
            "suggested_target": 20,
            "clarifying_questions": [],
        }
    )
    provider = FakeProvider(["not json", valid])
    result, _ = asyncio.run(
        structured(provider, "<user_data>Write</user_data>", GoalSuggestion, 100)
    )
    assert result.suggested_target == 20
    assert provider.calls == 2
    bad = FakeProvider(["{}", "{}"])
    with pytest.raises(AIUnavailable):
        asyncio.run(structured(bad, "<user_data>Write</user_data>", GoalSuggestion, 100))
    assert bad.calls == 2


def test_anthropic_stream_parses_deltas_and_usage() -> None:
    events = [
        {"type": "message_start", "message": {"usage": {"input_tokens": 3}}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Start small."}},
        {"type": "message_delta", "usage": {"output_tokens": 4}},
    ]
    content = "".join("data: " + json.dumps(item) + "\n\n" for item in events)

    async def run() -> list[ProviderResult]:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, text=content))
        ) as client:
            provider = AnthropicProvider(
                IntegrationSettings(
                    anthropic_api_key="test", anthropic_model="configured-model", _env_file=None
                ),
                client,
            )
            return [
                item
                async for item in provider.stream_text(system="safe", user="data", max_tokens=20)
            ]

    parts = asyncio.run(run())
    assert parts[0].text == "Start small."
    assert parts[-1].input_tokens == 3
    assert parts[-1].output_tokens == 4


def test_redaction_omits_links_and_emails() -> None:
    value = redact("Contact me@example.test or see https://example.test/private?token=secret")
    assert "me@example.test" not in value
    assert "token=secret" not in value
    assert "[email]" in value
    assert "[link]" in value


def test_truncated_provider_stream_does_not_report_zero_confirmed_usage() -> None:
    event = {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Partial"}}
    content = "data: " + json.dumps(event) + "\n\n"

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, text=content))
        ) as client:
            provider = AnthropicProvider(
                IntegrationSettings(
                    anthropic_api_key="test", anthropic_model="configured-model", _env_file=None
                ),
                client,
            )
            stream = provider.stream_text(system="safe", user="data", max_tokens=20)
            first = await anext(stream)
            assert first.text == "Partial"
            assert first.output_tokens is None
            with pytest.raises(AIUnavailable):
                await anext(stream)

    asyncio.run(run())
