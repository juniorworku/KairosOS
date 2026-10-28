"""Unified local/Google feed with explicit consent and controlled provider responses."""

import re
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.integrations.calendar import DETAIL_SCOPE, FREEBUSY_SCOPE, decrypt_token, encrypt_token
from app.integrations.models import CalendarConnection, GoogleEventCache
from app.integrations.router import agenda_router, calendar_router
from app.models.auth import User
from app.models.planning import PlanningRecord
from app.routers.agenda import router as local_router


@pytest.fixture
def agenda_client(auth_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    auth_app.include_router(calendar_router)
    auth_app.include_router(local_router)
    auth_app.include_router(agenda_router)
    with TestClient(auth_app) as client:
        yield client


def key() -> str:
    from app.integrations.config import IntegrationSettings

    return IntegrationSettings().token_encryption_key


def csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/v1/auth/csrf").json()["csrf_token"]}


def login(client: TestClient) -> dict[str, Any]:
    assert (
        client.post(
            "/api/v1/auth/magic/request", json={"email": "owner@example.test"}, headers=csrf(client)
        ).status_code
        == 202
    )
    sender = client.app.state.email_sender  # type: ignore[union-attr]
    match = re.search(r"http://testserver/auth/confirm\?token=\S+", sender.messages[-1].text)
    assert match
    token = parse_qs(urlsplit(match.group()).query)["token"][0]
    result = client.post("/api/v1/auth/magic/verify", json={"token": token}, headers=csrf(client))
    assert result.status_code == 200
    return result.json()


def transport_for(monkeypatch: pytest.MonkeyPatch, handler: Any) -> None:
    import app.integrations.router as module

    original = httpx.AsyncClient

    def client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        return original(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(module.httpx, "AsyncClient", client)


def add_local(client: TestClient) -> dict[str, Any]:
    result = client.post(
        "/api/v1/events",
        json={
            "title": "Local dinner",
            "notes": "Bring a book",
            "start_at": "2026-11-02T18:00:00Z",
            "end_at": "2026-11-02T19:00:00Z",
            "timezone": "UTC",
        },
        headers=csrf(client),
    )
    assert result.status_code == 201, result.text
    return result.json()


@pytest.mark.parametrize("explicit", [False, True])
def test_google_details_require_separate_explicit_app_consent(
    agenda_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    explicit: bool,
) -> None:
    client = agenda_client
    login(client)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        assert request.url.host == "oauth2.googleapis.com"
        # Google may return a previously granted scope; the app must still require its own opt-in.
        return httpx.Response(
            200,
            json={
                "access_token": "access",
                "refresh_token": "refresh",
                "scope": FREEBUSY_SCOPE + " " + DETAIL_SCOPE,
            },
        )

    transport_for(monkeypatch, handler)
    consent = client.get(
        "/api/v1/calendar/connect",
        params={"details": str(explicit).lower()},
        follow_redirects=False,
    )
    params = parse_qs(urlsplit(consent.headers["location"]).query)
    assert (DETAIL_SCOPE in params["scope"][0].split()) is explicit
    response = client.get(
        "/api/v1/calendar/callback",
        params={"state": params["state"][0], "code": "test"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    status = client.get("/api/v1/calendar/status").json()
    assert status["details_enabled"] is explicit
    assert status["can_read_events"] is explicit
    assert seen == ["/token"]


def test_unified_feed_includes_named_timed_all_day_recurring_and_local_events(
    agenda_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = agenda_client
    user = login(client)
    add_local(client)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "access"})
        assert request.method == "GET" and request.url.path.endswith("/calendars/primary/events")
        assert request.url.params["singleEvents"] == "true"
        assert request.url.params["showDeleted"] == "false"
        assert "timeMin" in request.url.params and "timeMax" in request.url.params
        if "pageToken" not in request.url.params:
            return httpx.Response(
                200,
                json={
                    "summary": "Personal calendar",
                    "timeZone": "UTC",
                    "items": [
                        {
                            "id": "weekly_20261102",
                            "status": "confirmed",
                            "summary": "Weekly planning",
                            "description": "Review the notebook",
                            "recurringEventId": "weekly",
                            "originalStartTime": {"dateTime": "2026-11-02T09:00:00Z"},
                            "start": {"dateTime": "2026-11-02T09:00:00Z"},
                            "end": {"dateTime": "2026-11-02T10:00:00Z"},
                        }
                    ],
                    "nextPageToken": "second",
                },
            )
        return httpx.Response(
            200,
            json={
                "timeZone": "UTC",
                "items": [
                    {
                        "id": "holiday",
                        "status": "confirmed",
                        "summary": "Family visit",
                        "description": "Private note",
                        "start": {"date": "2026-11-03"},
                        "end": {"date": "2026-11-04"},
                    },
                    {
                        "id": "linked-event",
                        "status": "confirmed",
                        "summary": "Duplicate goal block",
                        "start": {"dateTime": "2026-11-02T11:00:00Z"},
                        "end": {"dateTime": "2026-11-02T12:00:00Z"},
                    },
                ],
            },
        )

    transport_for(monkeypatch, handler)

    async def prepare() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            db.add(
                CalendarConnection(
                    user_id=user["id"],
                    details_enabled=True,
                    scopes=[FREEBUSY_SCOPE, DETAIL_SCOPE],
                    token_enc=encrypt_token({"refresh_token": "refresh"}, key()),
                )
            )
            db.add(
                PlanningRecord(
                    user_id=user["id"],
                    kind="block",
                    payload={
                        "title": "Owned focus",
                        "status": "published",
                        "google_event_id": "linked-event",
                        "start_at": "2026-11-02T11:00:00+00:00",
                        "end_at": "2026-11-02T12:00:00+00:00",
                    },
                )
            )
            await db.commit()

    assert client.portal
    client.portal.call(prepare)
    response = client.get("/api/v1/agenda?start=2026-11-02&end=2026-11-09")
    assert response.status_code == 200, response.text
    rows = response.json()
    assert {row["source"] for row in rows} == {"local", "block", "google"}
    assert len(rows) == 4
    google = [row for row in rows if row["source"] == "google"]
    assert {row["title"] for row in google} == {"Weekly planning", "Family visit"}
    assert all(not row["editable"] and row["calendar_id"] == "primary" for row in google)
    recurring = next(row for row in google if row["recurring"])
    assert recurring["occurrence_date"] == "2026-11-02"
    assert recurring["notes"] == "Review the notebook"
    holiday = next(row for row in google if row["all_day"])
    assert holiday["start_at"] == "2026-11-03" and holiday["end_at"] == "2026-11-04"

    async def inspect() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            cached = list((await db.scalars(select(GoogleEventCache))).all())
            assert len(cached) == 3
            for row in cached:
                assert b"Private note" not in row.details_enc
                assert b"Weekly planning" not in row.details_enc
            assert any(
                decrypt_token(row.details_enc, key()).get("title") == "Family visit"
                for row in cached
            )
            connection = await db.scalar(select(CalendarConnection))
            assert connection and connection.details_from == date(2026, 11, 2)
            assert connection.details_to == date(2026, 11, 9)

    client.portal.call(inspect)
    count = len(requests)
    assert client.get("/api/v1/agenda?start=2026-11-02&end=2026-11-09").status_code == 200
    assert len(requests) == count, "Fresh covered ranges must use the cache"


def test_availability_only_never_reads_event_details_and_local_feed_works(
    agenda_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = agenda_client
    user = login(client)
    add_local(client)

    def unexpected(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Availability-only consent cannot fetch event details")

    transport_for(monkeypatch, unexpected)

    async def prepare() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            db.add(
                CalendarConnection(
                    user_id=user["id"],
                    scopes=[FREEBUSY_SCOPE],
                    token_enc=encrypt_token({"refresh_token": "refresh"}, key()),
                )
            )
            await db.commit()

    assert client.portal
    client.portal.call(prepare)
    response = client.get("/api/v1/agenda?start=2026-11-02&end=2026-11-09")
    assert response.status_code == 200
    assert [row["title"] for row in response.json()] == ["Local dinner"]
    assert client.get("/api/v1/agenda?start=2026-11-09&end=2026-11-02").status_code == 422
    assert client.get("/api/v1/agenda?start=2026-01-01&end=2028-01-01").status_code == 422


def test_outage_preserves_owned_cache_and_local_events_then_opt_out_purges_details(
    agenda_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = agenda_client
    user = login(client)
    add_local(client)

    def failure(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "access"})
        return httpx.Response(503, json={})

    transport_for(monkeypatch, failure)

    async def prepare() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            owner = await db.get(User, user["id"])
            assert owner
            other = User(email="other@example.test", plan_id=owner.plan_id)
            db.add(other)
            await db.flush()
            db.add(
                CalendarConnection(
                    user_id=owner.id,
                    details_enabled=True,
                    scopes=[FREEBUSY_SCOPE, DETAIL_SCOPE],
                    token_enc=encrypt_token({"refresh_token": "refresh"}, key()),
                    details_from=date(2026, 11, 2),
                    details_to=date(2026, 11, 9),
                    details_timezone="UTC",
                    details_synced_at=datetime.now(UTC) - timedelta(hours=1),
                )
            )
            for identity, title in [
                (owner.id, "Saved appointment"),
                (other.id, "Other user secret"),
            ]:
                db.add(
                    GoogleEventCache(
                        user_id=identity,
                        calendar_id="primary",
                        provider_event_id="cached",
                        start_at=datetime(2026, 11, 2, 9, tzinfo=UTC),
                        end_at=datetime(2026, 11, 2, 10, tzinfo=UTC),
                        all_day=False,
                        timezone="UTC",
                        recurring=False,
                        details_enc=encrypt_token(
                            {"title": title, "notes": "", "status": "confirmed"}, key()
                        ),
                    )
                )
            await db.commit()

    assert client.portal
    client.portal.call(prepare)
    response = client.get("/api/v1/agenda?start=2026-11-02&end=2026-11-09")
    assert response.status_code == 200
    assert response.headers["X-Calendar-Status"] == "unavailable"
    assert {row["title"] for row in response.json()} == {"Local dinner", "Saved appointment"}
    assert client.get("/api/v1/calendar/status").json()["details_error"]
    assert client.delete("/api/v1/calendar/details", headers=csrf(client)).status_code == 200
    rows = client.get("/api/v1/agenda?start=2026-11-02&end=2026-11-09").json()
    assert [row["title"] for row in rows] == ["Local dinner"]
    assert client.get("/api/v1/calendar/status").json()["details_enabled"] is False

    async def inspect() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            rows = list((await db.scalars(select(GoogleEventCache))).all())
            assert len(rows) == 1 and rows[0].user_id != user["id"]

    client.portal.call(inspect)


def test_optional_detail_failure_does_not_rollback_successful_availability_sync(
    agenda_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.integrations.models import CalendarBusy
    from app.integrations.router import sync_user

    client = agenda_client
    user = login(client)
    start = datetime.now(UTC) + timedelta(hours=3)
    end = start + timedelta(hours=1)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "access"})
        if request.url.path.endswith("/freeBusy"):
            return httpx.Response(
                200,
                json={
                    "calendars": {
                        "primary": {"busy": [{"start": start.isoformat(), "end": end.isoformat()}]}
                    }
                },
            )
        assert request.url.path.endswith("/calendars/primary/events")
        return httpx.Response(403, json={"error": {"message": "Controlled permission failure"}})

    transport_for(monkeypatch, handler)

    async def run() -> None:
        factory = client.app.state.session_factory  # type: ignore[union-attr]
        async with factory() as db:
            db.add(
                CalendarConnection(
                    user_id=user["id"],
                    scopes=[FREEBUSY_SCOPE, DETAIL_SCOPE],
                    details_enabled=True,
                    token_enc=encrypt_token({"refresh_token": "refresh"}, key()),
                )
            )
            db.add(
                CalendarBusy(
                    user_id=user["id"],
                    start_at=datetime.now(UTC),
                    end_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
            await db.commit()
        async with factory() as db:
            await sync_user(db, user["id"])
        async with factory() as db:
            rows = list((await db.scalars(select(CalendarBusy))).all())
            assert len(rows) == 1 and rows[0].start_at == start
            connection = await db.scalar(select(CalendarConnection))
            assert connection and connection.last_synced_at
            assert connection.details_error
            assert connection.details_from is None

    assert client.portal
    client.portal.call(run)
