"""Google Calendar boundary. Only availability and the dedicated Kairos calendar are used."""

import asyncio
import base64
import hashlib
import json
from datetime import UTC, datetime
from typing import cast
from urllib.parse import quote

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.config import IntegrationSettings
from app.integrations.jsonutil import Json, list_value, object_value, string_value
from app.integrations.models import CalendarBusy, CalendarConnection

FREEBUSY_SCOPE = "https://www.googleapis.com/auth/calendar.events.freebusy"
WRITE_SCOPE = "https://www.googleapis.com/auth/calendar.app.created"
API_URL = "https://www.googleapis.com/calendar/v3"


class CalendarUnavailable(Exception):
    pass


class CalendarReauth(CalendarUnavailable):
    pass


def encrypt_token(token: dict[str, Json], key: str) -> bytes:
    return Fernet(key.encode()).encrypt(json.dumps(token).encode())


def decrypt_token(value: bytes, key: str) -> dict[str, Json]:
    try:
        return object_value(cast(Json, json.loads(Fernet(key.encode()).decrypt(value))))
    except (InvalidToken, ValueError) as exc:
        raise CalendarUnavailable("Calendar credentials could not be read") from exc


def challenge(verifier: str) -> str:
    return (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )


def parse_timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timezone is required")
    return result.astimezone(UTC)


class GoogleCalendar:
    def __init__(self, config: IntegrationSettings, client: httpx.AsyncClient) -> None:
        self.config = config
        self.client = client

    async def exchange(self, code: str, verifier: str) -> dict[str, Json]:
        response = await self.client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "code_verifier": verifier,
                "client_id": self.config.google_client_id,
                "client_secret": self.config.google_client_secret,
                "redirect_uri": self.config.google_calendar_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if response.status_code != 200:
            raise CalendarUnavailable("Google authorization failed")
        token = object_value(cast(Json, response.json()))
        string_value(token.get("access_token"))
        return token

    async def access_token(self, connection: CalendarConnection, db: AsyncSession) -> str:
        token = decrypt_token(connection.token_enc, self.config.token_encryption_key)
        refresh = token.get("refresh_token")
        if not isinstance(refresh, str):
            raise CalendarReauth("Reconnect Google Calendar")
        response = await self.client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self.config.google_client_id,
                "client_secret": self.config.google_client_secret,
                "refresh_token": refresh,
                "grant_type": "refresh_token",
            },
        )
        body = object_value(cast(Json, response.json()))
        if response.status_code != 200:
            if body.get("error") == "invalid_grant":
                connection.status = "needs_reauth"
                await db.commit()
                raise CalendarReauth("Reconnect Google Calendar")
            raise CalendarUnavailable("Google Calendar is unavailable")
        token.update(body)
        connection.token_enc = encrypt_token(token, self.config.token_encryption_key)
        return string_value(body.get("access_token"))

    async def request(
        self,
        method: str,
        path: str,
        access: str,
        body: dict[str, Json] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Json]:
        for attempt in range(3):
            response = await self.client.request(
                method,
                API_URL + path,
                headers={"Authorization": f"Bearer {access}"},
                json=body,
                params=params,
            )
            if response.status_code == 410:
                raise CalendarUnavailable("sync_token_expired")
            if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                await asyncio.sleep(0.25 * 2**attempt)
                continue
            if response.status_code >= 400:
                raise CalendarUnavailable("Google Calendar request failed")
            if response.status_code == 204:
                return {}
            return object_value(cast(Json, response.json()))
        raise CalendarUnavailable("Google Calendar is unavailable")

    async def busy(
        self, access: str, start: datetime, end: datetime
    ) -> list[tuple[datetime, datetime]]:
        data = await self.request(
            "POST",
            "/freeBusy",
            access,
            {
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "items": [{"id": "primary"}],
            },
        )
        primary = object_value(object_value(data.get("calendars")).get("primary"))
        if primary.get("errors"):
            raise CalendarUnavailable("Calendar availability could not be read")
        return [
            (
                parse_timestamp(string_value(object_value(item).get("start"))),
                parse_timestamp(string_value(object_value(item).get("end"))),
            )
            for item in list_value(primary.get("busy", []))
        ]

    async def create_calendar(self, access: str) -> str:
        data = await self.request("POST", "/calendars", access, {"summary": "Kairos"})
        return string_value(data.get("id"))

    async def publish(
        self, access: str, calendar_id: str, block_id: str, title: str, start: str, end: str
    ) -> str:
        # A stable Google-compatible event ID makes retries idempotent, including after a crash.
        event_id = "k" + hashlib.sha256(block_id.encode()).hexdigest()[:40]
        path = f"/calendars/{quote(calendar_id, safe='')}/events"
        body: dict[str, Json] = {
            "id": event_id,
            "summary": title,
            "start": {"dateTime": start},
            "end": {"dateTime": end},
            "extendedProperties": {"private": {"kairos_block_id": block_id}},
        }
        response = await self.client.post(
            API_URL + path, headers={"Authorization": f"Bearer {access}"}, json=body
        )
        if response.status_code == 409:
            body.pop("id")
            await self.request("PUT", path + "/" + event_id, access, body)
        elif response.status_code >= 400:
            raise CalendarUnavailable("Calendar block could not be published")
        return event_id


async def read_calendar_busy(
    db: AsyncSession, user_id: str, start: datetime, end: datetime
) -> list[tuple[datetime, datetime]]:
    rows = (
        await db.scalars(
            select(CalendarBusy).where(
                CalendarBusy.user_id == user_id,
                CalendarBusy.start_at < end,
                CalendarBusy.end_at > start,
            )
        )
    ).all()
    return [(row.start_at, row.end_at) for row in rows]


async def replace_busy(
    db: AsyncSession,
    user_id: str,
    start: datetime,
    end: datetime,
    intervals: list[tuple[datetime, datetime]],
) -> None:
    await db.execute(
        delete(CalendarBusy).where(
            CalendarBusy.user_id == user_id,
            CalendarBusy.start_at < end,
            CalendarBusy.end_at > start,
        )
    )
    for left, right in intervals:
        if left < right:
            db.add(CalendarBusy(user_id=user_id, start_at=left, end_at=right))
