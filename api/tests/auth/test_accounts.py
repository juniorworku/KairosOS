import asyncio
import re
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.service import consume_magic, initialize_auth, verified_user
from app.models.auth import AuthIdentity, LoginSession, MagicLinkToken, User, now
from app.security import token_hash


def csrf(client: TestClient) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def request_token(client: TestClient, email: str = "owner@example.test") -> str:
    sender = client.app.state.email_sender  # type: ignore[union-attr]
    response = client.post(
        "/api/v1/auth/magic/request", json={"email": email}, headers=csrf(client)
    )
    assert response.status_code == 202
    link = re.search(r"http://testserver/auth/confirm\?token=\S+", sender.messages[-1].text)
    assert link is not None
    return parse_qs(urlsplit(link.group()).query)["token"][0]


def sign_in(client: TestClient, email: str = "owner@example.test") -> dict[str, Any]:
    token = request_token(client, email)
    response = client.post("/api/v1/auth/magic/verify", json={"token": token}, headers=csrf(client))
    assert response.status_code == 200, response.text
    return response.json()


def test_magic_request_is_generic_and_get_does_not_consume(auth_client: TestClient) -> None:
    client = auth_client
    token = request_token(client)
    assert client.get(f"/api/v1/auth/magic?token={token}").status_code == 200
    response = client.post("/api/v1/auth/magic/verify", json={"token": token}, headers=csrf(client))
    assert response.status_code == 200
    assert client.get("/api/v1/me").json()["role"] == "owner"
    replay = client.post("/api/v1/auth/magic/verify", json={"token": token}, headers=csrf(client))
    assert replay.status_code == 401
    generic = client.post(
        "/api/v1/auth/magic/request", json={"email": "unknown@example.test"}, headers=csrf(client)
    )
    assert generic.status_code == 202
    assert generic.json() == {"message": "If this email can sign in, we sent a link."}


def test_csrf_and_origin_are_enforced(auth_client: TestClient) -> None:
    client = auth_client
    sign_in(client)
    assert client.patch("/api/v1/me", json={"name": "Changed"}).status_code == 403
    headers = csrf(client) | {"Origin": "https://attacker.test"}
    assert client.patch("/api/v1/me", json={"name": "Changed"}, headers=headers).status_code == 403
    assert (
        client.patch("/api/v1/me", json={"name": "Changed"}, headers=csrf(client)).status_code
        == 200
    )


def test_profile_validation_and_export_omit_tokens(auth_client: TestClient) -> None:
    client = auth_client
    sign_in(client)
    assert (
        client.patch("/api/v1/me", json={"work_start": "20:00"}, headers=csrf(client)).status_code
        == 422
    )
    profile = client.patch(
        "/api/v1/me",
        json={"timezone": "Africa/Addis_Ababa", "ai_enabled": False},
        headers=csrf(client),
    )
    assert profile.json()["timezone"] == "Africa/Addis_Ababa"
    assert profile.json()["ai_enabled"] is False
    exported = client.get("/api/v1/me/export")
    assert exported.status_code == 200
    assert "token_hash" not in exported.text
    assert "csrf_hash" not in exported.text


def test_session_revocation_ends_access(auth_client: TestClient) -> None:
    client = auth_client
    sign_in(client)
    sessions = client.get("/api/v1/me/sessions").json()
    assert len(sessions) == 1
    assert sessions[0]["current"] is True
    assert (
        client.delete(f"/api/v1/me/sessions/{sessions[0]['id']}", headers=csrf(client)).status_code
        == 200
    )
    assert client.get("/api/v1/me").status_code == 401


def test_magic_token_expiry_and_hash_only_storage(auth_client: TestClient) -> None:
    client = auth_client
    token = request_token(client)

    async def expire() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            record = await db.scalar(select(MagicLinkToken))
            assert record is not None
            assert record.token_hash == token_hash(token)
            assert token not in record.__dict__.values()
            record.expires_at = now() - timedelta(seconds=1)
            await db.commit()

    assert client.portal is not None
    client.portal.call(expire)
    assert (
        client.post(
            "/api/v1/auth/magic/verify", json={"token": token}, headers=csrf(client)
        ).status_code
        == 401
    )


def test_concurrent_magic_verification_has_one_winner(auth_client: TestClient) -> None:
    client = auth_client
    token = request_token(client)

    async def run() -> list[bool]:
        async def verify() -> bool:
            async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
                try:
                    await consume_magic(db, token, client.app.state.settings)  # type: ignore[union-attr]
                    await db.commit()
                    return True
                except HTTPException:
                    await db.rollback()
                    return False

        return list(await asyncio.gather(verify(), verify()))

    assert client.portal is not None
    assert sorted(client.portal.call(run)) == [False, True]


def test_verified_google_and_email_link_to_same_account(auth_client: TestClient) -> None:
    client = auth_client

    async def run() -> None:
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            config = client.app.state.settings  # type: ignore[union-attr]
            google_user = await verified_user(
                db, "owner@example.test", "google", "google-subject", config
            )
            assert google_user is not None
            email_user = await verified_user(
                db, "owner@example.test", "email", "owner@example.test", config
            )
            assert email_user is not None
            assert google_user.id == email_user.id
            await db.commit()
            identities = list(await db.scalars(select(AuthIdentity)))
            assert {i.provider for i in identities} == {"google", "email"}

    assert client.portal is not None
    client.portal.call(run)


def test_disable_revokes_sessions_and_non_admin_is_denied(auth_client: TestClient) -> None:
    client = auth_client
    owner = sign_in(client)
    owner_cookies = dict(client.cookies)
    app = client.app
    app.state.settings.signup_mode = "open"  # type: ignore[union-attr]
    client.cookies.clear()
    user = sign_in(client, "member@example.test")
    user_cookies = dict(client.cookies)
    assert client.get("/api/v1/admin/users").status_code == 403
    client.cookies.clear()
    client.cookies.update(owner_cookies)
    disabled = client.patch(
        f"/api/v1/admin/users/{user['id']}", json={"disabled": True}, headers=csrf(client)
    )
    assert disabled.status_code == 200
    assert client.get("/api/v1/me").json()["id"] == owner["id"]
    client.cookies.clear()
    client.cookies.update(user_cookies)
    assert client.get("/api/v1/me").status_code == 401


def test_delete_owner_does_not_reseed_account(auth_client: TestClient) -> None:
    client = auth_client
    sign_in(client)
    assert client.delete("/api/v1/me", headers=csrf(client)).status_code == 200

    async def run() -> None:
        await initialize_auth(client.app.state.session_factory, client.app.state.settings)  # type: ignore[union-attr]
        async with client.app.state.session_factory() as db:  # type: ignore[union-attr]
            assert await db.scalar(select(User)) is None
            assert await db.scalar(select(LoginSession)) is None
            assert await db.scalar(select(MagicLinkToken)) is None

    assert client.portal is not None
    client.portal.call(run)


def test_invite_mode_accepts_only_invited_verified_email(auth_client: TestClient) -> None:
    client = auth_client
    sign_in(client)
    invite = client.post(
        "/api/v1/admin/invites", json={"email": "invited@example.test"}, headers=csrf(client)
    )
    assert invite.status_code == 201
    client.app.state.settings.signup_mode = "invite"  # type: ignore[union-attr]
    client.cookies.clear()
    user = sign_in(client, "invited@example.test")
    assert user["role"] == "user"
    sender = client.app.state.email_sender  # type: ignore[union-attr]
    count = len(sender.messages)
    response = client.post(
        "/api/v1/auth/magic/request", json={"email": "uninvited@example.test"}, headers=csrf(client)
    )
    assert response.status_code == 202
    assert len(sender.messages) == count


def test_rate_limit_does_not_reveal_eligible_email(auth_client: TestClient) -> None:
    client = auth_client
    request_token(client)
    sender = client.app.state.email_sender  # type: ignore[union-attr]
    before = len(sender.messages)
    response = client.post(
        "/api/v1/auth/magic/request", json={"email": "owner@example.test"}, headers=csrf(client)
    )
    assert response.status_code == 202
    assert len(sender.messages) == before


def test_google_login_requests_only_identity_scopes_and_pkce(auth_client: TestClient) -> None:
    client = auth_client
    settings = client.app.state.settings  # type: ignore[union-attr]
    settings.google_client_id = "client"
    settings.google_client_secret = "secret"
    response = client.get("/api/v1/auth/google/login", follow_redirects=False)
    assert response.status_code == 302
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["scope"] == ["openid email profile"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["state"] and query["nonce"] and query["code_challenge"]
    assert client.get("/api/v1/auth/google/callback?code=wrong&state=wrong").status_code == 401


def test_admin_plan_change_is_audited(auth_client: TestClient) -> None:
    client = auth_client
    owner = sign_in(client)
    plans = client.get("/api/v1/admin/plans").json()
    plus = next(plan for plan in plans if plan["key"] == "plus")
    changed = client.patch(
        f"/api/v1/admin/users/{owner['id']}", json={"plan_id": plus["id"]}, headers=csrf(client)
    )
    assert changed.status_code == 200
    assert changed.json()["plan_id"] == plus["id"]
    audit = client.get("/api/v1/admin/audit").json()
    assert any(entry["action"] == "user.plan_changed" for entry in audit)
