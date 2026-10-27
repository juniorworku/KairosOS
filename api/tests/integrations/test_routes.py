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
