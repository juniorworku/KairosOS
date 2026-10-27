"""Timer lifecycle, replay and local-date aggregation against real PostgreSQL."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_core import add_goal, csrf, next_week, sign_in

from app.models.auth import User
from app.models.planning import PlanningRecord
from app.routers.planning import router, save_reflection
from app.schemas.planning import ReflectionInput


@pytest.fixture
def focus_client(auth_app: FastAPI) -> Iterator[TestClient]:
    auth_app.include_router(router)
    with TestClient(auth_app) as client:
        yield client


def block(client: TestClient) -> dict[str, Any]:
    goal = add_goal(client)
    monday = next_week().isoformat()
    response = client.post(
        "/api/v1/blocks",
        json={
            "goal_id": goal["id"],
            "action_id": goal["actions"][0]["id"],
            "start_at": f"{monday}T09:00:00Z",
            "end_at": f"{monday}T10:00:00Z",
        },
        headers=csrf(client),
    )
    assert response.status_code == 201, response.text
    return response.json()


def start(client: TestClient, minutes: int, linked: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"planned_minutes": minutes}
    if linked:
        body["time_block_id"] = linked["id"]
    response = client.post("/api/v1/focus/start", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text
    return response.json()


def age(client: TestClient, session: dict[str, Any]) -> datetime:
    started = datetime.now(UTC) - timedelta(minutes=session["planned_minutes"] + 5)

    async def run() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            row = await db.get(PlanningRecord, session["id"])
            assert row is not None
            row.payload = {
                **row.payload,
                "started_at": started.isoformat(),
                "ends_at": (started + timedelta(minutes=session["planned_minutes"])).isoformat(),
            }
            await db.commit()

    assert client.portal is not None
    client.portal.call(run)
    return started


def block_status(client: TestClient, linked: dict[str, Any]) -> str:
    rows = client.get(f"/api/v1/plan/week?start={linked['week_start']}").json()
    return next(row["status"] for row in rows if row["id"] == linked["id"])


@pytest.mark.parametrize("automatic", [False, True])
def test_short_session_does_not_complete_long_block(
    focus_client: TestClient, automatic: bool
) -> None:
    client = focus_client
    sign_in(client)
    linked = block(client)
    session = start(client, 25, linked)
    began = age(client, session)
    if automatic:
        assert client.get("/api/v1/focus/active").json() is None
    else:
        response = client.post(
            f"/api/v1/focus/{session['id']}/end",
            json={"ended_at": (began + timedelta(minutes=25)).isoformat()},
            headers=csrf(client),
        )
        assert response.status_code == 200
        assert response.json()["actual_minutes"] == 25
    assert block_status(client, linked) == "accepted"
    # Two separate sessions contribute to the same block's budget.
    remaining = start(client, 35, linked)
    age(client, remaining)
    assert client.get("/api/v1/focus/active").json() is None
    assert block_status(client, linked) == "completed"


@pytest.mark.parametrize("decision", ["skipped", "cancelled", "completed"])
def test_expiry_and_correction_preserve_manual_block_decision(
    focus_client: TestClient,
    decision: str,
) -> None:
    client = focus_client
    sign_in(client)
    linked = block(client)
    session = start(client, 60, linked)
    changed = client.patch(
        f"/api/v1/blocks/{linked['id']}", json={"status": decision}, headers=csrf(client)
    )
    assert changed.status_code == 200, changed.text
    began = age(client, session)
    assert client.get("/api/v1/focus/active").json() is None
    assert block_status(client, linked) == decision
    corrected = client.post(
        f"/api/v1/focus/{session['id']}/end",
        json={"ended_at": (began + timedelta(minutes=5)).isoformat()},
        headers=csrf(client),
    )
    assert corrected.status_code == 200
    assert block_status(client, linked) == decision


def test_offline_correction_reopens_only_focus_completed_block(focus_client: TestClient) -> None:
    client = focus_client
    sign_in(client)
    linked = block(client)
    session = start(client, 60, linked)
    began = age(client, session)
    assert client.get("/api/v1/focus/active").json() is None
    assert block_status(client, linked) == "completed"
    corrected = client.post(
        f"/api/v1/focus/{session['id']}/end",
        json={
            "ended_at": (began + timedelta(minutes=5)).isoformat(),
            "client_event_id": str(uuid4()),
        },
        headers=csrf(client),
    )
    assert corrected.status_code == 200
    assert corrected.json()["actual_minutes"] == 5
    assert block_status(client, linked) == "accepted"


def test_end_replay_cannot_overwrite_later_rating_or_extend_time(focus_client: TestClient) -> None:
    client = focus_client
    sign_in(client)
    session = start(client, 25)
    began = age(client, session)
    initial = {
        "ended_at": (began + timedelta(minutes=5)).isoformat(),
        "client_event_id": str(uuid4()),
        "self_rating": 2,
    }
    path = f"/api/v1/focus/{session['id']}/end"
    assert client.post(path, json=initial, headers=csrf(client)).json()["actual_minutes"] == 5
    revised = {**initial, "client_event_id": str(uuid4()), "self_rating": 4}
    assert client.post(path, json=revised, headers=csrf(client)).json()["self_rating"] == 4
    replay = client.post(path, json=initial, headers=csrf(client))
    assert replay.status_code == 200
    assert replay.json()["self_rating"] == 4
    assert replay.json()["actual_minutes"] == 5
    conflicting = client.post(path, json={**initial, "self_rating": 1}, headers=csrf(client))
    assert conflicting.status_code == 409
    later = client.post(
        path, json={"ended_at": (began + timedelta(minutes=20)).isoformat()}, headers=csrf(client)
    )
    assert later.json()["actual_minutes"] == 5
    assert later.json()["self_rating"] == 4
    another = start(client, 25)
    assert (
        client.post(
            f"/api/v1/focus/{another['id']}/end", json=initial, headers=csrf(client)
        ).status_code
        == 409
    )


def test_checkin_replay_rejects_changed_content(focus_client: TestClient) -> None:
    client = focus_client
    sign_in(client)
    goal = add_goal(client)
    path = f"/api/v1/goals/{goal['id']}/checkins"
    body = {"client_event_id": str(uuid4()), "metric_value": 7, "note": "Saved"}
    first = client.post(path, json=body, headers=csrf(client))
    assert first.status_code == 201
    assert client.post(path, json=body, headers=csrf(client)).json()["id"] == first.json()["id"]
    for changed in ({"metric_value": 9}, {"note": "Different"}):
        assert client.post(path, json=body | changed, headers=csrf(client)).status_code == 409
    checks = client.get(f"/api/v1/goals/{goal['id']}").json()["checkins"]
    assert len(checks) == 1 and checks[0]["metric_value"] == 7


@pytest.mark.parametrize(
    "timezone,day",
    [
        ("Pacific/Kiritimati", date(2026, 3, 9)),
        ("America/New_York", date(2026, 3, 8)),
    ],
)
def test_stats_split_cross_midnight_minutes_in_user_timezone(
    focus_client: TestClient,
    timezone: str,
    day: date,
) -> None:
    client = focus_client
    user_id = sign_in(client)["id"]
    assert (
        client.patch("/api/v1/me", json={"timezone": timezone}, headers=csrf(client)).status_code
        == 200
    )
    boundary = datetime.combine(day, datetime.min.time(), ZoneInfo(timezone)).astimezone(UTC)

    async def seed() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            began, ended = boundary - timedelta(minutes=15), boundary + timedelta(minutes=15)
            db.add(
                PlanningRecord(
                    user_id=user_id,
                    kind="focus",
                    payload={
                        "time_block_id": None,
                        "action_id": None,
                        "goal_id": None,
                        "started_at": began.isoformat(),
                        "ends_at": ended.isoformat(),
                        "ended_at": ended.isoformat(),
                        "actual_minutes": 30,
                        "planned_minutes": 30,
                        "self_rating": 4,
                    },
                )
            )
            await db.commit()

    assert client.portal is not None
    client.portal.call(seed)
    previous = day - timedelta(days=1)
    for value in (previous, day):
        result = client.get(f"/api/v1/focus/stats?from={value}&to={value}")
        assert result.status_code == 200
        assert result.json() == {"completed_sessions": 1, "total_minutes": 15, "average_rating": 4}
    together = client.get(f"/api/v1/focus/stats?from={previous}&to={day}").json()
    assert together["total_minutes"] == 30 and together["completed_sessions"] == 1
    assert client.get(f"/api/v1/focus/stats?from={day}&to={previous}").status_code == 422


def test_bad_end_times_do_not_end_active_session(focus_client: TestClient) -> None:
    client = focus_client
    sign_in(client)
    session = start(client, 25)
    began = datetime.fromisoformat(session["started_at"])
    for ended in (
        began.replace(tzinfo=None),
        began - timedelta(seconds=1),
        datetime.now(UTC) + timedelta(hours=1),
    ):
        response = client.post(
            f"/api/v1/focus/{session['id']}/end",
            json={"ended_at": ended.isoformat()},
            headers=csrf(client),
        )
        assert response.status_code == 422
    assert client.get("/api/v1/focus/active").json()["id"] == session["id"]


def test_reflections_require_monday_and_concurrent_saves_share_one_record(
    focus_client: TestClient,
) -> None:
    client = focus_client
    user_id = sign_in(client)["id"]
    monday = next_week()
    tuesday = monday + timedelta(days=1)
    assert client.get(f"/api/v1/reflection/{tuesday}").status_code == 422
    assert (
        client.post(
            f"/api/v1/reflection/{tuesday}", json={"wins": "Note"}, headers=csrf(client)
        ).status_code
        == 422
    )

    async def run() -> list[str]:
        async def save(value: str) -> str:
            async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
                user = await db.get(User, user_id)
                assert user is not None
                result = await save_reflection(monday, ReflectionInput(wins=value), db, user)
                return str(result["id"])

        ids = list(await asyncio.gather(save("First"), save("Second")))
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            rows = list(
                await db.scalars(select(PlanningRecord).where(PlanningRecord.kind == "reflection"))
            )
            assert len(rows) == 1
        return ids

    assert client.portal is not None
    ids = client.portal.call(run)
    assert ids[0] == ids[1]
