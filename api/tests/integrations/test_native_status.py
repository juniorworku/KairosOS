"""Native heartbeat authentication, ownership, revocation and freshness."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_routes import csrf, login

from app.integrations.router import ext_router
from app.models.planning import PlanningRecord
from app.routers.native import router as native_router
from app.routers.planning import router as planning_router


@pytest.fixture
def client(auth_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    import app.integrations.router as module

    async def no_limit(request: object) -> None:
        pass

    monkeypatch.setattr(module, "redeem_rate_limit", no_limit)
    auth_app.include_router(ext_router)
    auth_app.include_router(native_router)
    auth_app.include_router(planning_router)
    with TestClient(auth_app) as value:
        yield value


def pair(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/ext/pair", headers=csrf(client))
    response = client.post(
        "/api/v1/ext/pair/redeem",
        json={
            "code": response.json()["code"],
            "label": "Linux native companion",
        },
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}


def idle() -> dict[str, object]:
    return {"device_id": str(uuid4()), "mode": "idle", "suspended_count": 0}


def test_reports_require_bearer_and_reads_require_owner_session(client: TestClient) -> None:
    assert client.get("/api/v1/native/devices").status_code == 401
    login(client)
    assert client.post("/api/v1/ext/native/status", json=idle()).status_code == 401
    bearer = pair(client)
    response = client.post("/api/v1/ext/native/status", json=idle(), headers=bearer)
    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert response.json()["reporting"] == "helper"
    assert len(client.get("/api/v1/native/devices").json()) == 1
    # A repeated device update cannot create unbounded rows for the same credential.
    assert client.post("/api/v1/ext/native/status", json=idle(), headers=bearer).status_code == 200
    assert len(client.get("/api/v1/native/devices").json()) == 1
    client.cookies.clear()
    assert client.get("/api/v1/native/devices", headers=bearer).status_code == 401


def test_blocking_report_must_match_the_current_session_and_deadline(client: TestClient) -> None:
    login(client)
    bearer = pair(client)
    focus = client.post("/api/v1/focus/start", json={"planned_minutes": 25}, headers=csrf(client))
    assert focus.status_code == 201
    session = focus.json()
    body = idle() | {
        "mode": "blocking",
        "suspended_count": 2,
        "session_id": session["id"],
        "ends_at": session["ends_at"],
    }
    assert client.post("/api/v1/ext/native/status", json=body, headers=bearer).status_code == 200
    for patch in (
        {"session_id": str(uuid4())},
        {"ends_at": (datetime.now(UTC) + timedelta(hours=4)).isoformat()},
    ):
        assert (
            client.post("/api/v1/ext/native/status", json=body | patch, headers=bearer).status_code
            == 409
        )
    client.post(f"/api/v1/focus/{session['id']}/end", json={}, headers=csrf(client))
    assert client.post("/api/v1/ext/native/status", json=body, headers=bearer).status_code == 409
    assert client.post("/api/v1/ext/native/status", json=idle(), headers=bearer).status_code == 200


def test_stale_reports_are_not_connected_and_revocation_hides_them(client: TestClient) -> None:
    login(client)
    bearer = pair(client)
    response = client.post("/api/v1/ext/native/status", json=idle(), headers=bearer)
    credential = response.json()["credential_id"]

    async def age() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            row = await db.scalar(
                select(PlanningRecord).where(PlanningRecord.kind == "native_device")
            )
            assert row is not None
            row.payload = row.payload | {
                "last_seen_at": (datetime.now(UTC) - timedelta(seconds=40)).isoformat()
            }
            await db.commit()

    assert client.portal is not None
    client.portal.call(age)
    assert client.get("/api/v1/native/devices").json()[0]["connected"] is False
    client.delete(f"/api/v1/ext/tokens/{credential}", headers=csrf(client))
    assert client.get("/api/v1/native/devices").json() == []
    assert client.post("/api/v1/ext/native/status", json=idle(), headers=bearer).status_code == 401


@pytest.mark.parametrize(
    "patch", [{"mode": "blocking"}, {"suspended_count": 1}, {"executables": ["private"]}]
)
def test_malformed_reports_and_application_details_are_rejected(
    client: TestClient, patch: dict[str, object]
) -> None:
    login(client)
    assert (
        client.post(
            "/api/v1/ext/native/status", json=idle() | patch, headers=pair(client)
        ).status_code
        == 422
    )


def test_pending_recovery_remains_visible_without_a_live_session(client: TestClient) -> None:
    login(client)
    body = idle() | {"mode": "error", "suspended_count": 2}
    response = client.post("/api/v1/ext/native/status", json=body, headers=pair(client))
    assert response.status_code == 200
    assert response.json()["suspended_count"] == 2
    report = client.get("/api/v1/native/devices").json()[0]
    assert report["mode"] == "error" and report["session_id"] is None
