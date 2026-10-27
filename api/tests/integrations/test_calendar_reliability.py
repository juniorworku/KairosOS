"""Calendar failures and recovery use an isolated database and controlled HTTP transport."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.integrations.calendar import FREEBUSY_SCOPE, WRITE_SCOPE, encrypt_token, stable_event_id
from app.integrations.models import CalendarBusy, CalendarConnection
from app.integrations.router import calendar_router, calendar_status, sync_user
from app.models.auth import User
from app.models.planning import PlanningRecord


@pytest.fixture
def calendar_client(auth_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    auth_app.include_router(calendar_router)
    with TestClient(auth_app) as client:
        yield client


def config_key() -> str:
    from app.integrations.config import IntegrationSettings

    return IntegrationSettings().token_encryption_key


def install_transport(monkeypatch: pytest.MonkeyPatch, handler: Any) -> None:
    import app.integrations.router as module

    original = httpx.AsyncClient

    def client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        return original(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(module.httpx, "AsyncClient", client)


def test_full_sync_reset_recovers_crash_write_and_preserves_google_move(
    calendar_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = calendar_client
    requests: list[dict[str, str]] = []
    ids: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "access"})
        if request.url.path.endswith("/freeBusy"):
            return httpx.Response(200, json={"calendars": {"primary": {"busy": []}}})
        params = dict(request.url.params)
        requests.append(params)
        if params.get("syncToken") == "expired" and "pageToken" not in params:
            return httpx.Response(
                200,
                json={
                    "items": [{"id": "moved", "status": "cancelled"}],
                    "nextPageToken": "old-page",
                },
            )
        if params.get("syncToken") == "expired":
            return httpx.Response(410, json={})
        if "pageToken" not in params:
            return httpx.Response(
                200,
                json={
                    "timeZone": "America/New_York",
                    "items": [
                        {
                            "id": "moved",
                            "status": "confirmed",
                            "start": {"dateTime": "2026-11-02T11:00:00-05:00"},
                            "end": {"dateTime": "2026-11-02T12:30:00-05:00"},
                        }
                    ],
                    "nextPageToken": "full-page",
                },
            )
        assert params["pageToken"] == "full-page"
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": stable_event_id(ids["crash"]),
                        "status": "confirmed",
                        "extendedProperties": {"private": {"kairos_block_id": ids["crash"]}},
                        "start": {"dateTime": "2026-11-03T09:00:00Z"},
                        "end": {"dateTime": "2026-11-03T10:00:00Z"},
                    }
                ],
                "nextSyncToken": "new-token",
            },
        )

    install_transport(monkeypatch, handler)

    async def run() -> None:
        factory = client.app.state.session_factory  # type: ignore[union-attr]
        async with factory() as db:
            owner = await db.scalar(select(User))
            assert owner
            user_id = owner.id
            owner.timezone = "America/New_York"
            db.add(
                CalendarConnection(
                    user_id=user_id,
                    scopes=[FREEBUSY_SCOPE, WRITE_SCOPE],
                    app_calendar_id="app",
                    sync_token="expired",
                    token_enc=encrypt_token({"refresh_token": "refresh"}, config_key()),
                )
            )
            for name, event_id, status in [
                ("moved", "moved", "completed"),
                ("missing", "missing", "published"),
                ("crash", None, "accepted"),
            ]:
                payload = {
                    "status": status,
                    "start_at": "2026-11-02T14:00:00+00:00",
                    "end_at": "2026-11-02T15:00:00+00:00",
                    "planned_minutes": 60,
                    "moved_count": 0,
                    "week_start": "2026-11-02",
                }
                if event_id:
                    payload["google_event_id"] = event_id
                row = PlanningRecord(user_id=user_id, kind="block", payload=payload)
                db.add(row)
                await db.flush()
                ids[name] = row.id
            await db.commit()
        async with factory() as db:
            await sync_user(db, user_id)
        async with factory() as db:
            moved = await db.get(PlanningRecord, ids["moved"])
            missing = await db.get(PlanningRecord, ids["missing"])
            recovered = await db.get(PlanningRecord, ids["crash"])
            assert moved and moved.payload["status"] == "completed"
            assert moved.payload["planned_minutes"] == 90
            assert moved.payload["moved_count"] == 1
            assert moved.payload["start_at"] == "2026-11-02T16:00:00+00:00"
            assert missing and missing.payload["status"] == "cancelled"
            assert recovered and recovered.payload["google_event_id"] == stable_event_id(
                ids["crash"]
            )
            assert recovered.payload["status"] == "published"
            connection = await db.scalar(select(CalendarConnection))
            assert connection and connection.sync_token == "new-token"

    assert client.portal
    client.portal.call(run)
    assert "pageToken" not in requests[2]
    assert "syncToken" not in requests[2]


def test_failed_later_page_rolls_back_availability_and_block_changes(
    calendar_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = calendar_client

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "access"})
        if request.url.path.endswith("/freeBusy"):
            return httpx.Response(200, json={"calendars": {"primary": {"busy": []}}})
        if "pageToken" not in request.url.params:
            return httpx.Response(
                200,
                json={
                    "items": [{"id": "event", "status": "cancelled"}],
                    "nextPageToken": "page-two",
                },
            )
        return httpx.Response(503, json={})

    install_transport(monkeypatch, handler)

    async def run() -> None:
        from app.integrations.calendar import CalendarUnavailable

        factory = client.app.state.session_factory  # type: ignore[union-attr]
        async with factory() as db:
            owner = await db.scalar(select(User))
            assert owner
            user_id = owner.id
            db.add(
                CalendarConnection(
                    user_id=user_id,
                    scopes=[FREEBUSY_SCOPE, WRITE_SCOPE],
                    app_calendar_id="app",
                    sync_token="old-token",
                    token_enc=encrypt_token({"refresh_token": "refresh"}, config_key()),
                )
            )
            db.add(
                CalendarBusy(
                    user_id=user_id,
                    start_at=datetime.now(UTC),
                    end_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
            block = PlanningRecord(
                user_id=user_id,
                kind="block",
                payload={"status": "published", "google_event_id": "event"},
            )
            db.add(block)
            await db.commit()
            block_id = block.id
        async with factory() as db:
            with pytest.raises(CalendarUnavailable):
                await sync_user(db, user_id)
        async with factory() as db:
            rows = list((await db.scalars(select(CalendarBusy))).all())
            assert len(rows) == 1
            stored = await db.get(PlanningRecord, block_id)
            assert stored and stored.payload["status"] == "published"
            connection = await db.scalar(select(CalendarConnection))
            assert connection and connection.sync_token == "old-token"
            assert connection.last_synced_at is None

    assert client.portal
    client.portal.call(run)


def test_readonly_sync_prunes_expired_busy_and_capabilities_are_honest(
    calendar_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = calendar_client
    seen: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "access"})
        assert request.url.path.endswith("/freeBusy")
        return httpx.Response(200, json={"calendars": {"primary": {"busy": []}}})

    install_transport(monkeypatch, handler)

    async def run() -> None:
        factory = client.app.state.session_factory  # type: ignore[union-attr]
        async with factory() as db:
            owner = await db.scalar(select(User))
            assert owner
            user_id = owner.id
            connection = CalendarConnection(
                user_id=user_id,
                scopes=[FREEBUSY_SCOPE],
                app_calendar_id="previous-app",
                token_enc=encrypt_token({"refresh_token": "refresh"}, config_key()),
            )
            db.add(connection)
            db.add(
                CalendarBusy(
                    user_id=user_id,
                    start_at=datetime.now(UTC) - timedelta(days=2),
                    end_at=datetime.now(UTC) - timedelta(days=1),
                )
            )
            await db.commit()
            assert (await calendar_status(db, owner))["can_publish"] is False
        async with factory() as db:
            await sync_user(db, user_id)
        async with factory() as db:
            assert list((await db.scalars(select(CalendarBusy))).all()) == []
            owner = await db.get(User, user_id)
            connection = await db.scalar(select(CalendarConnection))
            assert owner and connection
            connection.scopes = [FREEBUSY_SCOPE, WRITE_SCOPE]
            connection.status = "needs_reauth"
            await db.commit()
            assert (await calendar_status(db, owner))["can_publish"] is False
            connection.status = "active"
            await db.commit()
            assert (await calendar_status(db, owner))["can_publish"] is True
            monkeypatch.delenv("GOOGLE_CLIENT_SECRET")
            assert (await calendar_status(db, owner))["can_publish"] is False

    assert client.portal
    client.portal.call(run)
    assert not any(path.endswith("/events") for path in seen)


def test_disconnect_invalidates_pending_calendar_consent_before_any_provider_request(
    calendar_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import re
    from urllib.parse import parse_qs, urlsplit

    from app.integrations.models import CalendarState

    client = calendar_client

    def headers() -> dict[str, str]:
        return {"X-CSRF-Token": client.get("/api/v1/auth/csrf").json()["csrf_token"]}

    assert (
        client.post(
            "/api/v1/auth/magic/request", json={"email": "owner@example.test"}, headers=headers()
        ).status_code
        == 202
    )
    sender = client.app.state.email_sender  # type: ignore[union-attr]
    link = re.search(r"http://testserver/auth/confirm\?token=\S+", sender.messages[-1].text)
    assert link
    token = parse_qs(urlsplit(link.group()).query)["token"][0]
    assert (
        client.post(
            "/api/v1/auth/magic/verify", json={"token": token}, headers=headers()
        ).status_code
        == 200
    )
    consent = client.get("/api/v1/calendar/connect", follow_redirects=False)
    old_state = parse_qs(urlsplit(consent.headers["location"]).query)["state"][0]

    def unexpected_request(request: httpx.Request) -> httpx.Response:
        raise AssertionError("A disconnected consent must not reach Google")

    install_transport(monkeypatch, unexpected_request)
    assert client.post("/api/v1/calendar/disconnect", headers=headers()).status_code == 200
    assert (
        client.get(
            "/api/v1/calendar/callback", params={"state": old_state, "code": "stale-code"}
        ).status_code
        == 400
    )

    async def inspect() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            assert list((await db.scalars(select(CalendarState))).all()) == []

    assert client.portal
    client.portal.call(inspect)
