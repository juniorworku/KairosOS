"""Isolated PostgreSQL test schemas. Set TEST_DATABASE_URL to run database tests."""

import importlib
import os
import pkgutil
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.models
from app.auth.limits import MemoryLimiter
from app.auth.router import router
from app.auth.service import initialize_auth
from app.config import Settings
from app.db import Base


@dataclass
class CapturedEmail:
    to: str
    subject: str
    text: str
    html: str


class CaptureSender:
    def __init__(self) -> None:
        self.messages: list[CapturedEmail] = []

    async def send(self, to: str, subject: str, text: str, html: str) -> None:
        self.messages.append(CapturedEmail(to, subject, text, html))


@pytest.fixture
def auth_app() -> FastAPI:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL for isolated PostgreSQL integration tests")
    settings = Settings(
        app_env="test",
        database_url=url,
        owner_email="owner@example.test",
        app_base_url="http://testserver",
        secret_key="test-secret-key-32-bytes-minimum-only",
        _env_file=None,
    )
    # Register every domain table so export and deletion tests exercise actual cascades.
    for module in pkgutil.iter_modules(app.models.__path__):
        importlib.import_module(f"app.models.{module.name}")
    importlib.import_module("app.integrations.models")
    schema = f"test_{uuid4().hex}"
    admin_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": schema}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            await initialize_auth(factory, settings)
            yield
        finally:
            await engine.dispose()
            async with admin_engine.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin_engine.dispose()

    application = FastAPI(lifespan=lifespan)
    application.state.settings = settings
    application.state.session_factory = factory
    application.state.auth_limiter = MemoryLimiter()
    application.state.email_sender = CaptureSender()
    application.include_router(router)
    return application


@pytest.fixture
def auth_client(auth_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(auth_app) as client:
        yield client
