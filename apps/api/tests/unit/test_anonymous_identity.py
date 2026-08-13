from collections.abc import Generator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from app.api.v1.routes import anonymous_sessions as anonymous_session_routes
from app.core.config import Settings
from app.core.security import session_token_digest
from app.db.base import Base
from app.db.models import User
from app.main import create_app
from app.services.anonymous_identity import AnonymousIdentityService
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ALLOWED_ORIGIN = "http://testserver"


class SqliteAnonymousIdentityService(AnonymousIdentityService):
    """Use a naive injected clock because SQLite drops timezone offsets."""

    def __init__(self, session, settings) -> None:  # type: ignore[no-untyped-def]
        super().__init__(
            session,
            settings,
            clock=lambda: datetime.now(UTC).replace(tzinfo=None),
        )


@contextmanager
def anonymous_session_client(
    settings: Settings,
) -> Iterator[tuple[TestClient, sessionmaker]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app(
        settings,
        database_engine=engine,
        database_health_check=lambda _engine: True,
    )
    with TestClient(app) as client:
        yield client, factory


@pytest.fixture
def identity_client(
    test_settings: Settings,
) -> Generator[tuple[TestClient, sessionmaker]]:
    with anonymous_session_client(test_settings) as value:
        yield value


def _consent_payload(version: str = "stage-4-v1") -> dict[str, object]:
    return {"consent": True, "consent_version": version}


def _user_count(factory: sessionmaker) -> int:
    with factory() as session:
        return session.scalar(select(func.count()).select_from(User)) or 0


def test_explicit_consent_creates_one_hashed_identity_and_secure_response_contract(
    identity_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, factory = identity_client

    response = client.post(
        "/api/v1/anonymous-sessions",
        headers={"Origin": ALLOWED_ORIGIN},
        json=_consent_payload(),
    )

    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["status"] == "active"
    assert body["consent_version"] == test_settings.consent_version
    assert body["current_consent_version"] == test_settings.consent_version
    assert len(body["csrf_token"]) == 64
    assert "id" not in body
    assert "anonymous_token_digest" not in body

    raw_token = client.cookies.get(test_settings.anonymous_session_cookie_name)
    assert raw_token is not None
    set_cookie = response.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Secure" not in set_cookie

    with factory() as session:
        users = list(session.scalars(select(User)).all())
    assert len(users) == 1
    assert users[0].anonymous_token_digest == session_token_digest(
        test_settings.anonymous_session_secret,
        raw_token,
    )
    assert raw_token != users[0].anonymous_token_digest


@pytest.mark.parametrize(
    ("headers", "payload", "expected_status"),
    [
        ({}, _consent_payload(), 403),
        ({"Origin": "https://untrusted.example"}, _consent_payload(), 403),
        ({"Origin": ALLOWED_ORIGIN}, {"consent": False, "consent_version": "stage-4-v1"}, 422),
        ({"Origin": ALLOWED_ORIGIN}, {**_consent_payload(), "unexpected": True}, 422),
        ({"Origin": ALLOWED_ORIGIN}, _consent_payload("old-version"), 409),
    ],
)
def test_rejected_consent_requests_create_no_identity_or_cookie(
    identity_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
    headers: dict[str, str],
    payload: dict[str, object],
    expected_status: int,
) -> None:
    client, factory = identity_client

    response = client.post(
        "/api/v1/anonymous-sessions",
        headers=headers,
        json=payload,
    )

    assert response.status_code == expected_status
    assert response.json()["error"]["code"] in {
        "origin_not_allowed",
        "validation_error",
        "consent_version_outdated",
    }
    assert _user_count(factory) == 0
    assert client.cookies.get(test_settings.anonymous_session_cookie_name) is None


def test_wrong_content_type_creates_no_identity(
    identity_client: tuple[TestClient, sessionmaker],
) -> None:
    client, factory = identity_client

    response = client.post(
        "/api/v1/anonymous-sessions",
        headers={"Origin": ALLOWED_ORIGIN, "Content-Type": "text/plain"},
        content='{"consent":true,"consent_version":"stage-4-v1"}',
    )

    assert response.status_code in {403, 422}
    assert _user_count(factory) == 0


def test_bootstrap_reaffirm_and_delete_preserve_one_identity_until_clear(
    identity_client: tuple[TestClient, sessionmaker],
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    client, factory = identity_client
    monkeypatch.setattr(
        anonymous_session_routes,
        "AnonymousIdentityService",
        SqliteAnonymousIdentityService,
    )
    created = client.post(
        "/api/v1/anonymous-sessions",
        headers={"Origin": ALLOWED_ORIGIN},
        json=_consent_payload(),
    )
    assert created.status_code == 201
    created_body = created.json()

    bootstrap = client.get("/api/v1/me")
    assert bootstrap.status_code == 200
    assert bootstrap.headers["cache-control"] == "no-store"
    assert bootstrap.json() == created_body

    missing_csrf = client.post(
        "/api/v1/anonymous-sessions",
        headers={"Origin": ALLOWED_ORIGIN},
        json=_consent_payload(),
    )
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["error"]["code"] == "csrf_validation_failed"
    assert missing_csrf.headers["cache-control"] == "no-store"
    assert _user_count(factory) == 1

    reaffirmed = client.post(
        "/api/v1/anonymous-sessions",
        headers={
            "Origin": ALLOWED_ORIGIN,
            test_settings.csrf_header_name: created_body["csrf_token"],
        },
        json=_consent_payload(),
    )
    assert reaffirmed.status_code == 200
    assert reaffirmed.json() == created_body
    assert "set-cookie" not in reaffirmed.headers
    assert _user_count(factory) == 1

    deleted = client.delete(
        "/api/v1/me",
        headers={
            "Origin": ALLOWED_ORIGIN,
            test_settings.csrf_header_name: created_body["csrf_token"],
        },
    )
    assert deleted.status_code == 204
    assert deleted.headers["cache-control"] == "no-store"
    assert "Max-Age=0" in deleted.headers["set-cookie"]
    assert _user_count(factory) == 0


def test_malformed_cookie_fails_closed_clears_cookie_and_exposes_no_lifecycle(
    identity_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, factory = identity_client

    response = client.get(
        "/api/v1/me",
        headers={"Cookie": f"{test_settings.anonymous_session_cookie_name}=malformed"},
    )

    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "anonymous_session_required",
        "message": "An active anonymous session is required",
    }
    assert "csrf_token" not in response.text
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert response.headers["cache-control"] == "no-store"
    assert _user_count(factory) == 0


def test_protected_write_with_allowed_origin_but_no_cookie_returns_401(
    identity_client: tuple[TestClient, sessionmaker],
) -> None:
    client, factory = identity_client

    response = client.delete(
        "/api/v1/me",
        headers={"Origin": ALLOWED_ORIGIN},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "anonymous_session_required"
    assert response.headers["cache-control"] == "no-store"
    assert "set-cookie" not in response.headers
    assert _user_count(factory) == 0


@pytest.mark.parametrize("state", ["expired", "revoked", "unknown"])
def test_unusable_well_formed_session_fails_closed(
    identity_client: tuple[TestClient, sessionmaker],
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
    state: str,
) -> None:
    client, factory = identity_client
    monkeypatch.setattr(
        anonymous_session_routes,
        "AnonymousIdentityService",
        SqliteAnonymousIdentityService,
    )
    raw_token = state[0].upper() * 43
    now = datetime.now(UTC).replace(tzinfo=None)
    if state != "unknown":
        with factory.begin() as session:
            session.add(
                User(
                    anonymous_token_digest=session_token_digest(
                        test_settings.anonymous_session_secret,
                        raw_token,
                    ),
                    consent_version=test_settings.consent_version,
                    consented_at=now - timedelta(days=2),
                    expires_at=(
                        now - timedelta(seconds=1)
                        if state == "expired"
                        else now + timedelta(days=1)
                    ),
                    revoked_at=now if state == "revoked" else None,
                )
            )
    client.cookies.set(
        test_settings.anonymous_session_cookie_name,
        raw_token,
        domain="testserver.local",
        path=test_settings.anonymous_session_cookie_path,
    )

    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "anonymous_session_required"
    assert "csrf_token" not in response.text
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert response.headers["cache-control"] == "no-store"


def test_unexpired_outdated_consent_has_lifecycle_only_and_reconsents_in_place(
    identity_client: tuple[TestClient, sessionmaker],
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
) -> None:
    client, factory = identity_client
    monkeypatch.setattr(
        anonymous_session_routes,
        "AnonymousIdentityService",
        SqliteAnonymousIdentityService,
    )
    raw_token = "O" * 43
    digest = session_token_digest(test_settings.anonymous_session_secret, raw_token)
    now = datetime.now(UTC).replace(tzinfo=None)
    with factory.begin() as session:
        session.add(
            User(
                anonymous_token_digest=digest,
                consent_version="stage-4-v0",
                consented_at=now - timedelta(days=30),
                expires_at=now + timedelta(days=1),
                revoked_at=None,
            )
        )
    client.cookies.set(
        test_settings.anonymous_session_cookie_name,
        raw_token,
        domain="testserver.local",
        path=test_settings.anonymous_session_cookie_path,
    )

    bootstrap = client.get("/api/v1/me")

    assert bootstrap.status_code == 200
    assert bootstrap.json()["status"] == "consent_outdated"
    assert bootstrap.json()["consent_version"] == "stage-4-v0"
    assert bootstrap.json()["current_consent_version"] == test_settings.consent_version
    assert set(bootstrap.json()) == {
        "status",
        "consent_version",
        "current_consent_version",
        "consented_at",
        "expires_at",
        "csrf_token",
    }

    reconsented = client.post(
        "/api/v1/anonymous-sessions",
        headers={
            "Origin": ALLOWED_ORIGIN,
            test_settings.csrf_header_name: bootstrap.json()["csrf_token"],
        },
        json=_consent_payload(),
    )

    assert reconsented.status_code == 200
    assert reconsented.json()["status"] == "active"
    assert reconsented.headers["set-cookie"].startswith(
        f"{test_settings.anonymous_session_cookie_name}={raw_token};"
    )
    assert (
        f"Max-Age={test_settings.anonymous_session_ttl_seconds}"
        in reconsented.headers["set-cookie"]
    )
    assert (
        client.cookies.get(
            test_settings.anonymous_session_cookie_name,
            domain="testserver.local",
            path=test_settings.anonymous_session_cookie_path,
        )
        == raw_token
    )
    with factory() as session:
        users = list(session.scalars(select(User)).all())
    assert len(users) == 1
    assert users[0].anonymous_token_digest == digest
    assert users[0].consent_version == test_settings.consent_version


def test_public_and_stateless_paths_do_not_create_identity_or_cookie(
    identity_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, factory = identity_client

    responses = [
        client.get("/health"),
        client.get("/api/v1/games"),
        client.get("/api/v1/metadata/genres"),
        client.get("/api/v1/models/status"),
        client.post(
            "/api/v1/recommendations",
            headers={"Cookie": f"{test_settings.anonymous_session_cookie_name}={'F' * 43}"},
            json={"preferred_genres": ["strategy"]},
        ),
    ]

    assert all(response.status_code in {200, 503} for response in responses)
    assert _user_count(factory) == 0
    assert all("set-cookie" not in response.headers for response in responses)


def test_credentialed_cors_preflight_allows_protected_methods_and_csrf_header(
    identity_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, _factory = identity_client

    for method in ("POST", "PUT", "DELETE"):
        response = client.options(
            "/api/v1/me",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": (
                    f"content-type,{test_settings.csrf_header_name.casefold()}"
                ),
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
        assert response.headers["access-control-allow-credentials"] == "true"
        assert method in response.headers["access-control-allow-methods"]

    rejected = client.options(
        "/api/v1/me",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "DELETE",
        },
    )
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers
