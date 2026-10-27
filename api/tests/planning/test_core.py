"""Real PostgreSQL tests for the planning loop and ownership boundaries."""

import asyncio
import re
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.auth import User
from app.models.planning import PlanningRecord
from app.routers.planning import router, start_focus
from app.schemas.planning import FocusInput


@pytest.fixture
def planning_client(auth_app: FastAPI) -> Iterator[TestClient]:
    auth_app.include_router(router)
    with TestClient(auth_app) as client:
        yield client


def csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/v1/auth/csrf").json()["csrf_token"]}


def sign_in(client: TestClient, email: str = "owner@example.test") -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/magic/request", json={"email": email}, headers=csrf(client)
    )
    assert response.status_code == 202
    message = client.app.state.email_sender.messages[-1]  # type: ignore[union-attr]
    match = re.search(r"http://testserver/auth/confirm\?token=\S+", message.text)
    assert match
    token = parse_qs(urlsplit(match.group()).query)["token"][0]
    response = client.post("/api/v1/auth/magic/verify", json={"token": token}, headers=csrf(client))
    assert response.status_code == 200, response.text
    return response.json()


def next_week() -> date:
    today = datetime.now(UTC).date()
    return today + timedelta(days=7 - today.weekday())


def goal_body() -> dict[str, Any]:
    return {
        "title": "Publish a thoughtful essay",
        "outcome_statement": "Finish a draft",
        "start_date": (date.today() - timedelta(days=10)).isoformat(),
        "target_date": (date.today() + timedelta(days=120)).isoformat(),
        "actions": [{"title": "Write", "weekly_minutes_target": 120}],
        "obstacles": [
            {
                "risk_text": "Interrupted",
                "if_cue": "A message arrives",
                "then_response": "Reply after focus",
            }
        ],
    }


def add_goal(client: TestClient) -> dict[str, Any]:
    result = client.post("/api/v1/goals", json=goal_body(), headers=csrf(client))
    assert result.status_code == 201, result.text
    return result.json()


def test_complete_loop_persists_and_replays_checkin(planning_client: TestClient) -> None:
    client = planning_client
    sign_in(client)
    goal = add_goal(client)
    checkin_body = {"metric_value": 12, "note": "First pages", "client_event_id": str(uuid4())}
    first = client.post(
        f"/api/v1/goals/{goal['id']}/checkins", json=checkin_body, headers=csrf(client)
    )
    second = client.post(
        f"/api/v1/goals/{goal['id']}/checkins", json=checkin_body, headers=csrf(client)
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert len(client.get(f"/api/v1/goals/{goal['id']}").json()["checkins"]) == 1
    week = next_week().isoformat()
    draft = client.post("/api/v1/plan/draft", json={"week_start": week}, headers=csrf(client))
    assert draft.status_code == 200, draft.text
    blocks = draft.json()["blocks"]
    assert blocks and all(b["reason"] for b in blocks)
    accepted = client.post(
        "/api/v1/plan/accept", json={"block_ids": [b["id"] for b in blocks]}, headers=csrf(client)
    )
    assert accepted.status_code == 200, accepted.text
    again = client.post("/api/v1/plan/draft", json={"week_start": week}, headers=csrf(client))
    assert again.status_code == 200, again.text
    assert again.json()["blocks"] == []
    assert all(
        b["status"] == "accepted" for b in client.get(f"/api/v1/plan/week?start={week}").json()
    )
    focus = client.post(
        "/api/v1/focus/start",
        json={"time_block_id": blocks[0]["id"], "planned_minutes": 25},
        headers=csrf(client),
    )
    assert focus.status_code == 201, focus.text
    assert client.get("/api/v1/focus/active").json()["id"] == focus.json()["id"]
    ended = client.post(
        f"/api/v1/focus/{focus.json()['id']}/end", json={"self_rating": 4}, headers=csrf(client)
    )
    assert ended.status_code == 200
    assert ended.json()["actual_minutes"] < 1
    assert client.get("/api/v1/focus/active").json() is None
    assert client.get("/api/v1/focus/stats").json()["completed_sessions"] == 1
    assert client.get("/api/v1/focus/sessions").json()["items"][0]["self_rating"] == 4
    assert client.get("/api/v1/trajectory").json()[0]["actual_fraction"] == 0.12
    saved = client.post(
        f"/api/v1/reflection/{week}",
        json={"wins": "I began", "adjustments": "Shorter first block"},
        headers=csrf(client),
    )
    assert saved.status_code == 200
    assert client.get(f"/api/v1/reflection/{week}").json()["wins"] == "I began"


def test_every_record_operation_is_user_scoped(planning_client: TestClient) -> None:
    client = planning_client
    sign_in(client)
    goal = add_goal(client)
    week = next_week().isoformat()
    draft = client.post(
        "/api/v1/plan/draft", json={"week_start": week}, headers=csrf(client)
    ).json()
    block = draft["blocks"][0]
    busy = client.post(
        "/api/v1/busy",
        json={"start_at": f"{week}T18:00:00Z", "end_at": f"{week}T19:00:00Z"},
        headers=csrf(client),
    ).json()
    focus = client.post(
        "/api/v1/focus/start", json={"action_id": goal["actions"][0]["id"]}, headers=csrf(client)
    ).json()
    client.app.state.settings.signup_mode = "open"  # type: ignore[union-attr]
    client.cookies.clear()
    sign_in(client, "second@example.test")
    assert client.get("/api/v1/goals").json() == []
    assert client.get(f"/api/v1/goals/{goal['id']}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/goals/{goal['id']}", json=goal_body(), headers=csrf(client)
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/goals/{goal['id']}", headers=csrf(client)).status_code == 404
    assert (
        client.post(
            f"/api/v1/goals/{goal['id']}/checkins", json={"metric_value": 1}, headers=csrf(client)
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/plan/accept", json={"block_ids": [block["id"]]}, headers=csrf(client)
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/blocks/{block['id']}", json={"status": "skipped"}, headers=csrf(client)
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/blocks/{block['id']}", headers=csrf(client)).status_code == 404
    assert client.delete(f"/api/v1/busy/{busy['id']}", headers=csrf(client)).status_code == 404
    assert (
        client.post(f"/api/v1/focus/{focus['id']}/end", json={}, headers=csrf(client)).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/focus/start",
            json={"action_id": goal["actions"][0]["id"]},
            headers=csrf(client),
        ).status_code
        == 404
    )
    assert client.get("/api/v1/focus/sessions").json()["items"] == []


def test_manual_busy_and_move_constraints(planning_client: TestClient) -> None:
    client = planning_client
    sign_in(client)
    add_goal(client)
    week = next_week().isoformat()
    busy = {"start_at": f"{week}T09:00:00Z", "end_at": f"{week}T12:00:00Z"}
    assert client.post("/api/v1/busy", json=busy, headers=csrf(client)).status_code == 201
    blocks = client.post(
        "/api/v1/plan/draft", json={"week_start": week}, headers=csrf(client)
    ).json()["blocks"]
    assert blocks
    assert (
        client.patch(
            f"/api/v1/blocks/{blocks[0]['id']}", json=busy, headers=csrf(client)
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/blocks/{blocks[0]['id']}",
            json={"start_at": f"{week}T22:00:00Z", "end_at": f"{week}T23:00:00Z"},
            headers=csrf(client),
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/plan/accept",
            json={"block_ids": [b["id"] for b in blocks]},
            headers=csrf(client),
        ).status_code
        == 200
    )
    if len(blocks) > 1:
        assert (
            client.patch(
                f"/api/v1/blocks/{blocks[1]['id']}",
                json={"start_at": blocks[0]["start_at"], "end_at": blocks[0]["end_at"]},
                headers=csrf(client),
            ).status_code
            == 409
        )


def test_concurrent_focus_has_one_winner(planning_client: TestClient) -> None:
    client = planning_client
    user_id = sign_in(client)["id"]

    async def run() -> list[int]:
        async def start() -> int:
            async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
                user = await db.get(User, user_id)
                assert user is not None
                try:
                    await start_focus(FocusInput(), db, user)
                    return 201
                except HTTPException as error:
                    await db.rollback()
                    return error.status_code

        return list(await asyncio.gather(start(), start()))

    assert client.portal is not None
    assert sorted(client.portal.call(run)) == [201, 409]


def test_expiry_and_offline_early_end_correction(planning_client: TestClient) -> None:
    client = planning_client
    sign_in(client)
    session = client.post(
        "/api/v1/focus/start", json={"planned_minutes": 25}, headers=csrf(client)
    ).json()
    start = datetime.now(UTC) - timedelta(minutes=30)

    async def age() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            row = await db.get(PlanningRecord, session["id"])
            assert row is not None
            row.payload = {
                **row.payload,
                "started_at": start.isoformat(),
                "ends_at": (start + timedelta(minutes=25)).isoformat(),
            }
            await db.commit()

    assert client.portal is not None
    client.portal.call(age)
    assert client.get("/api/v1/focus/active").json() is None
    end_body = {
        "ended_at": (start + timedelta(minutes=5)).isoformat(),
        "client_event_id": str(uuid4()),
        "self_rating": 3,
    }
    first = client.post(f"/api/v1/focus/{session['id']}/end", json=end_body, headers=csrf(client))
    assert first.status_code == 200, first.text
    assert first.json()["actual_minutes"] == 5
    second = client.post(f"/api/v1/focus/{session['id']}/end", json=end_body, headers=csrf(client))
    assert second.json()["actual_minutes"] == 5


def test_database_enforces_action_cap(planning_client: TestClient) -> None:
    client = planning_client
    user_id = sign_in(client)["id"]

    async def invalid_insert() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            db.add(
                PlanningRecord(
                    user_id=user_id, kind="goal", payload={"actions": [{"title": "x"}] * 6}
                )
            )
            with pytest.raises(IntegrityError):
                await db.flush()
            await db.rollback()
            assert not list(await db.scalars(select(PlanningRecord)))

    assert client.portal is not None
    client.portal.call(invalid_insert)


def test_blocklists_default_snapshot_and_ownership(planning_client: TestClient) -> None:
    client = planning_client
    sign_in(client)
    first = client.post(
        "/api/v1/blocklists",
        json={"name": "Deep work", "domains": ["YouTube.com"]},
        headers=csrf(client),
    )
    assert first.status_code == 201, first.text
    assert first.json()["is_default"] is True
    focus = client.post("/api/v1/focus/start", json={}, headers=csrf(client))
    assert focus.status_code == 201
    assert focus.json()["blocklist_snapshot"] == ["youtube.com"]
    second = client.post(
        "/api/v1/blocklists",
        json={"name": "Writing", "domains": ["reddit.com"], "is_default": True},
        headers=csrf(client),
    )
    assert second.status_code == 201
    assert client.get("/api/v1/focus/active").json()["blocklist_snapshot"] == ["youtube.com"]
    lists = client.get("/api/v1/blocklists").json()
    assert [item["id"] for item in lists if item["is_default"]] == [second.json()["id"]]
    client.app.state.settings.google_redirect_uri = "https://api.example.com/callback"  # type: ignore[union-attr]
    assert (
        client.post(
            "/api/v1/blocklists",
            json={"name": "Oops", "domains": ["example.com"]},
            headers=csrf(client),
        ).status_code
        == 422
    )
    client.app.state.settings.signup_mode = "open"  # type: ignore[union-attr]
    client.cookies.clear()
    sign_in(client, "other@example.test")
    assert client.get("/api/v1/blocklists").json() == []
    assert (
        client.patch(
            f"/api/v1/blocklists/{first.json()['id']}",
            json={"name": "Changed", "domains": []},
            headers=csrf(client),
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/blocklists/{first.json()['id']}", headers=csrf(client)).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/focus/start", json={"blocklist_id": first.json()["id"]}, headers=csrf(client)
        ).status_code
        == 404
    )
