"""Email delivery task; queue payloads and task events redact email arguments."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.service import send_magic_link
from app.config import get_settings
from app.db import create_engine
from app.jobs.celery_app import celery_app


def deliver_magic(email: str, source_ip_hash: str) -> None:
    async def run() -> None:
        config = get_settings()
        engine = create_engine(config.database_url)
        try:
            await send_magic_link(
                async_sessionmaker(engine, expire_on_commit=False),
                config,
                email,
                source_ip_hash,
                raise_on_failure=True,
            )
        finally:
            await engine.dispose()

    asyncio.run(run())


celery_app.task(
    name="kairos.auth.send_magic_link",
    ignore_result=True,
    autoretry_for=(RuntimeError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)(deliver_magic)
