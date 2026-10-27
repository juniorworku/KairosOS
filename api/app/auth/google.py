"""Google OpenID Connect with PKCE and signature, issuer, audience and nonce checks."""

import hmac
from typing import TypedDict

import httpx
import jwt
from fastapi import HTTPException

from app.config import Settings
from app.security import token_hash


class GoogleIdentity(TypedDict):
    email: str
    subject: str
    name: str


async def verify_google_code(
    code: str,
    verifier: str,
    nonce_hash: str,
    config: Settings,
) -> GoogleIdentity:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": config.google_client_id,
                    "client_secret": config.google_client_secret,
                    "redirect_uri": config.google_redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": verifier,
                },
            )
            response.raise_for_status()
            identity_token = response.json().get("id_token")
            if not isinstance(identity_token, str):
                raise ValueError("Missing identity token")
            header = jwt.get_unverified_header(identity_token)
            if header.get("alg") != "RS256":
                raise ValueError("Unexpected signature algorithm")
            keys_response = await client.get("https://www.googleapis.com/oauth2/v3/certs")
            keys_response.raise_for_status()
            key_data = next(
                (
                    key
                    for key in keys_response.json()["keys"]
                    if key.get("kid") == header.get("kid")
                ),
                None,
            )
            if key_data is None:
                raise ValueError("Unknown signing key")
            key = jwt.PyJWK.from_dict(key_data, algorithm="RS256")
            claims = jwt.decode(
                identity_token,
                key.key,
                algorithms=["RS256"],
                audience=config.google_client_id,
                issuer=["https://accounts.google.com", "accounts.google.com"],
                options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce", "email"]},
            )
            if claims.get("email_verified") is not True:
                raise ValueError("Email not verified")
            nonce = claims.get("nonce")
            if not isinstance(nonce, str) or not hmac.compare_digest(token_hash(nonce), nonce_hash):
                raise ValueError("Nonce mismatch")
            email, subject = claims["email"], claims["sub"]
            if not isinstance(email, str) or not isinstance(subject, str):
                raise ValueError("Invalid identity")
            name = claims.get("name", "")
            return {
                "email": email.strip().lower(),
                "subject": subject,
                "name": name if isinstance(name, str) else "",
            }
    except (httpx.HTTPError, jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(401, "Google sign-in could not be verified. Try again.") from exc
