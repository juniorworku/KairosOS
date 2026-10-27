"""Small security helpers shared by web authentication and integrations."""

import base64
import hashlib
import hmac
import secrets
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, Response

from app.config import Settings

SESSION_COOKIE = "kairos_session"
CSRF_COOKIE = "kairos_csrf"
OAUTH_COOKIE = "kairos_oauth"


def random_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def pkce_challenge(verifier: str) -> str:
    return (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )


def ip_hash(request: Request, config: Settings) -> str:
    # Do not trust arbitrary forwarded headers. Configure trusted proxies at the server boundary.
    address = request.client.host if request.client else "unknown"
    return hmac.new(config.secret_key.encode(), address.encode(), hashlib.sha256).hexdigest()


def set_cookie(
    response: Response,
    config: Settings,
    name: str,
    value: str,
    *,
    http_only: bool,
    max_age: int,
) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=http_only,
        secure=config.app_env not in {"dev", "test"},
        samesite="lax",
        path="/",
        domain=config.cookie_domain or None,
    )


def clear_cookies(response: Response, config: Settings) -> None:
    for name in (SESSION_COOKIE, CSRF_COOKIE, OAUTH_COOKIE):
        response.delete_cookie(name, path="/", domain=config.cookie_domain or None)


def require_csrf(request: Request, config: Settings, expected_hash: str | None = None) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != config.app_base_url.rstrip("/"):
        raise HTTPException(403, "This request could not be verified.")
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get("x-csrf-token", "")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(403, "This request could not be verified. Refresh and try again.")
    if expected_hash and not hmac.compare_digest(token_hash(header), expected_hash):
        raise HTTPException(403, "This request could not be verified. Refresh and try again.")


def safe_next(value: str | None) -> str:
    allowed = {"/today", "/goals", "/plan", "/focus", "/review", "/settings"}
    if value is None:
        return "/today"
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or value not in allowed:
        raise HTTPException(400, "Choose a page inside Kairos.")
    return value
