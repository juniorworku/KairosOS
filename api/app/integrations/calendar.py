"""Google Calendar boundary. Only availability and the dedicated Kairos calendar are used."""

import asyncio
import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import cast
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.config import IntegrationSettings
from app.integrations.jsonutil import Json, list_value, object_value, string_value
from app.integrations.models import CalendarBusy, CalendarConnection

DETAIL_SCOPE = "https://www.googleapis.com/auth/calendar.events.owned.readonly"
FREEBUSY_SCOPE = "https://www.googleapis.com/auth/calendar.events.freebusy"
WRITE_SCOPE = "https://www.googleapis.com/auth/calendar.app.created"
API_URL = "https://www.googleapis.com/calendar/v3"


class CalendarUnavailable(Exception):
    pass


class CalendarReauth(CalendarUnavailable):
    pass


class CalendarHTTPError(CalendarUnavailable):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__("Google Calendar request failed")


@dataclass(frozen=True)
class PublishedEvent:
    event_id: str
    data: dict[str, Json]


def stable_event_id(block_id: str) -> str:
    return "k" + hashlib.sha256(block_id.encode()).hexdigest()[:40]


def event_bounds(event: dict[str, Json], timezone: str) -> tuple[datetime, datetime, bool]:
    left, right = object_value(event.get("start")), object_value(event.get("end"))
    if isinstance(left.get("dateTime"), str) and isinstance(right.get("dateTime"), str):
        start = parse_timestamp(string_value(left["dateTime"]))
        end = parse_timestamp(string_value(right["dateTime"]))
        all_day = False
    else:
        try:
            zone = ZoneInfo(string_value(left.get("timeZone", timezone)))
        except ZoneInfoNotFoundError as exc:
            raise CalendarUnavailable("Calendar timezone is invalid") from exc
        start = datetime.combine(date.fromisoformat(string_value(left.get("date"))), time.min, zone)
        end = datetime.combine(date.fromisoformat(string_value(right.get("date"))), time.min, zone)
        start, end, all_day = start.astimezone(UTC), end.astimezone(UTC), True
    if end <= start:
        raise CalendarUnavailable("Calendar event duration is invalid")
    return start, end, all_day


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
        *,
        retry_safe: bool = True,
    ) -> dict[str, Json]:
        attempts = 3 if retry_safe else 1
        for attempt in range(attempts):
            try:
                response = await self.client.request(
                    method,
                    API_URL + path,
                    headers={"Authorization": f"Bearer {access}"},
                    json=body,
                    params=params,
                )
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt + 1 == attempts:
                    raise
                await asyncio.sleep(0.25 * 2**attempt)
                continue
            if response.status_code == 401:
                raise CalendarReauth("Reconnect Google Calendar")
            if response.status_code in {429, 500, 502, 503, 504} and attempt + 1 < attempts:
                await asyncio.sleep(0.25 * 2**attempt)
                continue
            if response.status_code >= 400:
                raise CalendarHTTPError(response.status_code)
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

    async def event_instances(
        self, access: str, start: datetime, end: datetime, timezone: str
    ) -> tuple[list[dict[str, Json]], str, str]:
        params = {
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "singleEvents": "true",
            "showDeleted": "false",
            "orderBy": "startTime",
            "maxResults": "2500",
            "timeZone": timezone,
            "fields": (
                "summary,timeZone,nextPageToken,items(id,status,summary,description,"
                "start,end,recurringEventId,originalStartTime)"
            ),
        }
        events: list[dict[str, Json]] = []
        pages: set[str] = set()
        calendar_name, calendar_timezone = "Google Calendar", timezone
        while True:
            data = await self.request("GET", "/calendars/primary/events", access, params=params)
            if isinstance(data.get("summary"), str):
                calendar_name = string_value(data["summary"])
            if isinstance(data.get("timeZone"), str):
                calendar_timezone = string_value(data["timeZone"])
            for event in list_value(data.get("items", [])):
                value = object_value(event)
                if value.get("status") != "cancelled":
                    events.append(value)
            if len(events) > 20000:
                raise CalendarUnavailable("Choose a shorter calendar range.")
            page = data.get("nextPageToken")
            if not isinstance(page, str) or not page:
                break
            if page in pages or len(pages) >= 20:
                raise CalendarUnavailable("Calendar pagination did not complete")
            pages.add(page)
            params["pageToken"] = page
        return events, calendar_timezone, calendar_name

    async def create_calendar(self, access: str, timezone: str = "UTC") -> str:
        # Google assigns calendar IDs: an ambiguous failure cannot safely be retried automatically.
        data = await self.request(
            "POST",
            "/calendars",
            access,
            {"summary": "Kairos", "timeZone": timezone},
            retry_safe=False,
        )
        return string_value(data.get("id"))

    async def publish(
        self, access: str, calendar_id: str, block_id: str, title: str, start: str, end: str
    ) -> PublishedEvent:
        event_id = stable_event_id(block_id)
        path = f"/calendars/{quote(calendar_id, safe='')}/events"
        body: dict[str, Json] = {
            "id": event_id,
            "summary": title,
            "start": {"dateTime": start},
            "end": {"dateTime": end},
            "extendedProperties": {"private": {"kairos_block_id": block_id}},
        }
        try:
            # Stable event IDs make network/429/5xx retry safe.
            data = await self.request("POST", path, access, body)
            return PublishedEvent(event_id, {**body, **data})
        except CalendarHTTPError as exc:
            if exc.status_code != 409:
                raise
        data = await self.request("GET", path + "/" + event_id, access)
        private = object_value(object_value(data.get("extendedProperties", {})).get("private", {}))
        if private.get("kairos_block_id") != block_id or data.get("status") == "cancelled":
            raise CalendarUnavailable("The existing event cannot be claimed. Sync Google Calendar.")
        # Never PUT on conflict: the user may have moved or edited the successful first write.
        return PublishedEvent(event_id, data)


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
            or_(
                CalendarBusy.end_at <= start,
                (CalendarBusy.start_at < end) & (CalendarBusy.end_at > start),
            ),
        )
    )
    for left, right in intervals:
        clipped_start, clipped_end = max(start, left), min(end, right)
        if clipped_start < clipped_end:
            db.add(CalendarBusy(user_id=user_id, start_at=clipped_start, end_at=clipped_end))
