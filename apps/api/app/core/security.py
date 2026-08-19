from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import format_datetime

from fastapi import Response
from pydantic import SecretStr

from app.core.config import Settings, _normalized_http_origin

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
CSRF_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SESSION_DOMAIN = b"gamelens:session:v1\x00"
CSRF_DOMAIN = b"gamelens:csrf:v1\x00"


def utc_now() -> datetime:
    return datetime.now(UTC)


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def token_is_well_formed(raw_token: str) -> bool:
    if TOKEN_PATTERN.fullmatch(raw_token) is None:
        return False
    try:
        decoded = base64.urlsafe_b64decode(f"{raw_token}=")
    except ValueError:
        return False
    return len(decoded) == 32


def _secret_value(secret: str | SecretStr) -> str:
    return secret.get_secret_value() if isinstance(secret, SecretStr) else secret


def _hmac_hex(secret: str | SecretStr, domain: bytes, raw_token: str) -> str:
    return hmac.new(
        _secret_value(secret).encode("utf-8"),
        domain + raw_token.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()


def session_token_digest(secret: str | SecretStr, raw_token: str) -> str:
    return _hmac_hex(secret, SESSION_DOMAIN, raw_token)


def csrf_token(secret: str | SecretStr, raw_token: str) -> str:
    return _hmac_hex(secret, CSRF_DOMAIN, raw_token)


def csrf_matches(secret: str | SecretStr, raw_token: str, candidate: str | None) -> bool:
    if candidate is None or CSRF_PATTERN.fullmatch(candidate) is None:
        return False
    return hmac.compare_digest(csrf_token(secret, raw_token), candidate)


def origin_is_allowed(settings: Settings, origin: str | None) -> bool:
    if origin is None:
        return False
    try:
        normalized = _normalized_http_origin(origin)
    except ValueError:
        return False
    return any(hmac.compare_digest(normalized, allowed) for allowed in settings.cors_origins)


@dataclass(frozen=True)
class SessionCredential:
    raw_token: str
    digest: str


def parse_session_credential(settings: Settings, raw_token: str | None) -> SessionCredential | None:
    if raw_token is None or not token_is_well_formed(raw_token):
        return None
    return SessionCredential(
        raw_token=raw_token,
        digest=session_token_digest(settings.anonymous_session_secret, raw_token),
    )


def set_session_cookie(
    response: Response,
    settings: Settings,
    raw_token: str,
    *,
    expires_at: datetime,
    now: datetime,
) -> None:
    def normalized(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    expires_at = normalized(expires_at)
    now = normalized(now)
    max_age = max(0, int((expires_at - now).total_seconds()))
    response.set_cookie(
        key=settings.anonymous_session_cookie_name,
        value=raw_token,
        max_age=max_age,
        expires=expires_at,
        path=settings.anonymous_session_cookie_path,
        secure=settings.anonymous_session_cookie_secure,
        httponly=True,
        samesite=settings.anonymous_session_cookie_samesite,
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    attributes = [
        f"{settings.anonymous_session_cookie_name}=",
        "Max-Age=0",
        f"Expires={format_datetime(datetime(1970, 1, 1, tzinfo=UTC), usegmt=True)}",
        f"Path={settings.anonymous_session_cookie_path}",
        "HttpOnly",
        f"SameSite={settings.anonymous_session_cookie_samesite}",
    ]
    if settings.anonymous_session_cookie_secure:
        attributes.append("Secure")
    response.headers.append("set-cookie", "; ".join(attributes))
