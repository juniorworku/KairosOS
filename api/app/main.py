"""Application factory and infrastructure health endpoints."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from starlette.responses import Response

from app.config import Settings, get_settings
from app.db import create_engine

logger = logging.getLogger("kairos.health")
Check = Callable[[], Awaitable[bool]]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: Literal["ready", "unavailable"]
    checks: dict[str, bool]


def create_app(
    settings: Settings | None = None,
    *,
    database_check: Check | None = None,
    redis_check: Check | None = None,
) -> FastAPI:
    config = settings or get_settings()
    engine = create_engine(config.database_url)
    redis: Redis = Redis.from_url(config.redis_url)

    async def check_database() -> bool:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True

    async def check_redis() -> bool:
        return bool(await redis.ping())

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await redis.aclose()
            await engine.dispose()

    app = FastAPI(title="Kairos API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[config.app_base_url],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    @app.middleware("http")
    async def response_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Request-ID"] = str(uuid4())
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if config.app_env in {"staging", "production"}:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.get("/healthz", response_model=HealthResponse, tags=["Infrastructure"])
    async def healthz() -> HealthResponse:
        return HealthResponse()

    async def run_check(check: Check) -> bool:
        try:
            return await asyncio.wait_for(check(), timeout=config.readiness_timeout_seconds)
        except Exception:
            # Exception text can contain a connection URL. Never log it.
            logger.warning("infrastructure_readiness_check_failed")
            return False

    @app.get(
        "/readyz",
        response_model=ReadinessResponse,
        responses={503: {"model": ReadinessResponse}},
        tags=["Infrastructure"],
    )
    async def readyz() -> JSONResponse:
        database_ok, redis_ok = await asyncio.gather(
            run_check(database_check or check_database), run_check(redis_check or check_redis)
        )
        ready = database_ok and redis_ok
        body = ReadinessResponse(
            status="ready" if ready else "unavailable",
            checks={"database": database_ok, "redis": redis_ok},
        )
        return JSONResponse(status_code=200 if ready else 503, content=body.model_dump())

    return app


app = create_app()
