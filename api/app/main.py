"""Application factory and infrastructure health endpoints."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.exceptions import HTTPException
from starlette.responses import Response

from app.auth.router import router as auth_router
from app.auth.service import initialize_auth
from app.config import Settings, get_settings
from app.db import create_engine
from app.integrations.coach import coach_router
from app.integrations.config import IntegrationSettings
from app.integrations.router import calendar_router, disconnect_calendar_for_user, ext_router
from app.models.auth import User
from app.observability import configure_logging
from app.routers.planning import router as planning_router

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
    configure_logging()
    config = settings or get_settings()
    engine = create_engine(config.database_url)
    redis: Redis = Redis.from_url(config.redis_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def check_database() -> bool:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True

    async def check_redis() -> bool:
        return bool(await redis.ping())

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            if config.owner_email or config.app_env in {"staging", "production"}:
                await initialize_auth(factory, config)
            yield
        finally:
            await redis.aclose()
            await engine.dispose()

    app = FastAPI(title="Kairos API", version="0.1.0", lifespan=lifespan)
    app.state.settings = config
    app.state.session_factory = factory

    async def before_delete(db: AsyncSession, user: User) -> None:
        await disconnect_calendar_for_user(db, user.id)

    app.state.before_account_delete = before_delete
    app.include_router(auth_router)
    app.include_router(planning_router)
    app.include_router(calendar_router)
    app.include_router(ext_router)
    app.include_router(coach_router)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, error: HTTPException) -> JSONResponse:
        detail = error.detail
        value = (
            detail
            if isinstance(detail, dict)
            else {"code": "request_failed", "message": str(detail), "details": {}}
        )
        return JSONResponse(
            status_code=error.status_code, content={"error": value}, headers=error.headers
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        messages = "; ".join(str(item["msg"]) for item in error.errors())
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "validation_error", "message": messages, "details": {}}},
        )

    integration_config = IntegrationSettings()
    origins = [config.app_base_url]
    if integration_config.extension_id:
        origins.append(f"chrome-extension://{integration_config.extension_id}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Authorization"],
    )

    @app.middleware("http")
    async def response_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = perf_counter()
        request_id = str(uuid4())
        response = await call_next(request)
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000),
            },
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = request_id
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
