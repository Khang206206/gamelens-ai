from collections.abc import Generator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from app.core.config import Settings
from app.core.security import session_token_digest
from app.db.base import Base
from app.db.models import Interaction, InteractionType, User
from app.db.seed import load_seed_file, seed_database
from app.main import create_app
from app.services import feedback as feedback_services
from app.services.anonymous_identity import AnonymousIdentityService
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
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


def _repair_sqlite_partial_indexes(engine) -> None:  # type: ignore[no-untyped-def]
    with engine.begin() as connection:
        connection.execute(text("DROP INDEX uq_interactions_active_reaction"))
        connection.execute(text("DROP INDEX uq_interactions_active_state_type"))
        connection.execute(
            text(
                """
                CREATE UNIQUE INDEX uq_interactions_active_reaction
                ON interactions (user_id, game_id)
                WHERE superseded_at IS NULL
                  AND interaction_type IN ('liked', 'disliked')
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE UNIQUE INDEX uq_interactions_active_state_type
                ON interactions (user_id, game_id, interaction_type)
                WHERE superseded_at IS NULL
                  AND interaction_type IN ('played', 'wishlisted', 'rated')
                """
            )
        )


@contextmanager
def feedback_client(settings: Settings) -> Iterator[tuple[TestClient, sessionmaker]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    _repair_sqlite_partial_indexes(engine)
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
def stage_4_feedback_client(
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, sessionmaker]]:
    monkeypatch.setattr(
        feedback_services,
        "AnonymousIdentityService",
        SqliteAnonymousIdentityService,
    )
    with feedback_client(test_settings) as value:
        yield value


def _consent(client: TestClient, settings: Settings) -> tuple[str, str]:
    response = client.post(
        "/api/v1/anonymous-sessions",
        headers={"Origin": ALLOWED_ORIGIN},
        json={"consent": True, "consent_version": settings.consent_version},
    )
    assert response.status_code == 201
    token = client.cookies.get(settings.anonymous_session_cookie_name)
    assert token is not None
    return token, response.json()["csrf_token"]


def _headers(settings: Settings, csrf: str) -> dict[str, str]:
    return {"Origin": ALLOWED_ORIGIN, settings.csrf_header_name: csrf}


def _game_ids(client: TestClient, count: int = 3) -> list[int]:
    return [
        item["id"]
        for item in client.get(
            "/api/v1/games",
            params={"sort": "title", "page_size": count},
        ).json()["items"]
    ]


def test_feedback_full_resource_transition_noop_history_and_clear(
    stage_4_feedback_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, factory = stage_4_feedback_client
    _token, csrf = _consent(client, test_settings)
    game_id = _game_ids(client, 1)[0]
    empty_page = client.get("/api/v1/me/feedback")
    assert empty_page.status_code == 200
    assert empty_page.headers["cache-control"] == "no-store"
    assert empty_page.json() == {"items": [], "page": 1, "page_size": 50, "total": 0}

    initial_payload = {
        "reaction": "liked",
        "played": True,
        "wishlisted": False,
        "rating": 8.5,
    }
    initial = client.put(
        f"/api/v1/me/games/{game_id}/feedback",
        headers=_headers(test_settings, csrf),
        json=initial_payload,
    )

    assert initial.status_code == 200
    assert initial.headers["cache-control"] == "no-store"
    assert initial.json()["game_id"] == game_id
    assert initial.json()["reaction"] == "liked"
    assert initial.json()["played"] is True
    assert initial.json()["wishlisted"] is False
    assert initial.json()["rating"] == 8.5
    with factory() as session:
        before = [
            (row.id, row.interaction_type, row.value, row.occurred_at, row.superseded_at)
            for row in session.scalars(select(Interaction).order_by(Interaction.id)).all()
        ]
    assert len(before) == 3

    identical = client.put(
        f"/api/v1/me/games/{game_id}/feedback",
        headers=_headers(test_settings, csrf),
        json=initial_payload,
    )
    assert identical.status_code == 200
    initial_body = initial.json()
    identical_body = identical.json()
    initial_occurred_at = datetime.fromisoformat(
        initial_body.pop("latest_occurred_at").replace("Z", "+00:00")
    )
    identical_occurred_at = datetime.fromisoformat(
        identical_body.pop("latest_occurred_at").replace("Z", "+00:00")
    )
    if initial_occurred_at.tzinfo is None:
        initial_occurred_at = initial_occurred_at.replace(tzinfo=UTC)
    if identical_occurred_at.tzinfo is None:
        identical_occurred_at = identical_occurred_at.replace(tzinfo=UTC)
    assert identical_body == initial_body
    assert identical_occurred_at == initial_occurred_at
    with factory() as session:
        after_noop = [
            (row.id, row.interaction_type, row.value, row.occurred_at, row.superseded_at)
            for row in session.scalars(select(Interaction).order_by(Interaction.id)).all()
        ]
    assert after_noop == before

    changed = client.put(
        f"/api/v1/me/games/{game_id}/feedback",
        headers=_headers(test_settings, csrf),
        json={
            "reaction": "disliked",
            "played": False,
            "wishlisted": True,
            "rating": 7.0,
        },
    )
    assert changed.status_code == 200
    assert changed.json()["reaction"] == "disliked"
    assert changed.json()["played"] is False
    assert changed.json()["wishlisted"] is True
    assert changed.json()["rating"] == 7.0
    with factory() as session:
        rows = list(session.scalars(select(Interaction).order_by(Interaction.id)).all())
    assert len(rows) == 6
    active = [row for row in rows if row.superseded_at is None]
    assert {row.interaction_type for row in active} == {
        InteractionType.DISLIKED,
        InteractionType.WISHLISTED,
        InteractionType.RATED,
    }
    assert all(row.interaction_type is not InteractionType.VIEWED for row in rows)

    cleared = client.delete(
        f"/api/v1/me/games/{game_id}/feedback",
        headers=_headers(test_settings, csrf),
    )
    assert cleared.status_code == 204
    assert cleared.headers["cache-control"] == "no-store"
    assert client.get("/api/v1/me/feedback").json()["items"] == []
    with factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Interaction)
                .where(Interaction.superseded_at.is_(None))
            )
            == 0
        )
        assert session.scalar(select(func.count()).select_from(Interaction)) == 6

    second_clear = client.delete(
        f"/api/v1/me/games/{game_id}/feedback",
        headers=_headers(test_settings, csrf),
    )
    assert second_clear.status_code == 204
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Interaction)) == 6


def test_feedback_validation_protection_and_unknown_game_are_atomic(
    stage_4_feedback_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, factory = stage_4_feedback_client
    _token, csrf = _consent(client, test_settings)
    game_id = _game_ids(client, 1)[0]
    valid = {
        "reaction": "liked",
        "played": False,
        "wishlisted": False,
        "rating": None,
    }
    cases = [
        ({"Origin": ALLOWED_ORIGIN}, valid, game_id, 403, "csrf_validation_failed"),
        ({test_settings.csrf_header_name: csrf}, valid, game_id, 403, "origin_not_allowed"),
        (_headers(test_settings, csrf), {"reaction": "liked"}, game_id, 422, "validation_error"),
        (
            _headers(test_settings, csrf),
            {**valid, "rating": 8.25},
            game_id,
            422,
            "validation_error",
        ),
        (
            _headers(test_settings, csrf),
            {**valid, "rating": 10.5},
            game_id,
            422,
            "validation_error",
        ),
        (
            _headers(test_settings, csrf),
            {**valid, "reaction": "neutral"},
            game_id,
            422,
            "validation_error",
        ),
        (
            _headers(test_settings, csrf),
            {**valid, "unexpected": True},
            game_id,
            422,
            "validation_error",
        ),
        (_headers(test_settings, csrf), valid, 2_147_483_647, 404, "game_not_found"),
    ]

    for headers, payload, target, status, code in cases:
        response = client.put(
            f"/api/v1/me/games/{target}/feedback",
            headers=headers,
            json=payload,
        )
        assert response.status_code == status
        assert response.json()["error"]["code"] == code
        assert response.headers["cache-control"] == "no-store"
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(Interaction)) == 0


def test_all_empty_put_is_clear_and_feedback_pagination_is_stable(
    stage_4_feedback_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, factory = stage_4_feedback_client
    raw_token, csrf = _consent(client, test_settings)
    game_ids = _game_ids(client, 3)
    digest = session_token_digest(test_settings.anonymous_session_secret, raw_token)
    occurred_at = datetime(2026, 1, 2, tzinfo=UTC).replace(tzinfo=None)
    with factory.begin() as session:
        user_id = session.scalar(select(User.id).where(User.anonymous_token_digest == digest))
        assert user_id is not None
        for game_id in game_ids:
            session.add(
                Interaction(
                    user_id=user_id,
                    game_id=game_id,
                    interaction_type=InteractionType.LIKED,
                    occurred_at=occurred_at,
                )
            )

    first = client.get("/api/v1/me/feedback?page=1&page_size=2")
    second = client.get("/api/v1/me/feedback?page=2&page_size=2")
    beyond = client.get("/api/v1/me/feedback?page=99&page_size=2")

    assert first.status_code == 200
    assert first.json()["total"] == 3
    assert [item["game_id"] for item in first.json()["items"]] == sorted(game_ids)[:2]
    assert [item["game_id"] for item in second.json()["items"]] == sorted(game_ids)[2:]
    assert beyond.json()["items"] == []
    assert beyond.json()["total"] == 3

    cleared = client.put(
        f"/api/v1/me/games/{game_ids[0]}/feedback",
        headers=_headers(test_settings, csrf),
        json={"reaction": None, "played": False, "wishlisted": False, "rating": None},
    )
    assert cleared.status_code == 200
    assert cleared.json() is None
    assert client.get("/api/v1/me/feedback").json()["total"] == 2


@pytest.mark.parametrize(
    "query",
    ["page=0", "page=1000001", "page_size=0", "page_size=101"],
)
def test_feedback_pagination_bounds_use_standard_validation_envelope(
    stage_4_feedback_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
    query: str,
) -> None:
    client, _factory = stage_4_feedback_client
    _token, _csrf = _consent(client, test_settings)

    response = client.get(f"/api/v1/me/feedback?{query}")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.headers["cache-control"] == "no-store"
