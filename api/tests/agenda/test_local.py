"""Local agenda CRUD, ownership, recurrence exceptions and scheduling intervals."""

import re
from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.auth import User
from app.models.planning import PlanningRecord
from app.routers.agenda import local_agenda, local_event_intervals, router


@pytest.fixture
def agenda_client(auth_app: FastAPI) -> Iterator[TestClient]:
    auth_app.include_router(router)
    with TestClient(auth_app) as client:
        yield client


def csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.get("/api/v1/auth/csrf").json()["csrf_token"]}


def login(client: TestClient, email: str = "owner@example.test") -> str:
    response = client.post(
        "/api/v1/auth/magic/request", json={"email": email}, headers=csrf(client)
    )
    assert response.status_code == 202
    message = client.app.state.email_sender.messages[-1]  # type: ignore[union-attr]
    match = re.search(r"http://testserver/auth/confirm\?token=\S+", message.text)
    assert match
    token = parse_qs(urlsplit(match.group()).query)["token"][0]
    response = client.post("/api/v1/auth/magic/verify", json={"token": token}, headers=csrf(client))
    assert response.status_code == 200
    return str(response.json()["id"])


def event_body() -> dict[str, Any]:
    return {
        "title": "Write",
        "notes": "Keep the outline",
        "start_at": "2026-11-02T09:00:00Z",
        "end_at": "2026-11-02T10:00:00Z",
        "timezone": "UTC",
        "all_day": False,
        "recurrence": {"frequency": "daily", "count": 3},
    }


def feed(
    client: TestClient, user_id: str, start: date = date(2026, 11, 2), end: date = date(2026, 11, 5)
) -> list[dict[str, Any]]:
    async def run() -> list[dict[str, Any]]:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            user = await db.get(User, user_id)
            assert user is not None
            return await local_agenda(db, user, start, end)

    assert client.portal is not None
    return client.portal.call(run)


def test_task_crud_scheduled_events_survive_task_deletion(agenda_client: TestClient) -> None:
    client = agenda_client
    user_id = login(client)
    task = client.post(
        "/api/v1/tasks",
        json={"title": "Draft", "notes": "Two pages", "due_date": "2026-11-04"},
        headers=csrf(client),
    )
    assert task.status_code == 201
    task_id = task.json()["id"]
    body = event_body() | {"task_id": task_id}
    event = client.post("/api/v1/events", json=body, headers=csrf(client))
    assert event.status_code == 201
    event_id = event.json()["id"]
    assert len(feed(client, user_id)) == 3
    assert (
        client.patch(
            f"/api/v1/tasks/{task_id}", json={"status": "done"}, headers=csrf(client)
        ).status_code
        == 200
    )
    assert all(item["status"] == "done" for item in feed(client, user_id))
    assert (
        client.patch(
            f"/api/v1/events/{event_id}/occurrences/2026-11-03",
            json={"task_id": task_id},
            headers=csrf(client),
        ).status_code
        == 200
    )
    assert client.delete(f"/api/v1/tasks/{task_id}", headers=csrf(client)).status_code == 204
    assert client.get("/api/v1/tasks").json() == []
    assert client.get(f"/api/v1/events/{event_id}").json()["task_id"] is None
    assert all(item["task_id"] is None for item in feed(client, user_id))


def test_occurrence_move_cancel_and_series_edit_preserve_exceptions(
    agenda_client: TestClient,
) -> None:
    client = agenda_client
    user_id = login(client)
    created = client.post("/api/v1/events", json=event_body(), headers=csrf(client))
    assert created.status_code == 201
    identifier = created.json()["id"]
    moved = client.patch(
        f"/api/v1/events/{identifier}/occurrences/2026-11-03",
        json={
            "start_at": "2026-11-10T14:00:00Z",
            "end_at": "2026-11-10T15:00:00Z",
        },
        headers=csrf(client),
    )
    assert moved.status_code == 200
    assert moved.json()["occurrence_date"] == "2026-11-03"
    assert (
        client.delete(
            f"/api/v1/events/{identifier}/occurrences/2026-11-04", headers=csrf(client)
        ).status_code
        == 204
    )
    assert len(feed(client, user_id)) == 1
    outside = feed(client, user_id, date(2026, 11, 10), date(2026, 11, 11))
    assert len(outside) == 1 and outside[0]["occurrence_date"] == "2026-11-03"
    updated = client.patch(
        f"/api/v1/events/{identifier}", json={"title": "Revised series"}, headers=csrf(client)
    )
    assert updated.status_code == 200
    assert (
        feed(client, user_id, date(2026, 11, 10), date(2026, 11, 11))[0]["title"]
        == "Revised series"
    )
    assert client.delete(f"/api/v1/events/{identifier}", headers=csrf(client)).status_code == 204
    assert feed(client, user_id, date(2026, 11, 1), date(2026, 11, 12)) == []


def test_all_day_feed_and_busy_intervals_use_local_midnights_across_dst(
    agenda_client: TestClient,
) -> None:
    client = agenda_client
    user_id = login(client)
    created = client.post(
        "/api/v1/events",
        json={
            "title": "Day off",
            "start_at": "2026-11-01T00:00:00-04:00",
            "end_at": "2026-11-02T00:00:00-05:00",
            "timezone": "America/New_York",
            "all_day": True,
        },
        headers=csrf(client),
    )
    assert created.status_code == 201, created.text
    rows = feed(client, user_id, date(2026, 11, 1), date(2026, 11, 2))
    assert rows[0]["start_at"] == "2026-11-01" and rows[0]["end_at"] == "2026-11-02"

    async def run() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            user = await db.get(User, user_id)
            assert user is not None
            intervals = await local_event_intervals(
                db, user, datetime(2026, 11, 1, tzinfo=UTC), datetime(2026, 11, 3, tzinfo=UTC)
            )
            assert len(intervals) == 1
            assert (intervals[0][1] - intervals[0][0]).total_seconds() == 25 * 3600

    assert client.portal is not None
    client.portal.call(run)


def test_tasks_series_and_occurrences_are_owner_scoped(agenda_client: TestClient) -> None:
    client = agenda_client
    first_id = login(client)
    task = client.post("/api/v1/tasks", json={"title": "Private task"}, headers=csrf(client)).json()
    event = client.post("/api/v1/events", json=event_body(), headers=csrf(client)).json()
    client.app.state.settings.signup_mode = "open"  # type: ignore[union-attr]
    client.cookies.clear()
    second_id = login(client, "other@example.test")
    assert first_id != second_id
    assert client.get("/api/v1/tasks").json() == [] and client.get("/api/v1/events").json() == []
    for method, path, body in [
        ("GET", f"/api/v1/tasks/{task['id']}", None),
        ("PATCH", f"/api/v1/tasks/{task['id']}", {"title": "No"}),
        ("DELETE", f"/api/v1/tasks/{task['id']}", None),
        ("GET", f"/api/v1/events/{event['id']}", None),
        ("PATCH", f"/api/v1/events/{event['id']}", {"title": "No"}),
        ("DELETE", f"/api/v1/events/{event['id']}", None),
        ("PATCH", f"/api/v1/events/{event['id']}/occurrences/2026-11-02", {"title": "No"}),
        ("DELETE", f"/api/v1/events/{event['id']}/occurrences/2026-11-02", None),
    ]:
        assert client.request(method, path, json=body, headers=csrf(client)).status_code == 404
    assert (
        client.post(
            "/api/v1/events", json=event_body() | {"task_id": task["id"]}, headers=csrf(client)
        ).status_code
        == 404
    )
    assert feed(client, second_id) == []


def test_invalid_partial_changes_roll_back_and_occurrence_dates_are_verified(
    agenda_client: TestClient,
) -> None:
    client = agenda_client
    user_id = login(client)
    event = client.post("/api/v1/events", json=event_body(), headers=csrf(client)).json()
    identifier = event["id"]
    assert (
        client.patch(
            f"/api/v1/events/{identifier}",
            json={"end_at": "2026-11-02T08:00:00Z"},
            headers=csrf(client),
        ).status_code
        == 422
    )
    assert client.get(f"/api/v1/events/{identifier}").json()["end_at"] == event["end_at"]
    assert (
        client.delete(
            f"/api/v1/events/{identifier}/occurrences/2026-11-20", headers=csrf(client)
        ).status_code
        == 404
    )
    assert len(feed(client, user_id)) == 3


def test_cancelled_occurrence_can_be_restored_without_losing_its_move(
    agenda_client: TestClient,
) -> None:
    client = agenda_client
    user_id = login(client)
    created = client.post("/api/v1/events", json=event_body(), headers=csrf(client)).json()
    path = f"/api/v1/events/{created['id']}/occurrences/2026-11-03"
    assert (
        client.patch(
            path,
            json={"start_at": "2026-11-03T14:00:00Z", "end_at": "2026-11-03T15:00:00Z"},
            headers=csrf(client),
        ).status_code
        == 200
    )
    assert client.delete(path, headers=csrf(client)).status_code == 204
    assert len(feed(client, user_id)) == 2
    restored = client.patch(path, json={"title": "Restored"}, headers=csrf(client))
    assert restored.status_code == 200
    assert restored.json()["start_at"] == "2026-11-03T14:00:00+00:00"
    rows = feed(client, user_id)
    assert len(rows) == 3
    assert (
        next(row for row in rows if row["occurrence_date"] == "2026-11-03")["title"] == "Restored"
    )


def test_linked_google_all_day_block_uses_calendar_dates_and_remains_read_only(
    agenda_client: TestClient,
) -> None:
    client = agenda_client
    user_id = login(client)

    async def seed() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            db.add(
                PlanningRecord(
                    user_id=user_id,
                    kind="block",
                    payload={
                        "title": "Published day",
                        "start_at": "2026-11-01T04:00:00+00:00",
                        "end_at": "2026-11-02T05:00:00+00:00",
                        "status": "published",
                        "google_event_id": "google-id",
                        "calendar_all_day": True,
                        "calendar_timezone": "America/New_York",
                        "calendar_start_date": "2026-11-01",
                        "calendar_end_date": "2026-11-02",
                    },
                )
            )
            await db.commit()

    assert client.portal is not None
    client.portal.call(seed)
    rows = feed(client, user_id, date(2026, 11, 1), date(2026, 11, 2))
    assert len(rows) == 1
    assert rows[0]["all_day"] is True
    assert rows[0]["start_at"] == "2026-11-01" and rows[0]["end_at"] == "2026-11-02"
    assert rows[0]["timezone"] == "America/New_York" and rows[0]["editable"] is False
