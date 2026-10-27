"""Database and authenticated-user dependencies used by every domain router."""

from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models.auth import LoginSession, User, now
from app.security import SESSION_COOKIE, require_csrf, token_hash


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    factory = cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)
    async with factory() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise


async def current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    config: Annotated[Settings, Depends(get_settings)],
) -> User:
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        raise HTTPException(401, "Sign in to continue.")
    current_time = now()
    session = await db.scalar(
        select(LoginSession).where(
            LoginSession.token_hash == token_hash(token),
            LoginSession.revoked_at.is_(None),
            LoginSession.expires_at > current_time,
            LoginSession.absolute_expires_at > current_time,
        )
    )
    if session is None:
        raise HTTPException(401, "Your session ended. Sign in again.")
    user = await db.get(User, session.user_id)
    if user is None or user.disabled_at is not None:
        raise HTTPException(401, "Your session ended. Sign in again.")
    require_csrf(request, config, session.csrf_hash)
    session.last_used_at = current_time
    session.expires_at = min(current_time + timedelta(days=30), session.absolute_expires_at)
    request.state.login_session = session
    await db.commit()
    return user


async def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if user.role not in {"admin", "owner"}:
        raise HTTPException(403, "You do not have access to this page.")
    return user
