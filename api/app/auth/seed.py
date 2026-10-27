"""Idempotent owner setup, using OWNER_EMAIL and the configured database."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.service import initialize_auth
from app.config import get_settings
from app.db import create_engine


async def seed_owner() -> None:
    config = get_settings()
    if not config.owner_email:
        raise ValueError("Set OWNER_EMAIL before running owner setup.")
    engine = create_engine(config.database_url)
    try:
        await initialize_auth(async_sessionmaker(engine, expire_on_commit=False), config)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_owner())
    print("Owner setup checked. Existing accounts and deletion choices are preserved.")
