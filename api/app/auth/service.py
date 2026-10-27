"""Account linking and scanner-safe, single-use sign-in tokens."""

import html
import logging
from datetime import timedelta

from fastapi import HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.email import EmailSender, get_sender
from app.config import Settings
from app.models.auth import (
    AuditLog,
    AuthIdentity,
    Invite,
    LoginSession,
    MagicLinkToken,
    OwnerSeed,
    Plan,
    User,
    identifier,
    now,
)
from app.security import CSRF_COOKIE, SESSION_COOKIE, ip_hash, random_token, set_cookie, token_hash

logger = logging.getLogger("kairos.auth")

PLAN_QUOTAS: dict[str, dict[str, int]] = {
    "owner": {
        "ai.calls": 10000,
        "ai.output_tokens": 10000000,
        "ai.retro": 1000,
        "ai.milestone_parse": 1000,
        "ai.chat_messages": 10000,
    },
    "free": {
        "ai.calls": 10,
        "ai.output_tokens": 30000,
        "ai.retro": 4,
        "ai.milestone_parse": 4,
        "ai.chat_messages": 10,
    },
    "plus": {
        "ai.calls": 100,
        "ai.output_tokens": 300000,
        "ai.retro": 20,
        "ai.milestone_parse": 40,
        "ai.chat_messages": 100,
    },
}


async def initialize_auth(factory: async_sessionmaker[AsyncSession], config: Settings) -> None:
    """Seed idempotently after migrations; never create schema at application startup."""
    async with factory() as db:
        for key, quotas in PLAN_QUOTAS.items():
            entitlements = {
                f"feature.{feature}": key != "free"
                for feature in (
                    "companion",
                    "activity_log",
                    "calendar_audit",
                    "retro",
                    "intervention",
                    "smart_env",
                )
            }
            await db.execute(
                insert(Plan)
                .values(
                    id=identifier(),
                    key=key,
                    name=key.title(),
                    quotas=quotas,
                    entitlements=entitlements,
                    is_default=key == "free",
                )
                .on_conflict_do_nothing(index_elements=["key"])
            )
        if config.owner_email:
            owner_plan = await db.scalar(select(Plan).where(Plan.key == "owner"))
            assert owner_plan is not None
            # Existing users are never silently promoted by an environment change.
            first_seed = await db.scalar(
                insert(OwnerSeed)
                .values(
                    email_hash=token_hash(config.owner_email),
                )
                .on_conflict_do_nothing(index_elements=["email_hash"])
                .returning(OwnerSeed.email_hash)
            )
            if first_seed is not None:
                await db.execute(
                    insert(User)
                    .values(
                        id=identifier(),
                        email=config.owner_email,
                        name="",
                        role="owner",
                        plan_id=owner_plan.id,
                    )
                    .on_conflict_do_nothing(index_elements=["email"])
                )
        await db.commit()


async def eligible(db: AsyncSession, email: str, config: Settings) -> bool:
    user = await db.scalar(select(User).where(User.email == email))
    if user is not None:
        return user.disabled_at is None
    if config.signup_mode == "open":
        return True
    if config.signup_mode == "invite":
        invite = await db.scalar(
            select(Invite).where(
                Invite.email == email,
                Invite.expires_at > now(),
                Invite.used_at.is_(None),
                Invite.revoked_at.is_(None),
            )
        )
        return invite is not None
    return False


async def verified_user(
    db: AsyncSession,
    email: str,
    provider: str,
    provider_id: str,
    config: Settings,
    *,
    name: str = "",
) -> User | None:
    if not await eligible(db, email, config):
        return None
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        plan = await db.scalar(select(Plan).where(Plan.is_default.is_(True)))
        if plan is None:
            raise HTTPException(503, "Sign-in is not ready. Try again later.")
        role = "user"
        plan_id = plan.id
        if config.signup_mode == "invite":
            invite = await db.scalar(
                update(Invite)
                .where(
                    Invite.email == email,
                    Invite.expires_at > now(),
                    Invite.used_at.is_(None),
                    Invite.revoked_at.is_(None),
                )
                .values(used_at=now())
                .returning(Invite)
            )
            if invite is None:
                return None
            role, plan_id = invite.role, invite.plan_id
        await db.execute(
            insert(User)
            .values(
                id=identifier(),
                email=email,
                name=name[:120],
                role=role,
                plan_id=plan_id,
                email_verified_at=now(),
            )
            .on_conflict_do_nothing(index_elements=["email"])
        )
        user = await db.scalar(select(User).where(User.email == email))
        assert user is not None
    if user.disabled_at is not None:
        return None
    identity = await db.scalar(
        select(AuthIdentity).where(
            AuthIdentity.provider == provider,
            AuthIdentity.provider_user_id == provider_id,
        )
    )
    if identity is not None and identity.user_id != user.id:
        raise HTTPException(401, "This sign-in could not be verified.")
    if identity is None:
        await db.execute(
            insert(AuthIdentity)
            .values(
                id=identifier(),
                user_id=user.id,
                provider=provider,
                provider_user_id=provider_id,
            )
            .on_conflict_do_nothing(index_elements=["provider", "provider_user_id"])
        )
        linked_user_id = await db.scalar(
            select(AuthIdentity.user_id).where(
                AuthIdentity.provider == provider,
                AuthIdentity.provider_user_id == provider_id,
            )
        )
        if linked_user_id != user.id:
            raise HTTPException(401, "This sign-in could not be verified.")
    user.email_verified_at = now()
    return user


async def send_magic_link(
    factory: async_sessionmaker[AsyncSession],
    config: Settings,
    email: str,
    source_ip_hash: str,
    sender: EmailSender | None = None,
    *,
    raise_on_failure: bool = False,
) -> None:
    try:
        async with factory() as db:
            if not await eligible(db, email, config):
                return
            token = random_token()
            await db.execute(
                update(MagicLinkToken)
                .where(
                    MagicLinkToken.email == email,
                    MagicLinkToken.consumed_at.is_(None),
                )
                .values(consumed_at=now())
            )
            db.add(
                MagicLinkToken(
                    email=email,
                    token_hash=token_hash(token),
                    created_ip_hash=source_ip_hash,
                    expires_at=now() + timedelta(minutes=config.magic_link_ttl_min),
                )
            )
            await db.commit()
        link = f"{config.app_base_url.rstrip('/')}/auth/confirm?token={token}"
        text = (
            f"Sign in to Kairos\n\n{link}\n\nThis link expires in "
            f"{config.magic_link_ttl_min} minutes. If you did not request it, ignore this email."
        )
        body = (
            "<h1>Sign in to Kairos</h1><p>Use the button below to sign in.</p>"
            f'<p><a href="{html.escape(link, quote=True)}">Sign in to Kairos</a></p>'
            f"<p>This link expires in {config.magic_link_ttl_min} minutes. "
            "If you did not request it, ignore this email.</p>"
        )
        await (sender or get_sender(config)).send(email, "Your Kairos sign-in link", text, body)
    except Exception:
        logger.warning("magic_link_delivery_failed")
        if raise_on_failure:
            raise RuntimeError("Email delivery failed") from None


async def consume_magic(db: AsyncSession, token: str, config: Settings) -> User:
    record = await db.scalar(
        update(MagicLinkToken)
        .where(
            MagicLinkToken.token_hash == token_hash(token),
            MagicLinkToken.expires_at > now(),
            MagicLinkToken.consumed_at.is_(None),
        )
        .values(consumed_at=now())
        .returning(MagicLinkToken)
    )
    if record is None:
        raise HTTPException(
            401, "This link has expired or has already been used. Request a new one."
        )
    user = await verified_user(db, record.email, "email", record.email, config)
    if user is None:
        await db.commit()
        raise HTTPException(401, "This sign-in could not be completed. Request a new link.")
    return user


async def create_session(
    db: AsyncSession,
    user: User,
    request: Request,
    response: Response,
    config: Settings,
) -> None:
    token, csrf = random_token(), random_token()
    current_time = now()
    db.add(
        LoginSession(
            user_id=user.id,
            token_hash=token_hash(token),
            csrf_hash=token_hash(csrf),
            expires_at=current_time + timedelta(days=30),
            absolute_expires_at=current_time + timedelta(days=90),
            user_agent=request.headers.get("user-agent", "")[:300],
            ip_hash=ip_hash(request, config),
        )
    )
    await db.commit()
    set_cookie(response, config, SESSION_COOKIE, token, http_only=True, max_age=90 * 86400)
    set_cookie(response, config, CSRF_COOKIE, csrf, http_only=False, max_age=90 * 86400)


async def set_plan(db: AsyncSession, user: User, plan: Plan, actor: User) -> None:
    old = user.plan_id
    user.plan_id = plan.id
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="user.plan_changed",
            target_type="user",
            target_id=user.id,
            details={"from": old, "to": plan.id},
        )
    )


async def revoke_user_sessions(db: AsyncSession, user_id: str) -> None:
    await db.execute(
        update(LoginSession)
        .where(
            LoginSession.user_id == user_id,
            LoginSession.revoked_at.is_(None),
        )
        .values(revoked_at=now())
    )
    # Integration credentials check the user's disabled flag on every authenticated call.
    # Token tables registered by other modules are also revoked immediately when supported.
    from app.db import Base

    for name in (
        "extension_tokens",
        "companion_tokens",
        "extension_pair_codes",
        "companion_pair_codes",
    ):
        table = Base.metadata.tables.get(name)
        if table is not None and "user_id" in table.c:
            if "revoked_at" in table.c:
                await db.execute(
                    table.update().where(table.c.user_id == user_id).values(revoked_at=now())
                )
            else:
                await db.execute(table.delete().where(table.c.user_id == user_id))
