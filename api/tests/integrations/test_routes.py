"""Database-backed ownership, pairing, and quota boundary checks."""

import asyncio
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.integrations.coach import coach_router, reserve
from app.integrations.config import IntegrationSettings
from app.integrations.models import AICall, ExtensionToken
from app.integrations.router import calendar_router, ext_router
from app.models.auth import Plan, User
from app.models.planning import PlanningRecord


@pytest.fixture
def integration_client(auth_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    import app.integrations.router as module

    async def no_limit(request: object) -> None:
        pass

    monkeypatch.setattr(module, "redeem_rate_limit", no_limit)
    auth_app.include_router(calendar_router)
    auth_app.include_router(ext_router)
    auth_app.include_router(coach_router)
    with TestClient(auth_app) as client:
        yield client


def csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/v1/auth/csrf").json()["csrf_token"]}


def login(client: TestClient) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/magic/request", json={"email": "owner@example.test"}, headers=csrf(client)
    )
    assert response.status_code == 202
    sender = client.app.state.email_sender  # type: ignore[union-attr]
    match = re.search(r"http://testserver/auth/confirm\?token=\S+", sender.messages[-1].text)
    assert match
    token = parse_qs(urlsplit(match.group()).query)["token"][0]
    response = client.post("/api/v1/auth/magic/verify", json={"token": token}, headers=csrf(client))
    assert response.status_code == 200
    return response.json()


def test_unconfigured_integrations_are_honest_and_authenticated(
    integration_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = integration_client
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert client.get("/api/v1/calendar/status").status_code == 401
    login(client)
    assert client.get("/api/v1/calendar/status").json()["configured"] is False
    assert client.get("/api/v1/calendar/connect", follow_redirects=False).status_code == 503
    assert (
        client.post(
            "/api/v1/coach/chat",
            json={"messages": [{"role": "user", "content": "Help"}]},
            headers=csrf(client),
        ).status_code
        == 503
    )
    assert client.post("/api/v1/ext/pair").status_code == 403


def test_pair_code_single_use_hash_only_and_extension_only(integration_client: TestClient) -> None:
    client = integration_client
    login(client)
    pair = client.post("/api/v1/ext/pair", headers=csrf(client))
    assert pair.status_code == 200
    body = {"code": pair.json()["code"]}
    redeemed = client.post("/api/v1/ext/pair/redeem", json=body)
    assert redeemed.status_code == 200
    token = redeemed.json()["token"]
    assert client.post("/api/v1/ext/pair/redeem", json=body).status_code == 400

    async def check_hash() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            row = await db.scalar(select(ExtensionToken))
            assert row is not None
            assert token not in row.__dict__.values()

    assert client.portal
    client.portal.call(check_hash)
    client.cookies.clear()
    headers = {"Authorization": "Bearer " + token}
    assert client.get("/api/v1/ext/state", headers=headers).status_code == 200
    assert client.get("/api/v1/me", headers=headers).status_code == 401
    assert client.get("/api/v1/ext/tokens", headers=headers).status_code == 401


def test_extension_state_owns_focus_and_revoke_stops_access(integration_client: TestClient) -> None:
    client = integration_client
    user = login(client)
    pair = client.post("/api/v1/ext/pair", headers=csrf(client)).json()
    token = client.post("/api/v1/ext/pair/redeem", json={"code": pair["code"]}).json()["token"]

    async def create_focus() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            db.add(
                PlanningRecord(
                    user_id=user["id"],
                    kind="focus",
                    payload={
                        "started_at": datetime.now(UTC).isoformat(),
                        "ends_at": (datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
                        "ended_at": None,
                        "planned_minutes": 30,
                        "title": "Write",
                    },
                )
            )
            db.add(
                PlanningRecord(
                    user_id=user["id"],
                    kind="blocklist",
                    payload={"domains": ["example.com"], "is_default": True},
                )
            )
            await db.commit()

    assert client.portal
    client.portal.call(create_focus)
    headers = {"Authorization": "Bearer " + token}
    state = client.get("/api/v1/ext/state", headers=headers)
    assert state.json()["blocklist"] == ["example.com"]
    assert state.json()["active_session"]["title"] == "Write"
    assert (
        client.post("/api/v1/ext/event", json={"type": "pause"}, headers=headers).status_code == 200
    )
    assert client.get("/api/v1/ext/state", headers=headers).json()["pause_until"]
    row = client.get("/api/v1/ext/tokens").json()[0]
    assert client.delete("/api/v1/ext/tokens/" + row["id"], headers=csrf(client)).status_code == 200
    assert client.get("/api/v1/ext/state", headers=headers).status_code == 401


def test_quota_reservation_exact_boundary_and_global_cap(integration_client: TestClient) -> None:
    client = integration_client
    user = login(client)

    async def run() -> None:
        factory = client.app.state.session_factory  # type: ignore[union-attr]
        async with factory() as db:
            owner = await db.get(User, user["id"])
            assert owner
            plan = await db.get(Plan, owner.plan_id)
            assert plan
            plan.quotas = {"ai.calls": 1, "ai.output_tokens": 10000, "ai.chat_messages": 2}
            await db.commit()

        async def reserve_once() -> bool:
            async with factory() as db:
                owner = await db.get(User, user["id"])
                assert owner
                try:
                    await reserve(db, owner, "chat", IntegrationSettings(_env_file=None))
                    return True
                except HTTPException as error:
                    assert error.status_code == 429
                    return False

        results = await asyncio.gather(reserve_once(), reserve_once())
        assert sorted(results) == [False, True]
        async with factory() as db:
            owner = await db.get(User, user["id"])
            assert owner
            with pytest.raises(HTTPException) as error:
                await reserve(
                    db,
                    owner,
                    "chat",
                    IntegrationSettings(global_ai_daily_call_cap=1, _env_file=None),
                )
            assert error.value.status_code == 503
            calls = list((await db.scalars(select(AICall))).all())
            assert len(calls) == 1

    assert client.portal
    client.portal.call(run)


def configure_calendar(monkeypatch: pytest.MonkeyPatch) -> str:
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", key)
    return key


def test_calendar_consent_uses_minimal_scopes_and_hashed_state(
    integration_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.integrations.calendar import FREEBUSY_SCOPE, WRITE_SCOPE
    from app.integrations.models import CalendarState
    from app.integrations.router import digest

    client = integration_client
    configure_calendar(monkeypatch)
    login(client)
    response = client.get("/api/v1/calendar/connect", follow_redirects=False)
    params = parse_qs(urlsplit(response.headers["location"]).query)
    assert params["scope"] == [FREEBUSY_SCOPE]
    assert params["code_challenge_method"] == ["S256"]
    raw_state = params["state"][0]

    async def inspect_state() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            row = await db.scalar(select(CalendarState))
            assert row
            assert row.token_hash == digest(raw_state)
            assert raw_state not in row.__dict__.values()

    assert client.portal
    client.portal.call(inspect_state)
    write = client.get("/api/v1/calendar/connect?write=true", follow_redirects=False)
    assert set(parse_qs(urlsplit(write.headers["location"]).query)["scope"][0].split()) == {
        FREEBUSY_SCOPE,
        WRITE_SCOPE,
    }
    assert client.get("/api/v1/calendar/callback?state=forged&code=bad").status_code == 400


def test_calendar_publish_requires_prior_acceptance_and_owns_records(
    integration_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.integrations.calendar import FREEBUSY_SCOPE, WRITE_SCOPE, encrypt_token
    from app.integrations.models import CalendarBusy, CalendarConnection

    client = integration_client
    key = configure_calendar(monkeypatch)
    user = login(client)
    ids: list[str] = []

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
                    token_enc=encrypt_token({"refresh_token": "test"}, key),
                    scopes=[FREEBUSY_SCOPE, WRITE_SCOPE],
                    app_calendar_id="own-calendar",
                )
            )
            own_block = PlanningRecord(
                user_id=owner.id, kind="block", payload={"status": "proposed"}
            )
            other_block = PlanningRecord(
                user_id=other.id, kind="block", payload={"status": "accepted"}
            )
            db.add_all([own_block, other_block])
            db.add(
                CalendarBusy(
                    user_id=other.id,
                    start_at=datetime.now(UTC),
                    end_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
            await db.commit()
            ids.extend([own_block.id, other_block.id])

    assert client.portal
    client.portal.call(prepare)
    assert (
        client.post(
            "/api/v1/calendar/publish", json={"block_ids": [ids[0]]}, headers=csrf(client)
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/calendar/publish", json={"block_ids": [ids[1]]}, headers=csrf(client)
        ).status_code
        == 404
    )
    assert client.get("/api/v1/calendar/busy").json() == []


def test_coach_stream_uses_provider_deltas_records_usage_and_respects_ai_off(
    integration_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.integrations.coach as module
    from app.integrations.coach import ProviderResult
    from app.integrations.jsonutil import Json

    class Provider:
        async def generate(
            self, *, system: str, user: str, schema: dict[str, Json] | None, max_tokens: int
        ) -> ProviderResult:
            return ProviderResult(text="{}")

        async def stream_text(self, *, system: str, user: str, max_tokens: int):  # type: ignore[no-untyped-def]
            assert "computed_context" not in user
            yield ProviderResult(text="Choose one ")
            yield ProviderResult(text="action.")
            yield ProviderResult(text="", input_tokens=20, output_tokens=4)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "configured-model")
    monkeypatch.setattr(module, "get_provider", lambda config, client: Provider())
    client = integration_client
    login(client)
    response = client.post(
        "/api/v1/coach/chat",
        json={"messages": [{"role": "user", "content": "What next?"}]},
        headers=csrf(client),
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "Choose one " in response.text
    assert "event: done" in response.text
    usage = client.get("/api/v1/coach/usage").json()
    assert usage["calls_used"] == 1
    assert usage["output_tokens_used"] == 4
    assert (
        client.patch("/api/v1/me", json={"ai_enabled": False}, headers=csrf(client)).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/coach/chat",
            json={"messages": [{"role": "user", "content": "What next?"}]},
            headers=csrf(client),
        ).status_code
        == 403
    )
    assert client.get("/api/v1/coach/usage").json()["calls_used"] == 1


def test_output_token_quota_boundary_and_period_rollover(integration_client: TestClient) -> None:
    client = integration_client
    user = login(client)

    async def run() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            owner = await db.get(User, user["id"])
            assert owner
            plan = await db.get(Plan, owner.plan_id)
            assert plan
            plan.quotas = {"ai.calls": 10, "ai.output_tokens": 1500, "ai.chat_messages": 10}
            stale = datetime.now(UTC).replace(day=1) - timedelta(days=1)
            db.add(
                AICall(
                    user_id=owner.id,
                    task="chat",
                    provider="anthropic",
                    model="test",
                    input_tokens=0,
                    output_tokens=99999,
                    status="success",
                    created_at=stale,
                )
            )
            await db.commit()
            await reserve(db, owner, "chat", IntegrationSettings(_env_file=None))
            with pytest.raises(HTTPException) as error:
                await reserve(db, owner, "chat", IntegrationSettings(_env_file=None))
            assert error.value.status_code == 429
            assert error.value.detail["metric"] == "ai.output_tokens"
            assert error.value.detail["used"] == 1500
            assert error.value.detail["resets_at"]

    assert client.portal
    client.portal.call(run)
