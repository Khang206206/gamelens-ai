from datetime import UTC, datetime, timedelta

import pytest
from app.core import security
from app.core.config import Settings
from fastapi import Response


def test_session_token_generation_uses_32_random_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        security.secrets,
        "token_urlsafe",
        lambda byte_count: calls.append(byte_count) or "A" * 43,
    )

    token = security.generate_session_token()

    assert calls == [32]
    assert token == "A" * 43
    assert security.token_is_well_formed(token) is True


@pytest.mark.parametrize(
    "raw_token",
    [
        None,
        "",
        "short",
        "A" * 42,
        "A" * 44,
        "A" * 42 + "!",
        "A" * 42 + "é",
    ],
)
def test_malformed_session_tokens_are_rejected(raw_token: str | None) -> None:
    assert security.token_is_well_formed(raw_token or "") is False


def test_session_digest_and_csrf_are_deterministic_and_domain_separated() -> None:
    secret = "unit-test-session-secret-with-at-least-32-bytes"
    raw_token = "A" * 43

    digest = security.session_token_digest(secret, raw_token)
    csrf = security.csrf_token(secret, raw_token)

    assert len(digest) == 64
    assert len(csrf) == 64
    assert digest != csrf
    assert digest == security.session_token_digest(secret, raw_token)
    assert csrf == security.csrf_token(secret, raw_token)
    assert security.session_token_digest(f"{secret}-rotated", raw_token) != digest
    assert raw_token not in digest
    assert raw_token not in csrf


def test_csrf_comparison_fails_closed() -> None:
    secret = "unit-test-session-secret-with-at-least-32-bytes"
    raw_token = "B" * 43
    expected = security.csrf_token(secret, raw_token)

    assert security.csrf_matches(secret, raw_token, expected) is True
    assert security.csrf_matches(secret, raw_token, None) is False
    assert security.csrf_matches(secret, raw_token, "0" * 63) is False
    assert security.csrf_matches(secret, raw_token, expected.upper()) is False
    assert security.csrf_matches(secret, raw_token, "é" * 64) is False
    assert security.csrf_matches(secret, f"{raw_token[:-1]}C", expected) is False


def test_parse_session_credential_derives_digest_without_database_access(
    test_settings: Settings,
) -> None:
    raw_token = "C" * 43

    credential = security.parse_session_credential(test_settings, raw_token)

    assert credential is not None
    assert credential.raw_token == raw_token
    assert credential.digest == security.session_token_digest(
        test_settings.anonymous_session_secret,
        raw_token,
    )
    assert security.parse_session_credential(test_settings, "malformed") is None
    assert security.parse_session_credential(test_settings, None) is None


def test_origin_allowlist_is_normalized_and_rejects_untrusted_values(
    test_settings: Settings,
) -> None:
    assert security.origin_is_allowed(test_settings, "http://testserver") is True
    assert security.origin_is_allowed(test_settings, "HTTP://TESTSERVER/") is True
    assert security.origin_is_allowed(test_settings, None) is False
    assert security.origin_is_allowed(test_settings, "https://testserver") is False
    assert security.origin_is_allowed(test_settings, "http://testserver.evil.test") is False
    assert security.origin_is_allowed(test_settings, "http://testserver/path") is False


def test_session_cookie_and_clear_cookie_use_matching_security_attributes(
    test_settings: Settings,
) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    expires_at = now + timedelta(seconds=test_settings.anonymous_session_ttl_seconds)
    raw_token = "D" * 43
    response = Response()

    security.set_session_cookie(
        response,
        test_settings,
        raw_token,
        expires_at=expires_at,
        now=now,
    )
    set_cookie = response.headers["set-cookie"]

    assert set_cookie.startswith(f"{test_settings.anonymous_session_cookie_name}={raw_token};")
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert f"Max-Age={test_settings.anonymous_session_ttl_seconds}" in set_cookie
    assert "Secure" not in set_cookie

    cleared = Response()
    security.clear_session_cookie(cleared, test_settings)
    clear_cookie = cleared.headers["set-cookie"]

    assert clear_cookie.startswith(f"{test_settings.anonymous_session_cookie_name}=;")
    assert "HttpOnly" in clear_cookie
    assert "Max-Age=0" in clear_cookie
    assert "Path=/api/v1" in clear_cookie
    assert "SameSite=lax" in clear_cookie


def test_secure_cookie_configuration_emits_secure_attribute() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        cors_origins=["https://app.example.com"],
        anonymous_session_cookie_secure=True,
        anonymous_session_secret="production-only-secret-with-at-least-32-bytes",
    )
    now = datetime(2026, 1, 1, tzinfo=UTC)
    response = Response()

    security.set_session_cookie(
        response,
        settings,
        "E" * 43,
        expires_at=now + timedelta(seconds=settings.anonymous_session_ttl_seconds),
        now=now,
    )

    assert "Secure" in response.headers["set-cookie"]
