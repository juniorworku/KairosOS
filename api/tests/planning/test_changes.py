"""Draft outcomes and explicit, stale-safe plan change acceptance."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_core import add_goal, csrf, goal_body, next_week, sign_in

from app.routers.agenda import router as agenda_router
from app.routers.planning import router


@pytest.fixture
def change_client(auth_app: FastAPI) -> Iterator[TestClient]:
    auth_app.include_router(router)
    auth_app.include_router(agenda_router)
    with TestClient(auth_app) as client:
        yield client


def add_block(client: TestClient) -> dict:
    goal = add_goal(client)
    monday = next_week().isoformat()
    result = client.post(
        "/api/v1/blocks",
        json={
            "goal_id": goal["id"],
            "action_id": goal["actions"][0]["id"],
            "start_at": f"{monday}T09:00:00Z",
            "end_at": f"{monday}T10:00:00Z",
            "notes": "Bring notes",
        },
        headers=csrf(client),
    )
    assert result.status_code == 201, result.text
    return result.json()


def week_blocks(client: TestClient) -> list:
    return client.get(f"/api/v1/plan/week?start={next_week()}").json()


def test_draft_explains_empty_account_and_past_week(change_client: TestClient) -> None:
    client = change_client
    sign_in(client)
    response = client.post(
        "/api/v1/plan/draft", json={"week_start": next_week().isoformat()}, headers=csrf(client)
    )
    assert response.status_code == 200, response.text
    assert response.json()["empty_reason"] == "no_goals"
    assert "Add a goal" in response.json()["message"]
    past = next_week() - timedelta(days=21)
    result = client.post(
        "/api/v1/plan/draft", json={"week_start": past.isoformat()}, headers=csrf(client)
    ).json()
    assert result["empty_reason"] == "past_week" and result["message"]


def test_draft_distinguishes_dates_and_unconfigured_action_time(change_client: TestClient) -> None:
    client = change_client
    sign_in(client)
    body = goal_body()
    body["start_date"] = (next_week() + timedelta(days=30)).isoformat()
    body["target_date"] = (next_week() + timedelta(days=90)).isoformat()
    goal = client.post("/api/v1/goals", json=body, headers=csrf(client)).json()
    result = client.post(
        "/api/v1/plan/draft", json={"week_start": next_week().isoformat()}, headers=csrf(client)
    ).json()
    assert result["empty_reason"] == "outside_dates"
    body["start_date"] = datetime.now(UTC).date().isoformat()
    body["actions"] = [{**goal["actions"][0], "weekly_minutes_target": 0}]
    assert (
        client.patch(f"/api/v1/goals/{goal['id']}", json=body, headers=csrf(client)).status_code
        == 200
    )
    result = client.post(
        "/api/v1/plan/draft", json={"week_start": next_week().isoformat()}, headers=csrf(client)
    ).json()
    assert result["empty_reason"] == "no_actions"


def test_move_preview_does_not_move_until_accept_and_replay_is_idempotent(
    change_client: TestClient,
) -> None:
    client = change_client
    sign_in(client)
    block = add_block(client)
    monday = next_week().isoformat()
    body = {
        "block_id": block["id"],
        "operation": "move",
        "start_at": f"{monday}T13:00:00Z",
        "end_at": f"{monday}T14:00:00Z",
    }
    response = client.post("/api/v1/plan/changes", json=body, headers=csrf(client))
    assert response.status_code == 201, response.text
    proposal = response.json()
    assert proposal["before"]["notes"] == "Bring notes"
    assert week_blocks(client)[0]["start_at"] == block["start_at"]
    assert (
        client.post("/api/v1/plan/changes", json=body, headers=csrf(client)).json()["id"]
        == proposal["id"]
    )
    for _ in range(2):
        result = client.post(f"/api/v1/plan/changes/{proposal['id']}/accept", headers=csrf(client))
        assert result.status_code == 200, result.text
    changed = week_blocks(client)[0]
    assert changed["start_at"] == proposal["after"]["start_at"]
    assert changed["moved_count"] == 1 and changed["notes"] == "Bring notes"


def test_accept_rechecks_new_busy_time_and_stale_snapshot(change_client: TestClient) -> None:
    client = change_client
    sign_in(client)
    block = add_block(client)
    monday = next_week().isoformat()
    target = {"start_at": f"{monday}T13:00:00Z", "end_at": f"{monday}T14:00:00Z"}
    proposal = client.post(
        "/api/v1/plan/changes",
        json={"block_id": block["id"], "operation": "move", **target},
        headers=csrf(client),
    ).json()
    busy = client.post("/api/v1/busy", json=target, headers=csrf(client)).json()
    result = client.post(f"/api/v1/plan/changes/{proposal['id']}/accept", headers=csrf(client))
    assert result.status_code == 409
    assert week_blocks(client)[0]["start_at"] == block["start_at"]
    client.delete(f"/api/v1/busy/{busy['id']}", headers=csrf(client))
    assert (
        client.patch(
            f"/api/v1/blocks/{block['id']}", json={"notes": "Changed later"}, headers=csrf(client)
        ).status_code
        == 200
    )
    result = client.post(f"/api/v1/plan/changes/{proposal['id']}/accept", headers=csrf(client))
    assert result.status_code == 409
    assert result.json()["detail"]["code"] == "stale_change"


def test_removal_and_dismissal_are_explicit(change_client: TestClient) -> None:
    client = change_client
    sign_in(client)
    block = add_block(client)
    body = {"block_id": block["id"], "operation": "remove"}
    proposal = client.post("/api/v1/plan/changes", json=body, headers=csrf(client)).json()
    assert week_blocks(client)[0]["status"] == "accepted"
    result = client.post(f"/api/v1/plan/changes/{proposal['id']}/dismiss", headers=csrf(client))
    assert result.status_code == 200
    assert week_blocks(client)[0]["status"] == "accepted"
    assert (
        client.post(
            f"/api/v1/plan/changes/{proposal['id']}/accept", headers=csrf(client)
        ).status_code
        == 409
    )
    proposal = client.post("/api/v1/plan/changes", json=body, headers=csrf(client)).json()
    assert (
        client.post(
            f"/api/v1/plan/changes/{proposal['id']}/accept", headers=csrf(client)
        ).status_code
        == 200
    )
    assert week_blocks(client)[0]["status"] == "cancelled"


def test_draft_proposes_busy_conflict_move_without_changing_accepted_block(
    change_client: TestClient,
) -> None:
    client = change_client
    sign_in(client)
    block = add_block(client)
    assert (
        client.post(
            "/api/v1/busy",
            json={"start_at": block["start_at"], "end_at": block["end_at"]},
            headers=csrf(client),
        ).status_code
        == 201
    )
    response = client.post(
        "/api/v1/plan/draft", json={"week_start": next_week().isoformat()}, headers=csrf(client)
    )
    assert response.status_code == 200, response.text
    assert response.json()["changes"]
    change = response.json()["changes"][0]
    assert change["operation"] == "move"
    assert change["before"]["start_at"] == block["start_at"]
    original = next(item for item in week_blocks(client) if item["id"] == block["id"])
    assert original["start_at"] == block["start_at"] and original["status"] == "accepted"


def test_proposals_are_owner_scoped(change_client: TestClient) -> None:
    client = change_client
    sign_in(client)
    block = add_block(client)
    proposal = client.post(
        "/api/v1/plan/changes",
        json={"block_id": block["id"], "operation": "remove"},
        headers=csrf(client),
    ).json()
    client.app.state.settings.signup_mode = "open"
    client.cookies.clear()
    sign_in(client, "second@example.test")
    assert client.get("/api/v1/plan/changes").json() == []
    assert (
        client.post(
            f"/api/v1/plan/changes/{proposal['id']}/accept", headers=csrf(client)
        ).status_code
        == 404
    )


def test_drafts_and_manual_blocks_respect_recurring_local_events(change_client: TestClient) -> None:
    client = change_client
    sign_in(client)
    goal = add_goal(client)
    monday = next_week().isoformat()
    event = client.post(
        "/api/v1/events",
        json={
            "title": "Protected appointment",
            "notes": "Keep this time",
            "timezone": "UTC",
            "start_at": f"{monday}T09:00:00Z",
            "end_at": f"{monday}T12:00:00Z",
            "recurrence": {"frequency": "weekly", "count": 2},
        },
        headers=csrf(client),
    )
    assert event.status_code == 201, event.text
    denied = client.post(
        "/api/v1/blocks",
        json={
            "goal_id": goal["id"],
            "action_id": goal["actions"][0]["id"],
            "start_at": f"{monday}T09:00:00Z",
            "end_at": f"{monday}T10:00:00Z",
        },
        headers=csrf(client),
    )
    assert denied.status_code == 409
    result = client.post("/api/v1/plan/draft", json={"week_start": monday}, headers=csrf(client))
    assert result.status_code == 200, result.text
    assert result.json()["blocks"] and result.json()["message"]
    left = datetime.fromisoformat(f"{monday}T08:50:00+00:00")
    right = datetime.fromisoformat(f"{monday}T12:10:00+00:00")
    for block in result.json()["blocks"]:
        assert not (
            datetime.fromisoformat(block["start_at"]) < right
            and datetime.fromisoformat(block["end_at"]) > left
        )


def test_direct_block_deletion_cleans_pending_previews(change_client: TestClient) -> None:
    client = change_client
    sign_in(client)
    block = add_block(client)
    response = client.post(
        "/api/v1/plan/changes",
        json={"block_id": block["id"], "operation": "remove"},
        headers=csrf(client),
    )
    assert response.status_code == 201
    assert client.delete(f"/api/v1/blocks/{block['id']}", headers=csrf(client)).status_code == 204
    assert client.get("/api/v1/plan/changes").json() == []


def test_out_of_week_goals_do_not_create_false_capacity_warnings(change_client: TestClient) -> None:
    client = change_client
    sign_in(client)
    body = goal_body()
    body["start_date"] = (next_week() - timedelta(days=60)).isoformat()
    body["target_date"] = (next_week() - timedelta(days=10)).isoformat()
    assert client.post("/api/v1/goals", json=body, headers=csrf(client)).status_code == 201
    assert add_goal(client)
    result = client.post(
        "/api/v1/plan/draft", json={"week_start": next_week().isoformat()}, headers=csrf(client)
    ).json()
    assert result["blocks"]
    # The active goal's 120min target with1.3 reserve has6min below its30min minimum;
    # the expired goal must not add its156min quota to this shortfall.
    assert result["dropped_minutes"] < 30


def test_new_draft_reserves_pending_move_destinations(change_client: TestClient) -> None:
    client = change_client
    sign_in(client)
    block = add_block(client)
    monday = next_week().isoformat()
    target = {"start_at": f"{monday}T13:00:00Z", "end_at": f"{monday}T14:00:00Z"}
    response = client.post(
        "/api/v1/plan/changes",
        json={"block_id": block["id"], "operation": "move", **target},
        headers=csrf(client),
    )
    assert response.status_code == 201, response.text
    result = client.post(
        "/api/v1/plan/draft", json={"week_start": monday}, headers=csrf(client)
    ).json()
    left, right = (
        datetime.fromisoformat(target["start_at"]),
        datetime.fromisoformat(target["end_at"]),
    )
    for item in result["blocks"]:
        assert not (
            datetime.fromisoformat(item["start_at"]) < right
            and datetime.fromisoformat(item["end_at"]) > left
        )
