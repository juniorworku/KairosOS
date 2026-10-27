import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from app.auth.google import verify_google_code
from app.config import Settings
from app.security import token_hash


def test_google_verifies_signature_and_identity_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    run_google_case(monkeypatch, {})


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "another-client"},
        {"iss": "https://attacker.test"},
        {"nonce": "wrong"},
        {"email_verified": False},
        {"email_verified": "true"},
        {"exp": 1},
    ],
)
def test_google_rejects_untrusted_identity(
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, Any],
) -> None:
    with pytest.raises(HTTPException) as error:
        run_google_case(monkeypatch, overrides)
    assert error.value.status_code == 401
    assert "Google sign-in" in str(error.value.detail)


def run_google_case(monkeypatch: pytest.MonkeyPatch, overrides: dict[str, Any]) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    public_key["kid"] = "test-key"
    claims: dict[str, Any] = {
        "iss": "https://accounts.google.com",
        "aud": "test-client",
        "sub": "test-subject",
        "email": "Owner@Example.Test",
        "email_verified": True,
        "name": "Owner",
        "nonce": "nonce",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    } | overrides
    encoded = jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})

    def transport(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://oauth2.googleapis.com/token":
            assert b"code_verifier=verifier" in request.content
            return httpx.Response(200, json={"id_token": encoded})
        assert str(request.url) == "https://www.googleapis.com/oauth2/v3/certs"
        return httpx.Response(200, json={"keys": [public_key]})

    client_type = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_type(
            transport=httpx.MockTransport(transport),
            **kwargs,
        ),
    )
    result = asyncio.run(
        verify_google_code(
            "code",
            "verifier",
            token_hash("nonce"),
            Settings(google_client_id="test-client", google_client_secret="secret", _env_file=None),
        )
    )
    assert result == {"email": "owner@example.test", "subject": "test-subject", "name": "Owner"}
