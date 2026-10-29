"""Controlled Google transport: selection, owned ACL, conditional writes and retry identity."""

import json
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_unified_agenda import agenda_client, csrf, key, login, transport_for  # noqa: F401, F811

from app.integrations.calendar import (
    DETAIL_SCOPE,
    EDIT_SCOPE,
    FREEBUSY_SCOPE,
    LIST_SCOPE,
    encrypt_token,
)
from app.integrations.models import CalendarConnection, CalendarSelection


def test_selection_and_conditional_event_lifecycle(
    agenda_client: TestClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = agenda_client
    user = login(client)
    state: dict[str, Any] = {"etag": '"1"'}
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "test-access"})
        if request.url.path.endswith("/calendarList"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "owned@example.test",
                            "summary": "Owned",
                            "timeZone": "UTC",
                            "accessRole": "owner",
                            "primary": True,
                        },
                        {
                            "id": "shared@example.test",
                            "summary": "Shared",
                            "timeZone": "UTC",
                            "accessRole": "reader",
                        },
                    ]
                },
            )
        if request.url.path.endswith("/freeBusy"):
            body = json.loads(request.content)
            assert {item["id"] for item in body["items"]} == {
                "owned@example.test",
                "shared@example.test",
            }
            return httpx.Response(
                200, json={"calendars": {item["id"]: {"busy": []} for item in body["items"]}}
            )
        if request.method == "POST":
            payload = json.loads(request.content)
            if "event" in state:
                return httpx.Response(409, json={})
            state["event"] = {**payload, "etag": state["etag"], "status": "confirmed"}
            return httpx.Response(200, json=state["event"])
        if request.method == "GET":
            return httpx.Response(200, json=state["event"])
        assert request.headers["If-Match"] == state["etag"]
        if request.method == "PATCH":
            if state.pop("force_412", False):
                return httpx.Response(412, json={})
            state["etag"] = '"2"'
            state["event"] = {
                **state["event"],
                **json.loads(request.content),
                "etag": state["etag"],
            }
            return httpx.Response(200, json=state["event"])
        return httpx.Response(204)

    transport_for(monkeypatch, handler)

    async def seed() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            db.add(
                CalendarConnection(
                    user_id=user["id"],
                    token_enc=encrypt_token({"refresh_token": "test-refresh"}, key()),
                    scopes=[FREEBUSY_SCOPE, DETAIL_SCOPE, EDIT_SCOPE, LIST_SCOPE],
                    details_enabled=True,
                    editing_enabled=True,
                )
            )
            await db.commit()

    assert client.portal
    client.portal.call(seed)
    listed = client.get("/api/v1/calendar/calendars")
    assert listed.status_code == 200, listed.text
    shared = listed.json()["calendars"][1]
    assert shared["can_select"] and not shared["can_read"] and not shared["can_write"]
    selected = client.put(
        "/api/v1/calendar/calendars",
        json={"calendar_ids": ["owned@example.test", "shared@example.test"]},
        headers=csrf(client),
    )
    assert selected.status_code == 200, selected.text
    body = {
        "calendar_id": "owned@example.test",
        "title": "Meeting",
        "notes": "Notes",
        "start_at": "2026-11-02T09:00:00Z",
        "end_at": "2026-11-02T10:00:00Z",
        "timezone": "UTC",
        "all_day": False,
    }
    creation = {**body, "client_event_id": str(uuid4())}
    created = client.post("/api/v1/calendar/events", json=creation, headers=csrf(client))
    assert created.status_code == 200, created.text
    identifier = created.json()["source_id"]
    assert created.json()["etag"] == '"1"'
    replay = client.post("/api/v1/calendar/events", json=creation, headers=csrf(client))
    assert replay.status_code == 200 and replay.json()["source_id"] == identifier
    changed = client.patch(
        f"/api/v1/calendar/events/{identifier}",
        json={**body, "title": "Changed", "etag": '"1"'},
        headers=csrf(client),
    )
    assert changed.status_code == 200 and changed.json()["etag"] == '"2"'
    stale = client.patch(
        f"/api/v1/calendar/events/{identifier}", json={**body, "etag": '"1"'}, headers=csrf(client)
    )
    assert stale.status_code == 409
    state["force_412"] = True
    raced = client.patch(
        f"/api/v1/calendar/events/{identifier}", json={**body, "etag": '"2"'}, headers=csrf(client)
    )
    assert raced.status_code == 409 and raced.json()["detail"]["code"] == "calendar_stale"
    state["event"]["recurrence"] = ["RRULE:FREQ=WEEKLY"]
    master = client.patch(
        f"/api/v1/calendar/events/{identifier}", json={**body, "etag": '"2"'}, headers=csrf(client)
    )
    assert master.status_code == 422
    state["event"].pop("recurrence")
    denied = client.post(
        "/api/v1/calendar/events",
        json={**creation, "calendar_id": "shared@example.test"},
        headers=csrf(client),
    )
    assert denied.status_code == 403
    deleted = client.delete(
        f"/api/v1/calendar/events/{identifier}",
        params={"calendar_id": body["calendar_id"], "etag": '"2"'},
        headers=csrf(client),
    )
    assert deleted.status_code == 204

    async def persisted() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            rows = list((await db.scalars(select(CalendarSelection))).all())
            assert len(rows) == 2 and all(row.selected for row in rows)
            assert all(b"Owned" not in row.metadata_enc for row in rows)

    client.portal.call(persisted)


def test_all_day_requires_local_midnight() -> None:
    from pydantic import ValidationError

    from app.integrations.multi_calendar import EventInput

    with pytest.raises(ValidationError):
        EventInput(
            calendar_id="x",
            title="x",
            start_at="2026-11-02T09:00:00Z",
            end_at="2026-11-03T09:00:00Z",
            timezone="UTC",
            all_day=True,
        )
    event = EventInput(
        calendar_id="x",
        title="x",
        start_at="2026-11-01T04:00:00Z",
        end_at="2026-11-02T05:00:00Z",
        timezone="America/New_York",
        all_day=True,
    )
    assert event.provider_body()["start"] == {"date": "2026-11-01"}
    assert event.provider_body()["end"] == {"date": "2026-11-02"}


def test_calendar_capability_envelope_before_consent(agenda_client: TestClient) -> None:  # noqa: F811
    login(agenda_client)
    response = agenda_client.get("/api/v1/calendar/calendars")
    assert response.status_code == 200
    assert response.json() == {
        "configured": True,
        "connected": False,
        "selection_enabled": False,
        "write_enabled": False,
        "calendars": [],
    }


@pytest.mark.anyio
async def test_busy_union_rejects_partial_provider_failure() -> None:
    from datetime import UTC, datetime, timedelta

    from app.integrations.calendar import CalendarUnavailable, GoogleCalendar
    from app.integrations.config import IntegrationSettings

    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        return httpx.Response(
            200,
            json={"calendars": {"one": {"busy": []}, "two": {"errors": [{"reason": "notFound"}]}}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        google = GoogleCalendar(IntegrationSettings(), client)
        now = datetime.now(UTC)
        with pytest.raises(CalendarUnavailable):
            await google.busy("fake", now, now + timedelta(days=1), ["one", "two"])
    assert seen[0]["items"] == [{"id": "one"}, {"id": "two"}]


@pytest.mark.anyio
async def test_provider_conditional_modification_is_not_retried() -> None:
    from app.integrations.calendar import CalendarHTTPError, GoogleCalendar
    from app.integrations.config import IntegrationSettings

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers["If-Match"] == '"old"'
        return httpx.Response(412, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        google = GoogleCalendar(IntegrationSettings(), client)
        with pytest.raises(CalendarHTTPError) as caught:
            await google.request(
                "PATCH",
                "/calendars/x/events/y",
                "fake",
                {"summary": "New"},
                headers={"If-Match": '"old"'},
                retry_safe=False,
            )
        assert caught.value.status_code == 412
    assert calls == 1


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_selected_owned_details_identity_and_explicit_edit_consent(
    agenda_client: TestClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.models.planning import PlanningRecord

    client = agenda_client
    user = login(client)
    sources: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "test-access"})
        assert request.method == "GET"
        sources.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "summary": "Source",
                "timeZone": "UTC",
                "items": [
                    {
                        "id": "same-provider-id",
                        "etag": '"v1"',
                        "summary": "Named event",
                        "status": "confirmed",
                        "start": {"dateTime": "2026-11-02T09:00:00Z"},
                        "end": {"dateTime": "2026-11-02T10:00:00Z"},
                    }
                ],
            },
        )

    transport_for(monkeypatch, handler)

    async def seed() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            db.add(
                CalendarConnection(
                    user_id=user["id"],
                    token_enc=encrypt_token({"refresh_token": "fake"}, key()),
                    scopes=[FREEBUSY_SCOPE, DETAIL_SCOPE, EDIT_SCOPE, LIST_SCOPE],
                    details_enabled=True,
                    selection_enabled=True,
                    editing_enabled=False,
                )
            )
            for identifier, role in [
                ("one", "owner"),
                ("two", "owner"),
                ("shared", "reader"),
                ("excluded", "owner"),
            ]:
                db.add(
                    CalendarSelection(
                        user_id=user["id"],
                        calendar_id=identifier,
                        access_role=role,
                        selected=identifier != "excluded",
                        metadata_enc=encrypt_token(
                            {"name": identifier, "timezone": "UTC", "primary": identifier == "one"},
                            key(),
                        ),
                    )
                )
            db.add(
                PlanningRecord(
                    user_id=user["id"],
                    kind="block",
                    payload={
                        "title": "Goal block",
                        "status": "published",
                        "google_event_id": "same-provider-id",
                        "google_calendar_id": "one",
                        "start_at": "2026-11-02T09:00:00Z",
                        "end_at": "2026-11-02T10:00:00Z",
                    },
                )
            )
            await db.commit()

    assert client.portal
    client.portal.call(seed)
    response = client.get("/api/v1/agenda?start=2026-11-02&end=2026-11-03")
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 2
    google = next(row for row in rows if row["source"] == "google")
    assert google["calendar_id"] == "two" and google["etag"] == '"v1"'
    assert not google["editable"]
    assert set(sources) == {
        "/calendar/v3/calendars/one/events",
        "/calendar/v3/calendars/two/events",
    }
    # Returning a previously granted scope alone is not explicit app consent to writes.
    denied = client.post(
        "/api/v1/calendar/events",
        json={
            "calendar_id": "one",
            "client_event_id": str(uuid4()),
            "title": "Denied",
            "start_at": "2026-11-02T09:00:00Z",
            "end_at": "2026-11-02T10:00:00Z",
            "timezone": "UTC",
        },
        headers=csrf(client),
    )
    assert denied.status_code == 403
