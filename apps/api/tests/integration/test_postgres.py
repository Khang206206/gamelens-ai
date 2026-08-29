from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from app.core.config import Settings
from app.core.security import generate_session_token, session_token_digest
from app.db.models import (
    Game,
    Genre,
    Interaction,
    InteractionType,
    Platform,
    RecommendationEvent,
    Tag,
    User,
    UserPreference,
    game_genres,
    game_platforms,
    game_tags,
)
from app.db.seed import load_seed_file, seed_database
from app.db.session import create_session_factory, session_scope
from app.main import create_app
from app.repositories.recommendation_catalog import RecommendationCatalogRepository
from app.services.recommendation import create_recommendation_service
from fastapi.testclient import TestClient
from gamelens_recommender import build_artifact
from sqlalchemy import Engine, delete, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.conftest import make_consented_user, make_recommendation_event

pytestmark = pytest.mark.integration


def make_game(
    slug: str,
    *,
    average_rating: Decimal | None = None,
    rating_count: int = 0,
    popularity_score: Decimal = Decimal("1.0"),
) -> Game:
    return Game(
        title=slug.replace("-", " ").title(),
        slug=slug,
        description="Integration test game",
        average_rating=average_rating,
        rating_count=rating_count,
        popularity_score=popularity_score,
    )


def test_migration_created_expected_schema_and_indexes(postgres_engine: Engine) -> None:
    inspector = inspect(postgres_engine)

    assert set(inspector.get_table_names()) >= {
        "alembic_version",
        "games",
        "genres",
        "tags",
        "platforms",
        "game_genres",
        "game_tags",
        "game_platforms",
        "users",
        "user_preferences",
        "interactions",
        "recommendation_events",
        "collaborative_artifact_builds",
        "collaborative_artifact_contributors",
    }
    game_indexes = {item["name"] for item in inspector.get_indexes("games")}
    assert {
        "ix_games_title",
        "ix_games_release_date",
        "ix_games_popularity_score_id",
    } <= game_indexes
    assert set(inspector.get_pk_constraint("game_genres")["constrained_columns"]) == {
        "game_id",
        "genre_id",
    }
    interaction_foreign_keys = {
        foreign_key["name"]: foreign_key
        for foreign_key in inspector.get_foreign_keys("interactions")
    }
    assert (
        interaction_foreign_keys["fk_interactions_game_id_games"]["options"]["ondelete"]
        == "RESTRICT"
    )
    assert (
        interaction_foreign_keys["fk_interactions_user_id_users"]["options"]["ondelete"]
        == "CASCADE"
    )
    contributor_indexes = {
        item["name"] for item in inspector.get_indexes("collaborative_artifact_contributors")
    }
    assert "ix_collaborative_artifact_contributors_user_id_build_id" in contributor_indexes
    contributor_foreign_keys = {
        tuple(foreign_key["constrained_columns"]): foreign_key
        for foreign_key in inspector.get_foreign_keys("collaborative_artifact_contributors")
    }
    assert contributor_foreign_keys[("build_id",)]["options"]["ondelete"] == "CASCADE"
    assert contributor_foreign_keys[("user_id",)]["options"]["ondelete"] == "CASCADE"


def test_seed_is_idempotent(postgres_session: Session) -> None:
    seed = load_seed_file()

    first = seed_database(postgres_session, seed)
    second = seed_database(postgres_session, seed)

    assert first.games.inserted == 30
    assert second.games.unchanged == 30
    assert second.taxonomies.unchanged == 36
    assert len(postgres_session.scalars(select(Game)).all()) == 30


def test_seed_updates_scalar_once(postgres_session: Session) -> None:
    seed = load_seed_file()
    seed_database(postgres_session, seed)
    target_seed = seed.games[0]
    target_seed.title = f"{target_seed.title} Updated"

    updated = seed_database(postgres_session, seed)
    unchanged = seed_database(postgres_session, seed)
    target = postgres_session.scalar(select(Game).where(Game.slug == target_seed.slug))

    assert updated.games.updated == 1
    assert unchanged.games.unchanged == 30
    assert target is not None
    assert target.title == target_seed.title


def test_seed_updates_associations_and_timestamp_once(postgres_session: Session) -> None:
    seed = load_seed_file()
    seed_database(postgres_session, seed)
    target_seed = seed.games[0]
    target = postgres_session.scalar(select(Game).where(Game.slug == target_seed.slug))
    assert target is not None
    original_updated_at = target.updated_at
    original_genres = set(target_seed.genre_slugs)
    replacement = next(
        item.slug for item in seed.taxonomies.genres if item.slug not in original_genres
    )
    target_seed.genre_slugs = [replacement]

    updated = seed_database(postgres_session, seed)
    postgres_session.expire_all()
    target = postgres_session.scalar(select(Game).where(Game.slug == target_seed.slug))
    assert target is not None

    assert updated.games.updated == 1
    assert {genre.slug for genre in target.genres} == {replacement}
    assert target.updated_at > original_updated_at
    unchanged = seed_database(postgres_session, seed)
    assert unchanged.games.unchanged == 30


def test_seed_rolls_back_and_restores_session_after_failure(postgres_session: Session) -> None:
    postgres_session.add(Genre(name="Action", slug="legacy-action"))
    postgres_session.commit()

    with pytest.raises(IntegrityError):
        seed_database(postgres_session, load_seed_file())

    assert postgres_session.scalar(select(Genre).where(Genre.slug == "legacy-action")) is not None
    assert postgres_session.scalar(select(Game)) is None


@pytest.mark.parametrize(
    ("average_rating", "popularity_score"),
    [
        (Decimal("-0.01"), Decimal("1")),
        (Decimal("10.01"), Decimal("1")),
        (Decimal("5"), Decimal("-0.01")),
    ],
)
def test_invalid_game_numeric_signals_are_rejected(
    postgres_session: Session,
    average_rating: Decimal,
    popularity_score: Decimal,
) -> None:
    postgres_session.add(
        make_game(
            "invalid-numeric-signals",
            average_rating=average_rating,
            popularity_score=popularity_score,
        )
    )

    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_negative_rating_count_is_rejected(postgres_session: Session) -> None:
    postgres_session.add(make_game("invalid-rating-count", rating_count=-1))

    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_duplicate_game_slug_is_rejected(postgres_session: Session) -> None:
    postgres_session.add_all([make_game("duplicate"), make_game("duplicate")])

    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_invalid_slug_format_is_rejected(postgres_session: Session) -> None:
    postgres_session.add(make_game("invalid_slug"))

    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_duplicate_association_pair_is_rejected(postgres_session: Session) -> None:
    genre = Genre(name="Strategy", slug="strategy")
    game = make_game("duplicate-association")
    game.genres = [genre, genre]
    postgres_session.add(game)

    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_invalid_preference_weight_is_rejected(postgres_session: Session) -> None:
    user = make_consented_user("constraint-user")
    user.preferences.append(
        UserPreference(preference_type="genre", value="rpg", weight=Decimal("1.5"))
    )
    postgres_session.add(user)

    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_invalid_preference_type_is_rejected(postgres_session: Session) -> None:
    user = make_consented_user("invalid-preference-type-user")
    user.preferences.append(
        UserPreference(preference_type="unknown", value="rpg", weight=Decimal("1"))
    )
    postgres_session.add(user)

    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_duplicate_user_preference_is_rejected(postgres_session: Session) -> None:
    user = make_consented_user("duplicate-preference-user")
    user.preferences.extend(
        [
            UserPreference(preference_type="genre", value="rpg", weight=Decimal("1")),
            UserPreference(preference_type="genre", value="rpg", weight=Decimal("-1")),
        ]
    )
    postgres_session.add(user)

    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_foreign_keys_are_enforced(postgres_session: Session) -> None:
    postgres_session.add(
        Interaction(
            user_id=999999,
            game_id=999999,
            interaction_type=InteractionType.LIKED,
        )
    )

    with pytest.raises(IntegrityError):
        postgres_session.commit()


@pytest.mark.parametrize(
    ("interaction_type", "value", "slug"),
    [
        ("rated", None, "rated-missing"),
        ("rated", Decimal("-0.01"), "rated-negative"),
        ("rated", Decimal("10.01"), "rated-too-large"),
        ("liked", Decimal("1"), "liked-with-value"),
        ("unknown", None, "unknown-interaction"),
    ],
)
def test_invalid_interaction_type_or_value_is_rejected(
    postgres_session: Session,
    interaction_type: str,
    value: Decimal | None,
    slug: str,
) -> None:
    user = make_consented_user(f"{slug}-user")
    game = make_game(slug)
    postgres_session.add_all([user, game])
    postgres_session.flush()
    postgres_session.add(
        Interaction(
            user_id=user.id,
            game_id=game.id,
            interaction_type=interaction_type,
            value=value,
        )
    )

    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_valid_interaction_value_boundaries_are_accepted(postgres_session: Session) -> None:
    user = make_consented_user("valid-interaction-user")
    lower_game = make_game("valid-interaction-lower-game")
    upper_game = make_game("valid-interaction-upper-game")
    postgres_session.add_all([user, lower_game, upper_game])
    postgres_session.flush()
    postgres_session.add_all(
        [
            Interaction(
                user_id=user.id,
                game_id=lower_game.id,
                interaction_type=InteractionType.RATED,
                value=Decimal("0"),
            ),
            Interaction(
                user_id=user.id,
                game_id=upper_game.id,
                interaction_type=InteractionType.RATED,
                value=Decimal("10"),
            ),
            Interaction(
                user_id=user.id,
                game_id=lower_game.id,
                interaction_type=InteractionType.LIKED,
            ),
        ]
    )

    postgres_session.commit()
    assert (
        postgres_session.scalar(select(Interaction).where(Interaction.value == Decimal("10")))
        is not None
    )


def test_user_delete_cascades_but_game_delete_is_restricted(
    postgres_session: Session,
) -> None:
    user = make_consented_user("delete-policy-user")
    game = make_game("delete-policy-game")
    postgres_session.add_all([user, game])
    postgres_session.flush()
    interaction = Interaction(
        user_id=user.id,
        game_id=game.id,
        interaction_type=InteractionType.LIKED,
    )
    postgres_session.add(interaction)
    postgres_session.commit()
    user_id = user.id
    game_id = game.id
    interaction_id = interaction.id

    with pytest.raises(IntegrityError):
        postgres_session.execute(delete(Game).where(Game.id == game_id))
        postgres_session.commit()
    postgres_session.rollback()

    postgres_session.execute(delete(User).where(User.id == user_id))
    postgres_session.commit()
    assert postgres_session.get(Interaction, interaction_id) is None
    assert postgres_session.get(Game, game_id) is not None


@pytest.mark.parametrize(
    ("request_context", "result_summary", "identity"),
    [
        ([], None, "json-context-array-user"),
        ({}, {"game_id": 1}, "json-summary-object-user"),
    ],
)
def test_recommendation_event_jsonb_shapes_are_enforced(
    postgres_session: Session,
    request_context: object,
    result_summary: object,
    identity: str,
) -> None:
    user = make_consented_user(identity)
    postgres_session.add(user)
    postgres_session.flush()
    event = make_recommendation_event(
        user.id,
        identity,
        request_context=request_context,
        result_summary=[],
    )
    event.result_summary = result_summary
    postgres_session.add(event)

    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_recommendation_event_jsonb_defaults_and_arrays(postgres_session: Session) -> None:
    user = make_consented_user("valid-json-shape-user")
    postgres_session.add(user)
    postgres_session.flush()
    event = make_recommendation_event(
        user.id,
        "valid-json-shape-user",
        result_summary=[{"game_id": 1}],
    )
    postgres_session.add(event)
    postgres_session.commit()
    postgres_session.refresh(event)

    assert event.request_context == {}
    assert event.result_summary == [{"game_id": 1}]


def test_request_session_rolls_back_on_error(
    postgres_session: Session,
    postgres_engine: Engine,
) -> None:
    dependency = session_scope(create_session_factory(postgres_engine))
    request_session = next(dependency)
    request_session.add(make_game("rolled-back-game"))
    request_session.flush()

    with pytest.raises(RuntimeError, match="request failed"):
        dependency.throw(RuntimeError("request failed"))

    assert postgres_session.scalar(select(Game).where(Game.slug == "rolled-back-game")) is None


def test_catalog_endpoints_use_postgresql(
    postgres_session: Session,
    integration_settings: Settings,
) -> None:
    seed_database(postgres_session, load_seed_file())
    app = create_app(integration_settings)

    with TestClient(app) as client:
        health = client.get("/health")
        catalog = client.get("/api/v1/games?page=1&page_size=5")
        detail = client.get(f"/api/v1/games/{catalog.json()['items'][0]['id']}")
        genres = client.get("/api/v1/metadata/genres")
        model_status = client.get("/api/v1/models/status")

    assert health.status_code == 200
    assert health.json()["database"] == "ready"
    assert catalog.status_code == 200
    assert catalog.json()["total"] == 30
    assert len(catalog.json()["items"]) == 5
    assert detail.status_code == 200
    assert detail.json()["genres"]
    assert genres.status_code == 200
    assert genres.json()
    assert model_status.json()["status"] == "not_configured"


def test_ready_recommendation_uses_postgresql_snapshot_without_writes(
    postgres_session: Session,
    integration_settings: Settings,
    tmp_path: Path,
) -> None:
    seed_database(postgres_session, load_seed_file())
    snapshot = RecommendationCatalogRepository(postgres_session).load().model_snapshot
    postgres_session.rollback()
    artifact = build_artifact(snapshot, tmp_path / "content-v1")
    raw_token = generate_session_token()
    consented_at = datetime.now(UTC)
    user = make_consented_user(
        "stateless-valid-cookie-user",
        consent_version=integration_settings.consent_version,
        consented_at=consented_at,
        expires_at=consented_at + timedelta(days=1),
    )
    user.anonymous_token_digest = session_token_digest(
        integration_settings.anonymous_session_secret,
        raw_token,
    )
    user.preferences.append(
        UserPreference(preference_type="genre", value="rpg", weight=Decimal("1"))
    )
    postgres_session.add(user)
    postgres_session.commit()
    tracked_tables = (
        Game.__table__,
        Genre.__table__,
        Tag.__table__,
        Platform.__table__,
        game_genres,
        game_tags,
        game_platforms,
        User.__table__,
        UserPreference.__table__,
        Interaction.__table__,
        RecommendationEvent.__table__,
    )
    before = {
        table.name: postgres_session.scalar(select(func.count()).select_from(table))
        for table in tracked_tables
    }
    game_id = postgres_session.scalar(select(Game.id).order_by(Game.id))
    assert game_id is not None
    app = create_app(
        integration_settings,
        recommendation_service=create_recommendation_service(artifact),
    )

    with TestClient(app) as client:
        status = client.get("/api/v1/models/status")
        response = client.post(
            "/api/v1/recommendations",
            headers={
                "Cookie": (f"{integration_settings.anonymous_session_cookie_name}={raw_token}")
            },
            json={"selected_game_ids": [game_id], "preferred_genres": ["strategy"]},
        )
        malformed_cookie_response = client.post(
            "/api/v1/recommendations",
            headers={"Cookie": (f"{integration_settings.anonymous_session_cookie_name}=malformed")},
            json={"selected_game_ids": [game_id], "preferred_genres": ["strategy"]},
        )

    postgres_session.rollback()
    after = {
        table.name: postgres_session.scalar(select(func.count()).select_from(table))
        for table in tracked_tables
    }
    assert status.json()["status"] == "ready"
    assert response.status_code == 200
    assert response.json()["items"]
    assert "set-cookie" not in response.headers
    assert malformed_cookie_response.status_code == 200
    assert malformed_cookie_response.json()["items"]
    assert "set-cookie" not in malformed_cookie_response.headers
    assert before == after
