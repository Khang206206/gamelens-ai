from collections.abc import Generator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.config import Settings
from app.core.security import session_token_digest
from app.db.base import Base
from app.db.models import PreferenceType, User, UserPreference
from app.db.seed import load_seed_file, seed_database
from app.main import create_app
from app.services import preferences as preference_services
from app.services.anonymous_identity import AnonymousIdentityService
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ALLOWED_ORIGIN = "http://testserver"


class SqliteAnonymousIdentityService(AnonymousIdentityService):
    def __init__(self, session, settings) -> None:  # type: ignore[no-untyped-def]
        super().__init__(
            session,
            settings,
            clock=lambda: datetime.now(UTC).replace(tzinfo=None),
        )


@contextmanager
def preference_client(settings: Settings) -> Iterator[tuple[TestClient, sessionmaker]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        seed_database(session, load_seed_file())
    app = create_app(
        settings,
        database_engine=engine,
        database_health_check=lambda _engine: True,
    )
    with TestClient(app) as client:
        yield client, factory


@pytest.fixture
def preferences_client(
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, sessionmaker]]:
    monkeypatch.setattr(
        preference_services,
        "AnonymousIdentityService",
        SqliteAnonymousIdentityService,
    )
    with preference_client(test_settings) as value:
        yield value


def _consent(client: TestClient, settings: Settings) -> tuple[str, str]:
    response = client.post(
        "/api/v1/anonymous-sessions",
        headers={"Origin": ALLOWED_ORIGIN},
        json={"consent": True, "consent_version": settings.consent_version},
    )
    assert response.status_code == 201
    raw_token = client.cookies.get(settings.anonymous_session_cookie_name)
    assert raw_token is not None
    return raw_token, response.json()["csrf_token"]


def _protected_headers(settings: Settings, csrf: str) -> dict[str, str]:
    return {"Origin": ALLOWED_ORIGIN, settings.csrf_header_name: csrf}


def _preference_count(factory: sessionmaker) -> int:
    with factory() as session:
        return session.scalar(select(func.count()).select_from(UserPreference)) or 0


def test_preferences_empty_replace_rehydrate_noop_and_clear(
    preferences_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, factory = preferences_client
    _raw_token, csrf = _consent(client, test_settings)
    empty = client.get("/api/v1/me/preferences")
    assert empty.status_code == 200
    assert empty.headers["cache-control"] == "no-store"
    assert empty.json() == {
        "selected_games": [],
        "preferred_genres": [],
        "preferred_tags": [],
        "preferred_platforms": [],
        "stale_references": [],
    }
    games = client.get("/api/v1/games?sort=title&page_size=3").json()["items"]
    payload = {
        "selected_game_ids": [games[1]["id"], games[0]["id"]],
        "preferred_genres": ["strategy", "rpg"],
        "preferred_tags": ["turn-based", "narrative"],
        "preferred_platforms": ["windows", "linux"],
    }

    saved = client.put(
        "/api/v1/me/preferences",
        headers=_protected_headers(test_settings, csrf),
        json=payload,
    )

    assert saved.status_code == 200
    assert saved.headers["cache-control"] == "no-store"
    assert [item["slug"] for item in saved.json()["selected_games"]] == sorted(
        [games[0]["slug"], games[1]["slug"]]
    )
    assert saved.json()["preferred_genres"] == ["rpg", "strategy"]
    assert saved.json()["preferred_tags"] == ["narrative", "turn-based"]
    assert saved.json()["preferred_platforms"] == ["linux", "windows"]
    assert saved.json()["stale_references"] == []
    assert _preference_count(factory) == 8
    with factory() as session:
        before = {
            (str(row.preference_type), row.value): (row.id, row.created_at, row.updated_at)
            for row in session.scalars(select(UserPreference)).all()
        }
        assert {row.weight for row in session.scalars(select(UserPreference)).all()} == {
            Decimal("1.000")
        }

    identical = client.put(
        "/api/v1/me/preferences",
        headers=_protected_headers(test_settings, csrf),
        json=payload,
    )
    rehydrated = client.get("/api/v1/me/preferences")

    assert identical.status_code == 200
    assert identical.json() == saved.json()
    assert rehydrated.json() == saved.json()
    with factory() as session:
        after = {
            (str(row.preference_type), row.value): (row.id, row.created_at, row.updated_at)
            for row in session.scalars(select(UserPreference)).all()
        }
    assert after == before

    cleared = client.delete(
        "/api/v1/me/preferences",
        headers=_protected_headers(test_settings, csrf),
    )
    assert cleared.status_code == 204
    assert cleared.headers["cache-control"] == "no-store"
    assert _preference_count(factory) == 0
    assert client.get("/api/v1/me/preferences").json() == empty.json()


def test_preference_validation_and_protection_leave_prior_state_unchanged(
    preferences_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, factory = preferences_client
    _raw_token, csrf = _consent(client, test_settings)
    valid = {"preferred_genres": ["strategy"]}
    assert (
        client.put(
            "/api/v1/me/preferences",
            headers=_protected_headers(test_settings, csrf),
            json=valid,
        ).status_code
        == 200
    )

    cases = [
        ({"Origin": ALLOWED_ORIGIN}, valid, 403, "csrf_validation_failed"),
        (
            {test_settings.csrf_header_name: csrf},
            valid,
            403,
            "origin_not_allowed",
        ),
        (
            _protected_headers(test_settings, csrf),
            {"preferred_genres": ["missing-taxonomy"]},
            422,
            "unknown_genre",
        ),
        (
            _protected_headers(test_settings, csrf),
            {"preferred_genres": ["strategy", "strategy"]},
            422,
            "validation_error",
        ),
        (
            _protected_headers(test_settings, csrf),
            {"preferred_platforms": ["linux"]},
            422,
            "validation_error",
        ),
        (
            _protected_headers(test_settings, csrf),
            {**valid, "weight": 0.5},
            422,
            "validation_error",
        ),
    ]
    for headers, payload, status, code in cases:
        response = client.put("/api/v1/me/preferences", headers=headers, json=payload)
        assert response.status_code == status
        assert response.json()["error"]["code"] == code
        assert response.headers["cache-control"] == "no-store"
        assert _preference_count(factory) == 1

    assert client.get("/api/v1/me/preferences").json()["preferred_genres"] == ["strategy"]


def test_preferences_report_bounded_stale_references_without_mutation(
    preferences_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, factory = preferences_client
    raw_token, _csrf = _consent(client, test_settings)
    digest = session_token_digest(test_settings.anonymous_session_secret, raw_token)
    with factory.begin() as session:
        user_id = session.scalar(select(User.id).where(User.anonymous_token_digest == digest))
        assert user_id is not None
        session.add_all(
            [
                UserPreference(
                    user_id=user_id,
                    preference_type=PreferenceType.GAME,
                    value="removed-game",
                    weight=Decimal("1.000"),
                ),
                UserPreference(
                    user_id=user_id,
                    preference_type=PreferenceType.TAG,
                    value="removed-tag",
                    weight=Decimal("1.000"),
                ),
            ]
        )

    response = client.get("/api/v1/me/preferences")

    assert response.status_code == 200
    assert response.json()["stale_references"] == ["game:removed-game", "tag:removed-tag"]
    assert _preference_count(factory) == 2


def test_two_anonymous_sessions_cannot_observe_each_others_preferences(
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        preference_services,
        "AnonymousIdentityService",
        SqliteAnonymousIdentityService,
    )
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        seed_database(session, load_seed_file())
    app = create_app(
        test_settings,
        database_engine=engine,
        database_health_check=lambda _engine: True,
    )
    with TestClient(app) as first, TestClient(app) as second:
        _first_token, first_csrf = _consent(first, test_settings)
        _second_token, second_csrf = _consent(second, test_settings)
        assert (
            first.put(
                "/api/v1/me/preferences",
                headers=_protected_headers(test_settings, first_csrf),
                json={"preferred_genres": ["strategy"]},
            ).status_code
            == 200
        )
        assert second.get("/api/v1/me/preferences").json()["preferred_genres"] == []
        assert (
            second.put(
                "/api/v1/me/preferences",
                headers=_protected_headers(test_settings, second_csrf),
                json={"preferred_tags": ["narrative"]},
            ).status_code
            == 200
        )
        assert first.get("/api/v1/me/preferences").json()["preferred_genres"] == ["strategy"]
        assert first.get("/api/v1/me/preferences").json()["preferred_tags"] == []
