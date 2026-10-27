"""Calendar and extension endpoints with explicit user approval boundaries."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import current_user, get_db
from app.integrations.calendar import (
    FREEBUSY_SCOPE,
    WRITE_SCOPE,
    CalendarReauth,
    CalendarUnavailable,
    GoogleCalendar,
    challenge,
    decrypt_token,
    encrypt_token,
    parse_timestamp,
    replace_busy,
)
from app.integrations.config import IntegrationSettings
from app.integrations.jsonutil import Json, list_value, string_value
from app.integrations.models import (
    CalendarBusy,
    CalendarConnection,
    CalendarState,
    ExtensionPair,
    ExtensionToken,
)
from app.models.auth import User
from app.models.planning import PlanningRecord

calendar_router = APIRouter(prefix="/api/v1/calendar", tags=["Calendar"])
ext_router = APIRouter(prefix="/api/v1/ext", tags=["Extension"])
DB = Annotated[AsyncSession, Depends(get_db)]
Owner = Annotated[User, Depends(current_user)]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def unavailable(message: str, code: str = "not_configured") -> HTTPException:
    return HTTPException(503, detail={"code": code, "message": message})


def require_calendar() -> IntegrationSettings:
    config = IntegrationSettings()
    if not config.calendar_configured:
        raise unavailable("Google Calendar is not configured.")
    return config


async def connection_for(db: AsyncSession, user_id: str, lock: bool = False) -> CalendarConnection:
    query = select(CalendarConnection).where(CalendarConnection.user_id == user_id)
    if lock:
        query = query.with_for_update()
    connection = await db.scalar(query)
    if connection is None:
        raise HTTPException(
            409,
            detail={"code": "calendar_disconnected", "message": "Connect Google Calendar first."},
        )
    return connection


@calendar_router.get("/status")
async def calendar_status(db: DB, user: Owner) -> dict[str, Json]:
    connection = await db.scalar(
        select(CalendarConnection).where(CalendarConnection.user_id == user.id)
    )
    configured = IntegrationSettings().calendar_configured
    return {
        "configured": configured,
        "connected": connection is not None,
        "status": connection.status
        if connection
        else ("disconnected" if configured else "not_configured"),
        "can_publish": bool(connection and WRITE_SCOPE in connection.scopes),
        "last_synced_at": connection.last_synced_at.isoformat()
        if connection and connection.last_synced_at
        else None,
        "app_calendar_id": connection.app_calendar_id if connection else None,
    }


@calendar_router.get("/connect")
async def calendar_connect(db: DB, user: Owner, write: bool = False) -> RedirectResponse:
    config = require_calendar()
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    db.add(
        CalendarState(
            user_id=user.id,
            token_hash=digest(state),
            verifier=verifier,
            write_access=write,
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    await db.commit()
    params = {
        "client_id": config.google_client_id,
        "redirect_uri": config.google_calendar_redirect_uri,
        "response_type": "code",
        "scope": " ".join([FREEBUSY_SCOPE] + ([WRITE_SCOPE] if write else [])),
        "state": state,
        "code_challenge": challenge(verifier),
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))


@calendar_router.get("/callback")
async def calendar_callback(
    request: Request, db: DB, user: Owner, state: str = "", code: str = "", error: str = ""
) -> RedirectResponse:
    config = require_calendar()
    record = await db.scalar(
        delete(CalendarState)
        .where(
            CalendarState.token_hash == digest(state),
            CalendarState.user_id == user.id,
            CalendarState.expires_at > datetime.now(UTC),
        )
        .returning(CalendarState)
    )
    if record is None or not code or error:
        await db.commit()
        raise HTTPException(
            400,
            detail={
                "code": "invalid_calendar_consent",
                "message": "Calendar consent expired or was cancelled.",
            },
        )
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            google = GoogleCalendar(config, client)
            token = await google.exchange(code, record.verifier)
            scopes = string_value(token.get("scope", "")).split()
            if FREEBUSY_SCOPE not in scopes or (record.write_access and WRITE_SCOPE not in scopes):
                raise CalendarUnavailable("Required calendar permission was not granted")
            connection = await db.scalar(
                select(CalendarConnection)
                .where(CalendarConnection.user_id == user.id)
                .with_for_update()
            )
            if connection:
                previous = decrypt_token(connection.token_enc, config.token_encryption_key)
                if "refresh_token" not in token and "refresh_token" in previous:
                    token["refresh_token"] = previous["refresh_token"]
                connection.token_enc = encrypt_token(token, config.token_encryption_key)
                connection.scopes = scopes
                connection.status = "active"
            else:
                connection = CalendarConnection(
                    user_id=user.id,
                    token_enc=encrypt_token(token, config.token_encryption_key),
                    scopes=scopes,
                )
                db.add(connection)
            if not isinstance(token.get("refresh_token"), str):
                raise CalendarUnavailable(
                    "Google did not return offline access; reconnect with consent"
                )
            if record.write_access and not connection.app_calendar_id:
                connection.app_calendar_id = await google.create_calendar(
                    string_value(token.get("access_token"))
                )
            await db.commit()
    except (CalendarUnavailable, httpx.HTTPError, ValueError) as exc:
        await db.rollback()
        raise unavailable(
            "Calendar connection could not be completed.", "calendar_unavailable"
        ) from exc
    return RedirectResponse(
        request.app.state.settings.app_base_url + "/settings?calendar=connected", status_code=303
    )


async def sync_user(db: AsyncSession, user_id: str) -> None:
    config = require_calendar()
    # Match planning/publication lock order: owner, calendar connection, then blocks.
    user = await db.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None or user.disabled_at is not None:
        return
    connection = await connection_for(db, user_id, lock=True)
    async with httpx.AsyncClient(timeout=20) as client:
        google = GoogleCalendar(config, client)
        access = await google.access_token(connection, db)
        start = datetime.now(UTC)
        end = start + timedelta(days=21)
        intervals = await google.busy(access, start, end)
        await replace_busy(db, user_id, start, end, intervals)
        if connection.app_calendar_id:
            await reconcile(db, user_id, connection, google, access)
        connection.last_synced_at = datetime.now(UTC)
        await db.commit()


async def reconcile(
    db: AsyncSession,
    user_id: str,
    connection: CalendarConnection,
    google: GoogleCalendar,
    access: str,
) -> None:
    from urllib.parse import quote

    path = f"/calendars/{quote(connection.app_calendar_id or '', safe='')}/events"
    params = {"showDeleted": "true", "maxResults": "2500"}
    if connection.sync_token:
        params["syncToken"] = connection.sync_token
    while True:
        try:
            data = await google.request("GET", path, access, params=params)
        except CalendarUnavailable as exc:
            if str(exc) == "sync_token_expired" and "syncToken" in params:
                connection.sync_token = None
                params.pop("syncToken")
                continue
            raise
        blocks = (
            await db.scalars(
                select(PlanningRecord).where(
                    PlanningRecord.user_id == user_id, PlanningRecord.kind == "block"
                )
            )
        ).all()
        by_event = {
            str(row.payload.get("google_event_id")): row
            for row in blocks
            if row.payload.get("google_event_id")
        }
        for value in list_value(data.get("items", [])):
            if not isinstance(value, dict):
                continue
            event_id = value.get("id")
            if not isinstance(event_id, str) or event_id not in by_event:
                continue
            block = by_event[event_id]
            payload = dict(block.payload)
            if value.get("status") == "cancelled":
                payload["status"] = "cancelled"
            else:
                left, right = value.get("start"), value.get("end")
                if not isinstance(left, dict) or not isinstance(right, dict):
                    continue
                if not isinstance(left.get("dateTime"), str) or not isinstance(
                    right.get("dateTime"), str
                ):
                    continue
                start, end = (
                    parse_timestamp(string_value(left["dateTime"])),
                    parse_timestamp(string_value(right["dateTime"])),
                )
                # Calendar refresh updates the link, not locally recorded completion/skip evidence.
                if payload.get("status") not in {"completed", "skipped"}:
                    payload["status"] = "published"
                if start.isoformat() != payload.get("start_at") or end.isoformat() != payload.get(
                    "end_at"
                ):
                    payload.update(
                        start_at=start.isoformat(),
                        end_at=end.isoformat(),
                        moved_count=int(str(payload.get("moved_count", 0))) + 1,
                    )
            block.payload = payload
        page = data.get("nextPageToken")
        if isinstance(page, str):
            params["pageToken"] = page
            continue
        token = data.get("nextSyncToken")
        if isinstance(token, str):
            connection.sync_token = token
        break


@calendar_router.post("/sync")
async def calendar_sync(db: DB, user: Owner) -> dict[str, str]:
    try:
        await sync_user(db, user.id)
    except CalendarReauth as exc:
        raise HTTPException(
            409, detail={"code": "needs_reauth", "message": "Reconnect Google Calendar."}
        ) from exc
    except (CalendarUnavailable, httpx.HTTPError, ValueError) as exc:
        raise unavailable("Calendar sync failed. Try again.", "calendar_unavailable") from exc
    return {"status": "synced"}


class PublishInput(BaseModel):
    block_ids: list[str] = Field(min_length=1, max_length=100)


@calendar_router.post("/publish")
async def calendar_publish(body: PublishInput, db: DB, user: Owner) -> dict[str, list[str]]:
    from app.routers.planning import lock_owner

    config = require_calendar()
    await lock_owner(db, user)
    connection = await connection_for(db, user.id, lock=True)
    if not connection.app_calendar_id or WRITE_SCOPE not in connection.scopes:
        raise HTTPException(
            409,
            detail={
                "code": "calendar_write_consent",
                "message": "Enable the Kairos calendar first.",
            },
        )
    blocks = (
        await db.scalars(
            select(PlanningRecord)
            .where(
                PlanningRecord.user_id == user.id,
                PlanningRecord.kind == "block",
                PlanningRecord.id.in_(body.block_ids),
            )
            .with_for_update()
        )
    ).all()
    if len(blocks) != len(set(body.block_ids)):
        raise HTTPException(404, detail="Block not found")
    if any(row.payload.get("status") not in {"accepted", "published"} for row in blocks):
        raise HTTPException(
            409,
            detail={"code": "accept_required", "message": "Accept these blocks before publishing."},
        )
    published: list[str] = []
    failed: list[str] = []
    async with httpx.AsyncClient(timeout=20) as client:
        google = GoogleCalendar(config, client)
        try:
            access = await google.access_token(connection, db)
        except (CalendarUnavailable, httpx.HTTPError) as exc:
            raise unavailable("Reconnect Google Calendar.", "calendar_unavailable") from exc
        for block in blocks:
            try:
                event_id = await google.publish(
                    access,
                    connection.app_calendar_id,
                    block.id,
                    str(block.payload.get("title", "Focus")),
                    str(block.payload["start_at"]),
                    str(block.payload["end_at"]),
                )
                block.payload = {
                    **block.payload,
                    "google_event_id": event_id,
                    "status": "published",
                }
                published.append(block.id)
            except (CalendarUnavailable, httpx.HTTPError):
                failed.append(block.id)
        await db.commit()
    return {"published": published, "failed": failed}


@calendar_router.post("/disconnect")
async def calendar_disconnect(db: DB, user: Owner) -> dict[str, str]:
    from app.routers.planning import lock_owner

    await lock_owner(db, user)
    connection = await db.scalar(
        select(CalendarConnection).where(CalendarConnection.user_id == user.id).with_for_update()
    )
    if connection:
        config = IntegrationSettings()
        token = decrypt_token(connection.token_enc, config.token_encryption_key)
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                response = await client.post(
                    "https://oauth2.googleapis.com/revoke",
                    data={"token": string_value(token.get("refresh_token"))},
                )
                if response.status_code not in {200, 400}:
                    raise CalendarUnavailable("Token revocation failed")
            except (httpx.HTTPError, CalendarUnavailable) as exc:
                raise unavailable(
                    "Google could not revoke access. Try again.", "calendar_unavailable"
                ) from exc
        await db.delete(connection)
    # Disconnect intentionally stops management; existing Google events remain untouched.
    blocks = (
        await db.scalars(
            select(PlanningRecord)
            .where(PlanningRecord.user_id == user.id, PlanningRecord.kind == "block")
            .with_for_update()
        )
    ).all()
    for block in blocks:
        payload = dict(block.payload)
        payload.pop("google_event_id", None)
        payload.pop("google_etag", None)
        if payload.get("status") == "published":
            payload["status"] = "accepted"
        block.payload = payload
    await db.execute(delete(CalendarBusy).where(CalendarBusy.user_id == user.id))
    await db.commit()
    return {"status": "disconnected"}


async def redeem_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    redis: Redis = Redis.from_url(request.app.state.settings.redis_url)
    try:
        key = "kairos:ext:redeem:" + digest(ip) + ":" + datetime.now(UTC).strftime("%Y%m%d%H")
        count = await redis.incr(key)
        await redis.expire(key, 3600)
        if count > 20:
            raise HTTPException(429, detail="Try again later")
    finally:
        await redis.aclose()


@ext_router.post("/pair")
async def ext_pair(db: DB, user: Owner) -> dict[str, str]:
    await db.execute(delete(ExtensionPair).where(ExtensionPair.user_id == user.id))
    code = f"{secrets.randbelow(1000000):06d}"
    expires = datetime.now(UTC) + timedelta(minutes=5)
    db.add(ExtensionPair(user_id=user.id, token_hash=digest(code), expires_at=expires))
    await db.commit()
    return {"code": code, "expires_at": expires.isoformat()}


class PairInput(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
    label: str = Field(default="Chrome", min_length=1, max_length=120)


@ext_router.post("/pair/redeem")
async def ext_redeem(body: PairInput, request: Request, db: DB) -> dict[str, str]:
    await redeem_rate_limit(request)
    pair = await db.scalar(
        delete(ExtensionPair)
        .where(
            ExtensionPair.token_hash == digest(body.code),
            ExtensionPair.expires_at > datetime.now(UTC),
        )
        .returning(ExtensionPair)
    )
    if pair is None:
        raise HTTPException(400, detail="Pairing code is invalid or expired")
    user = await db.get(User, pair.user_id)
    if user is None or user.disabled_at is not None:
        raise HTTPException(400, detail="Pairing code is invalid or expired")
    token = secrets.token_urlsafe(32)
    db.add(ExtensionToken(user_id=pair.user_id, token_hash=digest(token), label=body.label))
    await db.commit()
    return {"token": token}


@ext_router.get("/tokens")
async def ext_tokens(db: DB, user: Owner) -> list[dict[str, Json]]:
    rows = (await db.scalars(select(ExtensionToken).where(ExtensionToken.user_id == user.id))).all()
    return [
        {
            "id": row.id,
            "label": row.label,
            "created_at": row.created_at.isoformat(),
            "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
        }
        for row in rows
    ]


@ext_router.delete("/tokens/{token_id}")
async def ext_revoke(token_id: str, db: DB, user: Owner) -> dict[str, str]:
    await db.execute(
        delete(ExtensionToken).where(
            ExtensionToken.id == token_id, ExtensionToken.user_id == user.id
        )
    )
    await db.commit()
    return {"status": "revoked"}


async def extension_user(request: Request, db: DB) -> User:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or len(auth) < 30:
        raise HTTPException(401, detail="Extension token required")
    token = await db.scalar(
        select(ExtensionToken).where(ExtensionToken.token_hash == digest(auth[7:]))
    )
    user = await db.get(User, token.user_id) if token else None
    if token is None or user is None or user.disabled_at is not None:
        raise HTTPException(401, detail="Extension token is invalid")
    token.last_used_at = datetime.now(UTC)
    await db.flush()
    return user


ExtUser = Annotated[User, Depends(extension_user)]


async def active_focus(db: AsyncSession, user_id: str) -> PlanningRecord | None:
    await db.scalar(select(User).where(User.id == user_id).with_for_update())
    rows = (
        await db.scalars(
            select(PlanningRecord)
            .where(PlanningRecord.user_id == user_id, PlanningRecord.kind == "focus")
            .order_by(PlanningRecord.created_at.desc())
            .with_for_update()
        )
    ).all()
    for row in rows:
        if not row.payload.get("ended_at") and parse_timestamp(
            str(row.payload["ends_at"])
        ) > datetime.now(UTC):
            return row
    return None


@ext_router.get("/state")
async def ext_state(db: DB, user: ExtUser) -> dict[str, Json]:
    focus = await active_focus(db, user.id)
    if focus is None:
        await db.commit()
        return {"active_session": None, "blocklist": [], "ends_at": None}
    lists = (
        await db.scalars(
            select(PlanningRecord).where(
                PlanningRecord.user_id == user.id, PlanningRecord.kind == "blocklist"
            )
        )
    ).all()
    selected = next((row for row in lists if row.id == focus.payload.get("blocklist_id")), None)
    if selected is None:
        selected = next((row for row in lists if row.payload.get("is_default")), None)
    domains = cast(
        Json,
        focus.payload.get(
            "blocklist_snapshot", selected.payload.get("domains", []) if selected else []
        ),
    )
    await db.commit()
    return {
        "active_session": {"id": focus.id, "title": str(focus.payload.get("title", "Focus"))},
        "blocklist": domains,
        "ends_at": str(focus.payload["ends_at"]),
        "pause_until": cast(Json, focus.payload.get("pause_until")),
    }


class ExtEvent(BaseModel):
    type: str = Field(pattern=r"^(blocked|pause)$")
    domain: str = Field(default="", max_length=253)
    session_id: str | None = Field(default=None, max_length=36)
    pause_until: datetime | None = None
    event_id: str | None = Field(default=None, max_length=36)


@ext_router.post("/event")
async def ext_event(body: ExtEvent, db: DB, user: ExtUser) -> dict[str, str]:
    focus = await active_focus(db, user.id)
    if focus and (body.session_id is None or body.session_id == focus.id):
        payload = dict(focus.payload)
        processed = list(payload.get("processed_extension_events", []))
        if body.event_id and body.event_id in processed:
            await db.commit()
            return {"status": "recorded"}
        if body.event_id:
            payload["processed_extension_events"] = (processed + [body.event_id])[-100:]
        if body.type == "pause":
            now = datetime.now(UTC)
            until = body.pause_until or now + timedelta(minutes=5)
            if until.tzinfo is None or until > now + timedelta(minutes=5, seconds=5):
                raise HTTPException(422, detail="Pause must end within five minutes")
            payload["pause_until"] = min(until, now + timedelta(minutes=5)).isoformat()
            payload["pause_count"] = int(str(payload.get("pause_count", 0))) + 1
        else:
            payload["distractions_blocked_count"] = (
                int(str(payload.get("distractions_blocked_count", 0))) + 1
            )
        focus.payload = payload
    await db.commit()
    return {"status": "recorded"}


class ExtensionEnd(BaseModel):
    session_id: str | None = Field(default=None, max_length=36)
    ended_at: datetime | None = None


@ext_router.post("/end")
async def ext_end(db: DB, user: ExtUser, body: ExtensionEnd | None = None) -> dict[str, str]:
    from app.routers.planning import end_focus
    from app.schemas.planning import FocusEnd

    focus = await active_focus(db, user.id)
    if focus and (body is None or body.session_id is None or body.session_id == focus.id):
        await end_focus(focus.id, FocusEnd(ended_at=body.ended_at if body else None), db, user)
    else:
        await db.commit()
    return {"status": "ended"}


async def disconnect_calendar_for_user(db: AsyncSession, user_id: str) -> None:
    connection = await db.scalar(
        select(CalendarConnection).where(CalendarConnection.user_id == user_id)
    )
    if not connection:
        return
    config = IntegrationSettings()
    token = decrypt_token(connection.token_enc, config.token_encryption_key)
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            response = await client.post(
                "https://oauth2.googleapis.com/revoke",
                data={"token": string_value(token.get("refresh_token"))},
            )
            if response.status_code not in {200, 400}:
                raise CalendarUnavailable("Token revocation failed")
        except (CalendarUnavailable, httpx.HTTPError) as exc:
            raise unavailable(
                "Google could not revoke access. Try again.", "calendar_unavailable"
            ) from exc
    await db.delete(connection)
    await db.execute(delete(CalendarBusy).where(CalendarBusy.user_id == user_id))


@calendar_router.get("/busy")
async def calendar_busy(db: DB, user: Owner) -> list[dict[str, str]]:
    rows = (
        await db.scalars(
            select(CalendarBusy)
            .where(CalendarBusy.user_id == user.id, CalendarBusy.end_at > datetime.now(UTC))
            .order_by(CalendarBusy.start_at)
        )
    ).all()
    return [
        {"start_at": row.start_at.isoformat(), "end_at": row.end_at.isoformat()} for row in rows
    ]
