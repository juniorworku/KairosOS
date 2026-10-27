"""Email delivery task; queue payloads and task events redact email arguments."""

import asyncio

from sqlalchemy import delete, or_
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.service import send_magic_link
from app.config import get_settings
from app.db import create_engine
from app.jobs.celery_app import celery_app
from app.models.auth import Invite, LoginSession, MagicLinkToken, OAuthState, now


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


def purge_expired_auth() -> None:
    async def run() -> None:
        config = get_settings()
        engine = create_engine(config.database_url)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as db:
                moment = now()
                await db.execute(
                    delete(LoginSession).where(
                        or_(
                            LoginSession.expires_at <= moment,
                            LoginSession.absolute_expires_at <= moment,
                            LoginSession.revoked_at.is_not(None),
                        )
                    )
                )
                await db.execute(
                    delete(MagicLinkToken).where(
                        or_(
                            MagicLinkToken.expires_at <= moment,
                            MagicLinkToken.consumed_at.is_not(None),
                        )
                    )
                )
                await db.execute(
                    delete(OAuthState).where(
                        or_(
                            OAuthState.expires_at <= moment,
                            OAuthState.consumed_at.is_not(None),
                        )
                    )
                )
                await db.execute(
                    delete(Invite).where(
                        or_(
                            Invite.expires_at <= moment,
                            Invite.revoked_at.is_not(None),
                        )
                    )
                )
                await db.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


celery_app.task(name="kairos.auth.purge_expired", ignore_result=True)(purge_expired_auth)
celery_app.conf.beat_schedule = {
    **(celery_app.conf.beat_schedule or {}),
    "purge-expired-auth-daily": {"task": "kairos.auth.purge_expired", "schedule": 86400.0},
}
