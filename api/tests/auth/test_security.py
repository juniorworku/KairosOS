import asyncio

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.auth.limits import MemoryLimiter
from app.auth.schemas import EmailRequest, ProfileUpdate
from app.config import Settings
from app.security import pkce_challenge, random_token, safe_next, token_hash


def test_tokens_are_random_and_only_hashes_are_stored() -> None:
    token = random_token()
    assert len(token) >= 40
    assert token != random_token()
    assert len(token_hash(token)) == 64
    assert token not in token_hash(token)


def test_pkce_rfc7636_vector() -> None:
    assert pkce_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == (
        "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )


@pytest.mark.parametrize(
    "target", ["https://evil.test", "//evil.test", "/\\evil", "/today?next=evil"]
)
def test_open_redirects_are_rejected(target: str) -> None:
    with pytest.raises(HTTPException):
        safe_next(target)


def test_safe_next_defaults_and_allowed_routes() -> None:
    assert safe_next(None) == "/today"
    assert safe_next("/goals") == "/goals"


@pytest.mark.parametrize(
    "value", ["bad", "x@@example.test", "a b@example.test", "x\n@example.test"]
)
def test_bad_emails_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        EmailRequest(email=value)


def test_email_normalization() -> None:
    assert EmailRequest(email=" Owner@Example.Test ").email == "owner@example.test"


@pytest.mark.parametrize(
    "values",
    [
        {"timezone": "not/a_timezone"},
        {"work_days": [0, 0]},
        {"work_days": [7]},
        {"work_start": "18:00", "work_end": "09:00"},
        {"daily_max_focus_minutes": 10000},
    ],
)
def test_invalid_profile_values_rejected(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ProfileUpdate.model_validate(values)


def test_hosted_settings_do_not_allow_insecure_defaults() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production", _env_file=None)


def test_rate_limit_has_hard_boundary() -> None:
    async def run() -> None:
        limiter = MemoryLimiter()
        assert await limiter.allow("identity", 2, 60)
        assert await limiter.allow("identity", 2, 60)
        assert not await limiter.allow("identity", 2, 60)
        assert await limiter.allow("another", 2, 60)

    asyncio.run(run())
