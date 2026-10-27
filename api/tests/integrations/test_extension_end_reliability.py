"""Offline extension stop requests must never stop a newer focus session."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_routes import csrf, login

from app.integrations.router import ext_router
from app.models.planning import PlanningRecord
from app.routers.planning import router


@pytest.fixture
def extension_client(auth_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    import app.integrations.router as module

    async def no_limit(request: object) -> None:
        pass

    monkeypatch.setattr(module, "redeem_rate_limit", no_limit)
    auth_app.include_router(ext_router)
    auth_app.include_router(router)
    with TestClient(auth_app) as client:
        yield client


def paired_headers(client: TestClient) -> dict[str, str]:
    pair = client.post("/api/v1/ext/pair", headers=csrf(client))
    assert pair.status_code == 200
    token = client.post("/api/v1/ext/pair/redeem", json={"code": pair.json()["code"]})
    assert token.status_code == 200
    return {"Authorization": f"Bearer {token.json()['token']}"}


def test_expired_paired_end_corrects_original_without_stopping_newer_session(
    extension_client: TestClient,
) -> None:
    client = extension_client
    login(client)
    bearer = paired_headers(client)
    old = client.post(
        "/api/v1/focus/start", json={"planned_minutes": 25}, headers=csrf(client)
    ).json()
    began = datetime.now(UTC) - timedelta(minutes=30)

    async def age() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            row = await db.get(PlanningRecord, old["id"])
            assert row is not None
            row.payload = {
                **row.payload,
                "started_at": began.isoformat(),
                "ends_at": (began + timedelta(minutes=25)).isoformat(),
            }
            await db.commit()

    assert client.portal is not None
    client.portal.call(age)
    newer = client.post("/api/v1/focus/start", json={"planned_minutes": 25}, headers=csrf(client))
    assert newer.status_code == 201
    newer_id = newer.json()["id"]
    body = {"session_id": old["id"], "ended_at": (began + timedelta(minutes=5)).isoformat()}
    for _ in range(2):
        response = client.post("/api/v1/ext/end", json=body, headers=bearer)
        assert response.status_code == 200
        assert client.get("/api/v1/focus/active").json()["id"] == newer_id
    history = client.get("/api/v1/focus/sessions").json()["items"]
    original = next(row for row in history if row["id"] == old["id"])
    assert original["actual_minutes"] == 5
    assert (
        client.post(
            "/api/v1/ext/end", json={"session_id": str(uuid4())}, headers=bearer
        ).status_code
        == 200
    )
    assert client.get("/api/v1/focus/active").json()["id"] == newer_id


def test_extension_end_rejects_naive_timestamp_without_mutating_session(
    extension_client: TestClient,
) -> None:
    client = extension_client
    login(client)
    bearer = paired_headers(client)
    session = client.post("/api/v1/focus/start", json={}, headers=csrf(client)).json()
    body = {"session_id": session["id"], "ended_at": datetime.now().isoformat()}
    assert client.post("/api/v1/ext/end", json=body, headers=bearer).status_code == 422
    assert client.get("/api/v1/focus/active").json()["id"] == session["id"]
