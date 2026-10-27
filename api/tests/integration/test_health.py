import asyncio
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


async def passing_check() -> bool:
    return True


async def failing_check() -> bool:
    raise ConnectionError("secret connection details must not leak")


async def hanging_check() -> bool:
    await asyncio.sleep(10)
    return True


def test_liveness_without_infrastructure() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-request-id"]


def test_readiness_checks_both_dependencies() -> None:
    with TestClient(create_app(database_check=passing_check, redis_check=passing_check)) as client:
        response = client.get("/readyz")
        assert response.status_code == 200
        assert response.json() == {"status": "ready", "checks": {"database": True, "redis": True}}


def test_failed_readiness_is_sanitized() -> None:
    with TestClient(create_app(database_check=failing_check, redis_check=passing_check)) as client:
        response = client.get("/readyz")
        assert response.status_code == 503
        assert response.json()["checks"] == {"database": False, "redis": True}
        assert "secret" not in response.text


def test_production_hsts() -> None:
    with patch("app.main.initialize_auth", new_callable=AsyncMock) as initialize:
        with TestClient(
            create_app(
                Settings(
                    app_env="production",
                    app_base_url="https://kairos.example",
                    secret_key="x" * 32,
                    smtp_starttls=True,
                )
            )
        ) as client:
            assert "max-age" in client.get("/healthz").headers["strict-transport-security"]
        initialize.assert_awaited_once()


def test_readiness_timeout_is_unavailable() -> None:
    app = create_app(
        Settings(readiness_timeout_seconds=0.001),
        database_check=hanging_check,
        redis_check=passing_check,
    )
    with TestClient(app) as client:
        response = client.get("/readyz")
        assert response.status_code == 503
        assert response.json()["checks"]["database"] is False


def test_cors_only_allows_web_origin() -> None:
    with TestClient(create_app()) as client:
        allowed = client.get("/healthz", headers={"Origin": "http://localhost:5173"})
        denied = client.get("/healthz", headers={"Origin": "https://untrusted.example"})
        assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert "access-control-allow-origin" not in denied.headers
