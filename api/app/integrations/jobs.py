"""Idempotent periodic calendar refresh. Row locks serialize manual and worker syncs."""

import asyncio
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.db import create_engine
from app.integrations.config import IntegrationSettings
from app.integrations.models import CalendarConnection

if TYPE_CHECKING:
    from celery import Celery


async def sync_connections() -> dict[str, int]:
    from app.integrations.router import sync_user

    config = IntegrationSettings()
    if not config.calendar_configured:
        return {"synced": 0, "failed": 0}
    engine = create_engine(get_settings().database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    success = failed = 0
    try:
        async with factory() as db:
            ids = list(
                (
                    await db.scalars(
                        select(CalendarConnection.user_id).where(
                            CalendarConnection.status == "active"
                        )
                    )
                ).all()
            )
        for user_id in ids:
            async with factory() as db:
                try:
                    await sync_user(db, user_id)
                    success += 1
                except Exception:
                    # Provider responses can contain credentials; do not log exception text.
                    await db.rollback()
                    failed += 1
        return {"synced": success, "failed": failed}
    finally:
        await engine.dispose()


def sync_calendars() -> dict[str, int]:
    return asyncio.run(sync_connections())


def configure_jobs(app: "Celery") -> None:
    app.task(name="kairos.sync_calendars")(sync_calendars)
    app.conf.beat_schedule = {
        **(app.conf.beat_schedule or {}),
        "sync-calendar-every-ten-minutes": {"task": "kairos.sync_calendars", "schedule": 600.0},
    }
