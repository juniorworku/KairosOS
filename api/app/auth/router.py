"""Web-session authentication, account management and role-checked administration."""

import hmac
import logging
from datetime import timedelta
from typing import Annotated, Any, cast
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.email import EmailSender
from app.auth.google import verify_google_code
from app.auth.limits import Limiter, RedisLimiter
from app.auth.schemas import (
    AdminProfile,
    AdminUserUpdate,
    AuthConfig,
    CSRFResponse,
    EmailRequest,
    InviteRequest,
    MagicVerify,
    MessageResponse,
    Profile,
    ProfileUpdate,
    SessionInfo,
)
from app.auth.service import (
    consume_magic,
    create_session,
    revoke_user_sessions,
    send_magic_link,
    set_plan,
    verified_user,
)
from app.config import Settings
from app.db import Base
from app.deps import admin_user, current_user, get_db, get_settings
from app.models.auth import (
    AuditLog,
    Invite,
    LoginSession,
    MagicLinkToken,
    OAuthState,
    Plan,
    User,
    now,
)
from app.security import (
    CSRF_COOKIE,
    OAUTH_COOKIE,
    clear_cookies,
    ip_hash,
    pkce_challenge,
    random_token,
    require_csrf,
    safe_next,
    set_cookie,
    token_hash,
)

router = APIRouter(prefix="/api/v1", tags=["Accounts"])
DB = Annotated[AsyncSession, Depends(get_db)]
Config = Annotated[Settings, Depends(get_settings)]
SignedIn = Annotated[User, Depends(current_user)]
Admin = Annotated[User, Depends(admin_user)]
logger = logging.getLogger("kairos.auth")
GENERIC_MESSAGE = "If this email can sign in, we sent a link."


def checked_id(value: str) -> str:
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise HTTPException(404, "Record not found.") from exc


def limiter(request: Request, config: Settings) -> Limiter:
    injected = getattr(request.app.state, "auth_limiter", None)
    return cast(Limiter, injected) if injected is not None else RedisLimiter(config.redis_url)


@router.get("/auth/config", response_model=AuthConfig)
async def auth_config(config: Config) -> AuthConfig:
    return AuthConfig(
        google_enabled=bool(config.google_client_id and config.google_client_secret),
        email_enabled=True,
        development_owner_email=config.owner_email if config.app_env == "dev" else None,
    )


@router.get("/auth/csrf", response_model=CSRFResponse)
async def csrf(request: Request, response: Response, config: Config) -> CSRFResponse:
    # Preserve a session's bound CSRF token. Replacing it would invalidate another tab.
    token = request.cookies.get(CSRF_COOKIE) or random_token()
    set_cookie(response, config, CSRF_COOKIE, token, http_only=False, max_age=90 * 86400)
    response.headers["Cache-Control"] = "no-store"
    return CSRFResponse(csrf_token=token)


@router.post("/auth/magic/request", response_model=MessageResponse, status_code=202)
async def magic_request(
    payload: EmailRequest,
    request: Request,
    config: Config,
    background: BackgroundTasks,
) -> MessageResponse:
    require_csrf(request, config)
    try:
        rate = limiter(request, config)
        email_key = token_hash(payload.email)
        allowed = await rate.allow(f"email:{email_key}:minute", 1, 60)
        allowed = await rate.allow(f"email:{email_key}:hour", 5, 3600) and allowed
        source_hash = ip_hash(request, config)
        allowed = await rate.allow(f"ip:{source_hash}", 20, 3600) and allowed
        if allowed:
            if config.app_env in {"dev", "test"}:
                factory = cast(async_sessionmaker[AsyncSession], request.app.state.session_factory)
                sender = cast(EmailSender | None, getattr(request.app.state, "email_sender", None))
                background.add_task(
                    send_magic_link, factory, config, payload.email, source_hash, sender
                )
            else:
                from app.jobs.celery_app import celery_app

                celery_app.send_task(
                    "kairos.auth.send_magic_link",
                    args=[payload.email, source_hash],
                    argsrepr="[redacted]",
                )
    except Exception:
        # Fail closed, with the same response when Redis/queue/email is unavailable.
        logger.warning("magic_link_request_not_queued")
    return MessageResponse(message=GENERIC_MESSAGE)


@router.get("/auth/magic", response_model=MessageResponse)
async def magic_confirmation(
    token: Annotated[str, Query(min_length=20, max_length=200)],
) -> MessageResponse:
    # Security scanners may follow this URL. Verification happens only on POST.
    return MessageResponse(message="Open Kairos and choose Sign in to use this link.")


@router.post("/auth/magic/verify", response_model=Profile)
async def magic_verify(
    payload: MagicVerify,
    request: Request,
    response: Response,
    db: DB,
    config: Config,
) -> Profile:
    require_csrf(request, config)
    try:
        if not await limiter(request, config).allow(f"verify:{ip_hash(request, config)}", 30, 3600):
            raise HTTPException(429, "Too many attempts. Try again later.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "Sign-in is temporarily unavailable. Try again later.") from exc
    user = await consume_magic(db, payload.token, config)
    await create_session(db, user, request, response, config)
    response.headers["Cache-Control"] = "no-store"
    return Profile.model_validate(user)


@router.get("/auth/google/login")
async def google_login(
    request: Request, db: DB, config: Config, next: str | None = None
) -> RedirectResponse:
    safe_next(next)
    if not config.google_client_id or not config.google_client_secret:
        raise HTTPException(503, "Google sign-in is not connected yet. Use an email link.")
    try:
        if not await limiter(request, config).allow(f"google:{ip_hash(request, config)}", 30, 3600):
            raise HTTPException(429, "Too many attempts. Try again later.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "Sign-in is temporarily unavailable.") from exc
    state, nonce, verifier = random_token(), random_token(), random_token()
    db.add(
        OAuthState(
            id=token_hash(state),
            code_verifier=verifier,
            nonce_hash=token_hash(nonce),
            expires_at=now() + timedelta(minutes=10),
        )
    )
    await db.commit()
    query = urlencode(
        {
            "client_id": config.google_client_id,
            "redirect_uri": config.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": pkce_challenge(verifier),
            "code_challenge_method": "S256",
        }
    )
    response = RedirectResponse(
        f"https://accounts.google.com/o/oauth2/v2/auth?{query}", status_code=302
    )
    set_cookie(response, config, OAUTH_COOKIE, state, http_only=True, max_age=600)
    return response


@router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    db: DB,
    config: Config,
    code: str = "",
    state: str = "",
    error: str = "",
) -> RedirectResponse:
    cookie = request.cookies.get(OAUTH_COOKIE, "")
    if error or not code or not state or not cookie or not hmac.compare_digest(cookie, state):
        raise HTTPException(401, "Google sign-in could not be verified. Try again.")
    record = await db.scalar(
        update(OAuthState)
        .where(
            OAuthState.id == token_hash(state),
            OAuthState.expires_at > now(),
            OAuthState.consumed_at.is_(None),
        )
        .values(consumed_at=now())
        .returning(OAuthState)
    )
    if record is None:
        raise HTTPException(401, "This sign-in has expired. Try again.")
    identity = await verify_google_code(code, record.code_verifier, record.nonce_hash, config)
    user = await verified_user(
        db, identity["email"], "google", identity["subject"], config, name=identity["name"]
    )
    if user is None:
        await db.commit()
        raise HTTPException(401, "This sign-in could not be completed.")
    response = RedirectResponse(f"{config.app_base_url.rstrip('/')}/today", status_code=302)
    await create_session(db, user, request, response, config)
    response.delete_cookie(OAUTH_COOKIE, domain=config.cookie_domain or None)
    return response


@router.post("/auth/logout", response_model=MessageResponse)
async def logout(
    request: Request, response: Response, user: SignedIn, db: DB, config: Config
) -> MessageResponse:
    session = cast(LoginSession, request.state.login_session)
    session.revoked_at = now()
    await db.commit()
    clear_cookies(response, config)
    return MessageResponse(message="You are signed out.")


@router.get("/me", response_model=Profile)
async def me(user: SignedIn, response: Response) -> Profile:
    response.headers["Cache-Control"] = "no-store"
    return Profile.model_validate(user)


@router.patch("/me", response_model=Profile)
async def update_me(payload: ProfileUpdate, user: SignedIn, db: DB) -> Profile:
    start = payload.work_start or user.work_start
    end = payload.work_end or user.work_end
    if end <= start:
        raise HTTPException(422, "Work hours must end after they start.")
    for key, value in payload.model_dump(
        exclude_none=True, exclude={"onboarding_completed"}
    ).items():
        setattr(user, key, value)
    if payload.onboarding_completed is True:
        user.onboarding_completed_at = now()
    await db.commit()
    return Profile.model_validate(user)


@router.get("/me/sessions", response_model=list[SessionInfo])
async def my_sessions(request: Request, user: SignedIn, db: DB) -> list[SessionInfo]:
    sessions = await db.scalars(
        select(LoginSession)
        .where(
            LoginSession.user_id == user.id,
            LoginSession.revoked_at.is_(None),
            LoginSession.expires_at > now(),
            LoginSession.absolute_expires_at > now(),
        )
        .order_by(LoginSession.last_used_at.desc())
        .limit(100)
    )
    current = cast(LoginSession, request.state.login_session)
    return [
        SessionInfo(
            id=s.id,
            user_agent=s.user_agent,
            created_at=s.created_at,
            last_used_at=s.last_used_at,
            expires_at=s.expires_at,
            current=s.id == current.id,
        )
        for s in sessions
    ]


@router.delete("/me/sessions/{session_id}", response_model=MessageResponse)
async def revoke_session(
    session_id: str, request: Request, response: Response, user: SignedIn, db: DB, config: Config
) -> MessageResponse:
    session = await db.scalar(
        select(LoginSession).where(
            LoginSession.id == checked_id(session_id),
            LoginSession.user_id == user.id,
        )
    )
    if session is None:
        raise HTTPException(404, "Session not found.")
    session.revoked_at = now()
    await db.commit()
    if session.id == cast(LoginSession, request.state.login_session).id:
        clear_cookies(response, config)
    return MessageResponse(message="Session ended.")


@router.post("/me/sessions/revoke-all", response_model=MessageResponse)
async def revoke_all(response: Response, user: SignedIn, db: DB, config: Config) -> MessageResponse:
    await revoke_user_sessions(db, user.id)
    await db.commit()
    clear_cookies(response, config)
    return MessageResponse(message="You are signed out on every device.")


@router.get("/me/export")
async def export_me(user: SignedIn, db: DB, response: Response) -> dict[str, Any]:
    private_tables = {
        "sessions",
        "auth_identities",
        "magic_link_tokens",
        "oauth_states",
        "calendar_oauth_states",
        "extension_pair_codes",
        "extension_tokens",
        "companion_pair_codes",
        "companion_tokens",
    }
    data: dict[str, Any] = {"profile": Profile.model_validate(user).model_dump(mode="json")}
    for name, table in Base.metadata.tables.items():
        if name in private_tables or "user_id" not in table.c:
            continue
        columns = [
            column
            for column in table.c
            if not any(
                private in column.name for private in ("token", "secret", "credential", "ip_hash")
            )
        ]
        if columns:
            rows = (await db.execute(select(*columns).where(table.c.user_id == user.id))).mappings()
            data[name] = jsonable_encoder([dict(row) for row in rows])
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Disposition"] = 'attachment; filename="kairos-data.json"'
    return data


@router.delete("/me", response_model=MessageResponse)
async def delete_me(
    request: Request, response: Response, user: SignedIn, db: DB, config: Config
) -> MessageResponse:
    hook = getattr(request.app.state, "before_account_delete", None)
    if hook is not None:
        await hook(db, user)
    await db.execute(delete(MagicLinkToken).where(MagicLinkToken.email == user.email))
    await db.execute(delete(Invite).where(Invite.email == user.email))
    await db.execute(
        delete(AuditLog).where(
            or_(
                AuditLog.actor_user_id == user.id,
                (AuditLog.target_type == "user") & (AuditLog.target_id == user.id),
            )
        )
    )
    await db.execute(delete(User).where(User.id == user.id))
    await db.commit()
    clear_cookies(response, config)
    return MessageResponse(message="Your account and saved data have been deleted.")


@router.get("/admin/users", response_model=list[AdminProfile])
async def admin_users(
    admin: Admin,
    db: DB,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[AdminProfile]:
    users = list(
        await db.scalars(select(User).order_by(User.created_at).offset(offset).limit(limit))
    )
    ids = [user.id for user in users]
    seen_rows = (
        await db.execute(
            select(
                LoginSession.user_id,
                func.max(LoginSession.last_used_at),
            )
            .where(LoginSession.user_id.in_(ids))
            .group_by(LoginSession.user_id)
        )
    ).all()
    seen = {row[0]: row[1] for row in seen_rows}
    calls: dict[str, int] = {}
    tokens: dict[str, int] = {}
    ai_table = Base.metadata.tables.get("ai_calls")
    if ai_table is not None:
        today = now().replace(hour=0, minute=0, second=0, microsecond=0)
        call_rows = (
            await db.execute(
                select(
                    ai_table.c.user_id,
                    func.count(),
                )
                .where(ai_table.c.user_id.in_(ids), ai_table.c.created_at >= today)
                .group_by(ai_table.c.user_id)
            )
        ).all()
        calls = {str(row[0]): int(row[1]) for row in call_rows}
        token_rows = (
            await db.execute(
                select(
                    ai_table.c.user_id,
                    func.coalesce(func.sum(ai_table.c.output_tokens), 0),
                )
                .where(ai_table.c.user_id.in_(ids), ai_table.c.created_at >= today.replace(day=1))
                .group_by(ai_table.c.user_id)
            )
        ).all()
        tokens = {str(row[0]): int(row[1]) for row in token_rows}
    return [
        AdminProfile(
            **Profile.model_validate(user).model_dump(),
            last_seen_at=seen.get(user.id),
            ai_calls_today=calls.get(user.id, 0),
            ai_output_tokens_this_month=tokens.get(user.id, 0),
        )
        for user in users
    ]


@router.patch("/admin/users/{user_id}", response_model=Profile)
async def admin_update(user_id: str, payload: AdminUserUpdate, admin: Admin, db: DB) -> Profile:
    user = await db.get(User, checked_id(user_id))
    if user is None:
        raise HTTPException(404, "Account not found.")
    if user.role == "owner" and admin.role != "owner":
        raise HTTPException(403, "Only an owner can change this account.")
    if payload.role is not None:
        if admin.role != "owner":
            raise HTTPException(403, "Only an owner can change roles.")
        if user.id == admin.id and payload.role != "owner":
            raise HTTPException(422, "Keep your owner access or ask another owner to change it.")
        user.role = payload.role
    if payload.disabled is not None:
        if user.id == admin.id and payload.disabled:
            raise HTTPException(422, "You cannot disable your own account.")
        user.disabled_at = now() if payload.disabled else None
        if payload.disabled:
            await revoke_user_sessions(db, user.id)
    if payload.plan_id is not None:
        plan = await db.get(Plan, payload.plan_id)
        if plan is None:
            raise HTTPException(404, "Plan not found.")
        await set_plan(db, user, plan, admin)
    db.add(
        AuditLog(
            actor_user_id=admin.id,
            action="user.updated",
            target_type="user",
            target_id=user.id,
            details=payload.model_dump(exclude_none=True),
        )
    )
    await db.commit()
    return Profile.model_validate(user)


@router.post("/admin/users/{user_id}/revoke-sessions", response_model=MessageResponse)
async def admin_revoke(user_id: str, admin: Admin, db: DB) -> MessageResponse:
    user = await db.get(User, checked_id(user_id))
    if user is None:
        raise HTTPException(404, "Account not found.")
    if user.role == "owner" and admin.role != "owner":
        raise HTTPException(403, "Only an owner can change this account.")
    await revoke_user_sessions(db, user.id)
    db.add(
        AuditLog(
            actor_user_id=admin.id,
            action="user.sessions_revoked",
            target_type="user",
            target_id=user.id,
        )
    )
    await db.commit()
    return MessageResponse(message="All sessions for this account have ended.")


@router.get("/admin/plans")
async def admin_plans(admin: Admin, db: DB) -> list[dict[str, Any]]:
    plans = await db.scalars(select(Plan).order_by(Plan.key))
    return [
        {
            "id": p.id,
            "key": p.key,
            "name": p.name,
            "quotas": p.quotas,
            "entitlements": p.entitlements,
            "is_default": p.is_default,
        }
        for p in plans
    ]


@router.get("/admin/invites")
async def admin_invites(admin: Admin, db: DB) -> list[dict[str, Any]]:
    invites = await db.scalars(select(Invite).order_by(Invite.expires_at.desc()).limit(100))
    return [
        {
            "id": i.id,
            "email": i.email,
            "role": i.role,
            "plan_id": i.plan_id,
            "expires_at": i.expires_at,
            "used_at": i.used_at,
            "revoked_at": i.revoked_at,
        }
        for i in invites
    ]


@router.post("/admin/invites", status_code=201)
async def create_invite(payload: InviteRequest, admin: Admin, db: DB) -> dict[str, Any]:
    plan = (
        await db.get(Plan, payload.plan_id)
        if payload.plan_id
        else await db.scalar(select(Plan).where(Plan.is_default.is_(True)))
    )
    if plan is None:
        raise HTTPException(404, "Plan not found.")
    invite = Invite(
        email=payload.email,
        invited_by=admin.id,
        role=payload.role,
        plan_id=plan.id,
        token_hash=token_hash(random_token()),
        expires_at=now() + timedelta(days=payload.expires_in_days),
    )
    db.add(invite)
    await db.flush()
    db.add(
        AuditLog(
            actor_user_id=admin.id,
            action="invite.created",
            target_type="invite",
            target_id=invite.id,
        )
    )
    await db.commit()
    return {
        "id": invite.id,
        "email": invite.email,
        "role": invite.role,
        "plan_id": invite.plan_id,
        "expires_at": invite.expires_at,
    }


@router.delete("/admin/invites/{invite_id}", response_model=MessageResponse)
async def revoke_invite(invite_id: str, admin: Admin, db: DB) -> MessageResponse:
    invite = await db.get(Invite, checked_id(invite_id))
    if invite is None:
        raise HTTPException(404, "Invite not found.")
    invite.revoked_at = now()
    db.add(
        AuditLog(
            actor_user_id=admin.id,
            action="invite.revoked",
            target_type="invite",
            target_id=invite.id,
        )
    )
    await db.commit()
    return MessageResponse(message="Invite revoked.")


@router.get("/admin/audit")
async def audit_log(
    admin: Admin,
    db: DB,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    rows = await db.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    )
    return [
        {
            "id": row.id,
            "actor_user_id": row.actor_user_id,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "details": row.details,
            "created_at": row.created_at,
        }
        for row in rows
    ]
