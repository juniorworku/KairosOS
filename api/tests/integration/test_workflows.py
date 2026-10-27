"""Production app composition exercised against an isolated PostgreSQL schema."""

import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.integrations.coach import ProviderResult
from app.integrations.jsonutil import Json
from app.main import create_app
from app.models.auth import User
from app.models.planning import PlanningRecord
from app.schemas.planning import GoalInput


@pytest.fixture
def core_client(auth_app: FastAPI) -> Iterator[TestClient]:
    async def ready() -> bool:
        return True

    application = create_app(auth_app.state.settings, database_check=ready, redis_check=ready)
    # Use the fixture's isolated schema lifecycle, while retaining all real routers,
    # security headers, exception handlers, dependency wiring, and request middleware.
    application.router.lifespan_context = auth_app.router.lifespan_context
    for key in ("session_factory", "auth_limiter", "email_sender"):
        setattr(application.state, key, getattr(auth_app.state, key))
    with TestClient(application) as client:
        yield client


def csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/v1/auth/csrf").json()["csrf_token"]}


def login(client: TestClient) -> dict[str, Any]:
    assert (
        client.post(
            "/api/v1/auth/magic/request", json={"email": "owner@example.test"}, headers=csrf(client)
        ).status_code
        == 202
    )
    message = client.app.state.email_sender.messages[-1]  # type: ignore[union-attr]
    match = re.search(r"http://testserver/auth/confirm\?token=\S+", message.text)
    assert match
    token = parse_qs(urlsplit(match.group()).query)["token"][0]
    response = client.post("/api/v1/auth/magic/verify", json={"token": token}, headers=csrf(client))
    assert response.status_code == 200
    return response.json()


def goal_body(title: str = "Finish the manuscript") -> dict[str, Any]:
    today = datetime.now(UTC).date()
    return GoalInput(
        title=title,
        outcome_statement="Draft chapters for editor@example.test; HTTPS://private.example/notes",
        start_date=today - timedelta(days=30),
        target_date=today + timedelta(days=60),
        metric_name="Chapters",
        metric_target=10,
        actions=[{"title": "Write", "weekly_minutes_target": 180}],
    ).model_dump(mode="json")


def test_app_error_contract_rolls_back_and_keeps_planning_data(core_client: TestClient) -> None:
    client = core_client
    unauthenticated = client.get("/api/v1/goals")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "request_failed"
    assert unauthenticated.headers["cache-control"] == "no-store"
    assert unauthenticated.headers["x-request-id"]
    login(client)
    invalid = client.post("/api/v1/goals", json={"title": "Incomplete"}, headers=csrf(client))
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"
    created = client.post("/api/v1/goals", json=goal_body(), headers=csrf(client))
    assert created.status_code == 201, created.text
    identifier = created.json()["id"]
    denied = client.patch(f"/api/v1/goals/{identifier}", json=goal_body("Forged write"), headers={})
    assert denied.status_code == 403
    assert client.get(f"/api/v1/goals/{identifier}").json()["title"] == "Finish the manuscript"
    missing = client.patch(
        "/api/v1/blocks/not-owned", json={"status": "skipped"}, headers=csrf(client)
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    assert client.get("/api/v1/goals").json()[0]["id"] == identifier


def test_consented_coach_uses_real_effort_without_calendar_or_other_owner_data(
    core_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.integrations.coach as module

    client = core_client
    owner = login(client)
    body = goal_body()
    body["actions"].append(
        {
            "title": "Edit",
            "kind": "project",
            "total_minutes_estimate": 600,
            "weekly_minutes_target": 120,
        }
    )
    goal = client.post("/api/v1/goals", json=body, headers=csrf(client)).json()
    # Use a local week far ahead of UTC and a session spanning its boundary.
    zone = ZoneInfo("Pacific/Kiritimati")
    now = datetime.now(UTC)
    today = now.astimezone(zone).date()
    monday = today - timedelta(days=today.weekday())
    boundary = datetime.combine(monday, time.min, zone).astimezone(UTC)

    recent_end = min(boundary + timedelta(minutes=15), now)
    recent_minutes = (recent_end - boundary + timedelta(minutes=15)).total_seconds() / 60
    expected_weekly_minutes = round((recent_end - boundary).total_seconds() / 60, 1)

    async def seed() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            user = await db.get(User, owner["id"])
            assert user
            user.timezone = zone.key
            other = User(email="another@example.test", plan_id=user.plan_id)
            db.add(other)
            await db.flush()
            db.add(PlanningRecord(user_id=other.id, kind="goal", payload=goal_body("OTHER OWNER")))
            for start, end, minutes in [
                (boundary - timedelta(minutes=15), recent_end, recent_minutes),
                (boundary - timedelta(days=2), boundary - timedelta(days=2, minutes=-30), 30),
            ]:
                db.add(
                    PlanningRecord(
                        user_id=user.id,
                        kind="focus",
                        payload={
                            "goal_id": goal["id"],
                            "time_block_id": None,
                            "started_at": start.isoformat(),
                            "ends_at": end.isoformat(),
                            "ended_at": end.isoformat(),
                            "actual_minutes": minutes,
                            "planned_minutes": 30,
                            "title": "PRIVATE SESSION TITLE",
                        },
                    )
                )
            db.add(
                PlanningRecord(
                    user_id=user.id,
                    kind="checkin",
                    payload={
                        "goal_id": goal["id"],
                        "metric_value": 3,
                        "recorded_at": now.isoformat(),
                        "note": "PRIVATE CHECKIN NOTE",
                    },
                )
            )
            db.add(
                PlanningRecord(
                    user_id=user.id,
                    kind="busy",
                    payload={
                        "start_at": now.isoformat(),
                        "end_at": (now + timedelta(hours=1)).isoformat(),
                        "title": "PRIVATE CALENDAR TITLE",
                    },
                )
            )
            await db.commit()

    assert client.portal
    client.portal.call(seed)
    prompts: list[str] = []

    class Provider:
        async def generate(
            self, *, system: str, user: str, schema: dict[str, Json] | None, max_tokens: int
        ) -> ProviderResult:
            return ProviderResult(text="{}")

        async def stream_text(self, *, system: str, user: str, max_tokens: int):  # type: ignore[no-untyped-def]
            prompts.append(user)
            yield ProviderResult(text="Review the next chapter.")
            yield ProviderResult(text="", input_tokens=100, output_tokens=5)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "test-model")
    monkeypatch.setattr(module, "get_provider", lambda config, client: Provider())
    for consent in (False, True):
        response = client.post(
            "/api/v1/coach/chat",
            json={
                "messages": [{"role": "user", "content": "What should I work on?"}],
                "include_context": consent,
            },
            headers=csrf(client),
        )
        assert response.status_code == 200, response.text
        assert "event: done" in response.text
    assert "computed_context" not in prompts[0]
    context = json.loads(prompts[1].split("<computed_context>")[1].split("</computed_context>")[0])
    assert context["week_start"] == monday.isoformat()
    assert len(context["goals"]) == 1
    data = context["goals"][0]
    assert data["actions"][0]["weekly_minutes_target"] == 180
    assert data["actions"][1]["total_minutes_estimate"] == 600
    assert data["actions"][1]["remaining_minutes_estimate"] == 600
    assert "weekly_minutes_target" not in data["actions"][1]
    assert data["latest_metric_value"] == 3
    assert data["focused_minutes_this_week"] == expected_weekly_minutes
    assert data["completed_sessions_this_week"] == 1
    assert data["actual_fraction"] == 0.3
    for excluded in (
        "OTHER OWNER",
        "PRIVATE",
        "editor@example.test",
        "HTTPS://private",
        goal["id"],
    ):
        assert excluded not in prompts[1]
    assert "[email]" in data["outcome"] and "[link]" in data["outcome"]
    # Coaching remains read-only; it must not invent or apply planning changes.
    assert len(client.get("/api/v1/goals").json()) == 1
    assert client.get("/api/v1/coach/usage").json()["calls_used"] == 2


def test_manual_plan_move_focus_and_progress_survive_conflicts(core_client: TestClient) -> None:
    """Exercise the usable planning loop through the fully composed application."""
    from uuid import uuid4

    client = core_client
    login(client)
    goal_response = client.post("/api/v1/goals", json=goal_body(), headers=csrf(client))
    assert goal_response.status_code == 201
    goal = goal_response.json()
    today = datetime.now(UTC).date()
    week = (today + timedelta(days=7 - today.weekday())).isoformat()
    block_response = client.post(
        "/api/v1/blocks",
        json={
            "goal_id": goal["id"],
            "action_id": goal["actions"][0]["id"],
            "start_at": f"{week}T09:00:00Z",
            "end_at": f"{week}T10:00:00Z",
        },
        headers=csrf(client),
    )
    assert block_response.status_code == 201, block_response.text
    block = block_response.json()
    assert block["status"] == "accepted" and block["title"] == "Write"
    occupied = {"start_at": f"{week}T11:00:00Z", "end_at": f"{week}T12:00:00Z"}
    assert client.post("/api/v1/busy", json=occupied, headers=csrf(client)).status_code == 201
    conflict = client.patch(f"/api/v1/blocks/{block['id']}", json=occupied, headers=csrf(client))
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["error"]["code"]
    saved = client.get(f"/api/v1/plan/week?start={week}").json()
    assert saved[0]["start_at"] == block["start_at"]
    moved = client.patch(
        f"/api/v1/blocks/{block['id']}",
        json={
            "start_at": f"{week}T13:00:00Z",
            "end_at": f"{week}T14:00:00Z",
        },
        headers=csrf(client),
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["moved_count"] == 1
    session = client.post(
        "/api/v1/focus/start",
        json={
            "time_block_id": block["id"],
            "planned_minutes": 25,
        },
        headers=csrf(client),
    )
    assert session.status_code == 201, session.text
    end_body = {"self_rating": 4, "client_event_id": str(uuid4())}
    ended = client.post(
        f"/api/v1/focus/{session.json()['id']}/end", json=end_body, headers=csrf(client)
    )
    assert ended.status_code == 200, ended.text
    replay = client.post(
        f"/api/v1/focus/{session.json()['id']}/end", json=end_body, headers=csrf(client)
    )
    assert replay.status_code == 200
    assert replay.json()["actual_minutes"] == ended.json()["actual_minutes"]
    assert client.get("/api/v1/focus/stats").json()["completed_sessions"] == 1
    saved = client.get(f"/api/v1/plan/week?start={week}").json()
    assert saved[0]["status"] == "accepted", "A brief session cannot complete an hour-long block"
    check = {"metric_value": 2, "client_event_id": str(uuid4())}
    for _ in range(2):
        assert (
            client.post(
                f"/api/v1/goals/{goal['id']}/checkins", json=check, headers=csrf(client)
            ).status_code
            == 201
        )
    assert len(client.get(f"/api/v1/goals/{goal['id']}").json()["checkins"]) == 1
    assert client.get("/api/v1/trajectory").json()[0]["actual_fraction"] == 0.2
    assert (
        client.post(
            f"/api/v1/reflection/{week}", json={"wins": "Started a chapter"}, headers=csrf(client)
        ).status_code
        == 200
    )
    assert client.get(f"/api/v1/reflection/{week}").json()["wins"] == "Started a chapter"


@pytest.mark.parametrize("repaired", [True, False])
def test_coaching_schema_failure_retries_are_metered_and_never_save_a_goal(
    core_client: TestClient, monkeypatch: pytest.MonkeyPatch, repaired: bool
) -> None:
    import app.integrations.coach as module

    client = core_client
    login(client)
    calls: list[str] = []

    class Provider:
        async def generate(
            self, *, system: str, user: str, schema: dict[str, Json] | None, max_tokens: int
        ) -> ProviderResult:
            calls.append(user)
            content = "invalid JSON"
            if len(calls) == 2 and repaired:
                content = json.dumps(
                    {
                        "outcome_statement": "Finish the first three chapters",
                        "metric_name": "Chapters",
                        "metric_unit": "chapters",
                        "suggested_target": 3,
                        "clarifying_questions": [],
                    }
                )
            return ProviderResult(text=content, input_tokens=10, output_tokens=2)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "test-model")
    monkeypatch.setattr(module, "get_provider", lambda config, client: Provider())
    response = client.post(
        "/api/v1/coach/goal-refine", json={"text": "Finish my manuscript"}, headers=csrf(client)
    )
    assert response.status_code == (200 if repaired else 503), response.text
    if repaired:
        assert response.json()["suggested_target"] == 3
    else:
        assert response.json()["error"]["code"] == "ai_unavailable"
    assert len(calls) == 2
    assert client.get("/api/v1/coach/usage").json()["calls_used"] == 2
    assert client.get("/api/v1/coach/usage").json()["output_tokens_used"] == 4
    assert client.get("/api/v1/goals").json() == []
