from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier

import pytest
from app.commands.operator_safety import resolve_database_identity
from app.core.config import Settings
from app.core.security import csrf_token, generate_session_token, session_token_digest
from app.db.models import (
    Game,
    Interaction,
    InteractionType,
    RecommendationEvent,
    User,
    UserPreference,
)
from app.db.seed import load_seed_file, seed_database
from app.db.session import create_session_factory
from app.main import create_app
from app.repositories.recommendation_catalog import RecommendationCatalogRepository
from app.services.recommendation import create_recommendation_service
from app.services.retention import (
    AnonymousSessionRevocationService,
    RetentionCutoffs,
    RetentionService,
)
from fastapi.testclient import TestClient
from gamelens_recommender import build_artifact
from sqlalchemy import Engine, event, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.conftest import (
    make_consented_user,
    make_recommendation_event,
    make_revoked_legacy_user,
)

pytestmark = pytest.mark.integration


def make_game(slug: str) -> Game:
    return Game(
        title=slug.replace("-", " ").title(),
        slug=slug,
        description="Stage 4 persistence fixture",
        popularity_score=Decimal("1"),
    )


def test_stage_4_schema_columns_indexes_and_constraints(postgres_engine: Engine) -> None:
    inspector = inspect(postgres_engine)

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    assert {
        "anonymous_token_digest",
        "consent_version",
        "consented_at",
        "expires_at",
        "revoked_at",
    } <= user_columns
    assert "anonymous_key" not in user_columns
    assert "uq_users_anonymous_token_digest" in {
        constraint["name"] for constraint in inspector.get_unique_constraints("users")
    }
    assert {"ix_users_expires_at_id", "ix_users_revoked_at_id"} <= {
        index["name"] for index in inspector.get_indexes("users")
    }
    assert "ck_users_consent_lifecycle_valid" in {
        constraint["name"] for constraint in inspector.get_check_constraints("users")
    }

    interaction_columns = {column["name"] for column in inspector.get_columns("interactions")}
    assert "superseded_at" in interaction_columns
    assert {
        "uq_interactions_active_reaction",
        "uq_interactions_active_state_type",
        "ix_interactions_user_id_active_occurred_at",
    } <= {index["name"] for index in inspector.get_indexes("interactions")}
    assert "ck_interactions_superseded_not_before_occurrence" in {
        constraint["name"] for constraint in inspector.get_check_constraints("interactions")
    }

    event_columns = {column["name"] for column in inspector.get_columns("recommendation_events")}
    assert {
        "generation_id",
        "event_schema_version",
        "data_fingerprint",
        "ranking_policy_name",
        "ranking_policy_version",
    } <= event_columns
    assert "uq_recommendation_events_generation_id" in {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("recommendation_events")
    }
    assert {
        "ix_recommendation_events_generated_at_id",
        "ix_recommendation_events_policy_generated_at",
        "ix_recommendation_events_model_generated_at",
    } <= {index["name"] for index in inspector.get_indexes("recommendation_events")}
    assert "ck_recommendation_events_event_identity_complete" in {
        constraint["name"]
        for constraint in inspector.get_check_constraints("recommendation_events")
    }


@pytest.mark.parametrize(
    "user",
    [
        User(
            anonymous_token_digest="1" * 64,
            consent_version=None,
            consented_at=None,
            expires_at=None,
            revoked_at=None,
        ),
        User(
            anonymous_token_digest="2" * 64,
            consent_version="stage-4-v1",
            consented_at=datetime(2026, 1, 2, tzinfo=UTC),
            expires_at=datetime(2026, 1, 2, tzinfo=UTC),
            revoked_at=None,
        ),
        User(
            anonymous_token_digest="3" * 64,
            consent_version=" ",
            consented_at=datetime(2026, 1, 1, tzinfo=UTC),
            expires_at=datetime(2026, 1, 2, tzinfo=UTC),
            revoked_at=None,
        ),
    ],
)
def test_invalid_identity_lifecycle_is_rejected(
    postgres_session: Session,
    user: User,
) -> None:
    postgres_session.add(user)

    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_consented_and_revoked_legacy_identity_shapes_are_accepted(
    postgres_session: Session,
) -> None:
    active = make_consented_user("active-shape")
    legacy = make_revoked_legacy_user("legacy-shape")
    postgres_session.add_all([active, legacy])

    postgres_session.commit()

    assert active.id is not None
    assert legacy.id is not None
    assert legacy.consent_version is None
    assert legacy.revoked_at is not None


def test_duplicate_anonymous_token_digest_is_rejected(postgres_session: Session) -> None:
    first = make_consented_user("duplicate-digest")
    second = make_consented_user("duplicate-digest")
    postgres_session.add_all([first, second])

    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_temporal_interaction_constraints_allow_history_and_one_active_state(
    postgres_session: Session,
) -> None:
    user = make_consented_user("temporal-valid")
    game = make_game("temporal-valid-game")
    postgres_session.add_all([user, game])
    postgres_session.flush()
    occurred_at = datetime(2026, 1, 1, tzinfo=UTC)
    changed_at = occurred_at + timedelta(hours=1)
    postgres_session.add_all(
        [
            Interaction(
                user_id=user.id,
                game_id=game.id,
                interaction_type=InteractionType.LIKED,
                occurred_at=occurred_at,
                superseded_at=changed_at,
            ),
            Interaction(
                user_id=user.id,
                game_id=game.id,
                interaction_type=InteractionType.DISLIKED,
                occurred_at=changed_at,
            ),
            Interaction(
                user_id=user.id,
                game_id=game.id,
                interaction_type=InteractionType.PLAYED,
                occurred_at=changed_at,
            ),
            Interaction(
                user_id=user.id,
                game_id=game.id,
                interaction_type=InteractionType.RATED,
                value=Decimal("8.50"),
                occurred_at=changed_at,
            ),
        ]
    )

    postgres_session.commit()

    active = list(
        postgres_session.scalars(
            select(Interaction).where(Interaction.superseded_at.is_(None))
        ).all()
    )
    assert {item.interaction_type for item in active} == {
        InteractionType.DISLIKED,
        InteractionType.PLAYED,
        InteractionType.RATED,
    }


@pytest.mark.parametrize(
    ("first_type", "second_type"),
    [
        (InteractionType.LIKED, InteractionType.DISLIKED),
        (InteractionType.PLAYED, InteractionType.PLAYED),
        (InteractionType.WISHLISTED, InteractionType.WISHLISTED),
        (InteractionType.RATED, InteractionType.RATED),
    ],
)
def test_duplicate_active_feedback_dimension_is_rejected(
    postgres_session: Session,
    first_type: InteractionType,
    second_type: InteractionType,
) -> None:
    user = make_consented_user(f"duplicate-{first_type}-{second_type}")
    game = make_game(f"duplicate-{first_type}-{second_type}-game")
    postgres_session.add_all([user, game])
    postgres_session.flush()

    def value(interaction_type: InteractionType) -> Decimal | None:
        return Decimal("7.50") if interaction_type is InteractionType.RATED else None

    postgres_session.add_all(
        [
            Interaction(
                user_id=user.id,
                game_id=game.id,
                interaction_type=first_type,
                value=value(first_type),
            ),
            Interaction(
                user_id=user.id,
                game_id=game.id,
                interaction_type=second_type,
                value=value(second_type),
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_supersession_before_occurrence_is_rejected(postgres_session: Session) -> None:
    user = make_consented_user("bad-supersession")
    game = make_game("bad-supersession-game")
    postgres_session.add_all([user, game])
    postgres_session.flush()
    occurred_at = datetime(2026, 1, 2, tzinfo=UTC)
    postgres_session.add(
        Interaction(
            user_id=user.id,
            game_id=game.id,
            interaction_type=InteractionType.LIKED,
            occurred_at=occurred_at,
            superseded_at=occurred_at - timedelta(seconds=1),
        )
    )

    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_stage_4_event_requires_complete_identity_and_unique_generation_id(
    postgres_session: Session,
) -> None:
    user = make_consented_user("event-contract")
    postgres_session.add(user)
    postgres_session.flush()
    incomplete = RecommendationEvent(
        user_id=user.id,
        generation_id="incomplete-generation",
        event_schema_version="stage-4-v1",
        model_name="gamelens-content-tfidf",
        model_version="1.0.0",
        data_fingerprint=None,
        ranking_policy_name=None,
        ranking_policy_version=None,
        request_context={},
        result_summary=[],
    )
    postgres_session.add(incomplete)

    with pytest.raises(IntegrityError):
        postgres_session.commit()

    postgres_session.rollback()
    user = make_consented_user("event-contract-valid")
    postgres_session.add(user)
    postgres_session.flush()
    first = make_recommendation_event(user.id, "event-contract-valid")
    second = make_recommendation_event(user.id, "event-contract-valid")
    postgres_session.add_all([first, second])

    with pytest.raises(IntegrityError):
        postgres_session.commit()


@pytest.mark.parametrize("schema_version", ["arbitrary-v2", "legacy-v1"])
def test_event_contract_rejects_unrecognized_or_mixed_schema_identity(
    postgres_session: Session,
    schema_version: str,
) -> None:
    user = make_consented_user(f"event-schema-{schema_version}")
    postgres_session.add(user)
    postgres_session.flush()
    event = make_recommendation_event(user.id, f"event-schema-{schema_version}")
    event.event_schema_version = schema_version
    postgres_session.add(event)

    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_postgresql_personalized_http_commit_correlates_event_and_delete_cascades(
    postgres_session: Session,
    integration_settings: Settings,
    tmp_path: Path,
) -> None:
    seed_database(postgres_session, load_seed_file())
    catalog = RecommendationCatalogRepository(postgres_session).load()
    assert catalog.model_snapshot is not None
    postgres_session.rollback()
    artifact = build_artifact(catalog.model_snapshot, tmp_path / "stage-4-content")
    app = create_app(
        integration_settings,
        recommendation_service=create_recommendation_service(artifact),
    )

    with TestClient(app) as client:
        consent = client.post(
            "/api/v1/anonymous-sessions",
            headers={"Origin": "http://testserver"},
            json={"consent": True, "consent_version": integration_settings.consent_version},
        )
        assert consent.status_code == 201
        csrf = consent.json()["csrf_token"]
        games = client.get("/api/v1/games?page_size=3").json()["items"]
        protected_headers = {
            "Origin": "http://testserver",
            integration_settings.csrf_header_name: csrf,
        }
        saved = client.put(
            "/api/v1/me/preferences",
            headers=protected_headers,
            json={
                "selected_game_ids": [games[0]["id"]],
                "preferred_genres": ["strategy"],
                "preferred_tags": [],
                "preferred_platforms": [],
            },
        )
        assert saved.status_code == 200
        feedback = client.put(
            f"/api/v1/me/games/{games[1]['id']}/feedback",
            headers=protected_headers,
            json={
                "reaction": "liked",
                "played": False,
                "wishlisted": False,
                "rating": None,
            },
        )
        assert feedback.status_code == 200
        generated = client.post(
            "/api/v1/me/recommendations",
            headers=protected_headers,
            json={"top_k": 5},
        )
        assert generated.status_code == 200
        body = generated.json()

        postgres_session.rollback()
        stored_event = postgres_session.scalar(
            select(RecommendationEvent).where(
                RecommendationEvent.generation_id == body["generation_id"]
            )
        )
        assert stored_event is not None
        assert stored_event.event_schema_version == "stage-5-v1"
        assert stored_event.model_name == body["model_name"]
        assert stored_event.model_version == body["model_version"]
        assert stored_event.data_fingerprint == body["data_fingerprint"]
        assert stored_event.ranking_policy_name == body["policy"]["name"]
        assert stored_event.ranking_policy_version == body["policy"]["version"]
        assert stored_event.ranking_mode == body["ranking_mode"]
        assert stored_event.fallback_reason == body["fallback_reason"]
        assert stored_event.request_context["ranking_mode"] == body["ranking_mode"]
        assert stored_event.request_context["fallback_reason"] == body["fallback_reason"]
        assert len(stored_event.result_summary or []) == len(body["items"])
        assert [item["slug"] for item in stored_event.result_summary or []] == [
            item["game"]["slug"] for item in body["items"]
        ]

        statements: list[str] = []

        def capture_delete_sql(
            _connection: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            statements.append(statement)

        event.listen(app.state.database_engine, "before_cursor_execute", capture_delete_sql)
        deleted = client.delete("/api/v1/me", headers=protected_headers)
        event.remove(app.state.database_engine, "before_cursor_execute", capture_delete_sql)
        assert deleted.status_code == 204
        assert "Max-Age=0" in deleted.headers["set-cookie"]
        normalized = [statement.casefold() for statement in statements]
        assert not any("from user_preferences" in statement for statement in normalized)
        assert not any("from interactions" in statement for statement in normalized)
        assert not any("from recommendation_events" in statement for statement in normalized)

    postgres_session.rollback()
    assert postgres_session.scalar(select(func.count()).select_from(User)) == 0
    assert postgres_session.scalar(select(func.count()).select_from(UserPreference)) == 0
    assert postgres_session.scalar(select(func.count()).select_from(Interaction)) == 0
    assert postgres_session.scalar(select(func.count()).select_from(RecommendationEvent)) == 0
    assert postgres_session.scalar(select(func.count()).select_from(Game)) == 30


def test_postgresql_concurrent_feedback_replacements_serialize_one_active_state(
    postgres_session: Session,
    integration_settings: Settings,
) -> None:
    seed_database(postgres_session, load_seed_file())
    raw_token = generate_session_token()
    now = datetime.now(UTC)
    user = User(
        anonymous_token_digest=session_token_digest(
            integration_settings.anonymous_session_secret,
            raw_token,
        ),
        consent_version=integration_settings.consent_version,
        consented_at=now,
        expires_at=now + timedelta(days=1),
        revoked_at=None,
    )
    postgres_session.add(user)
    postgres_session.commit()
    game_id = postgres_session.scalar(select(Game.id).order_by(Game.id))
    assert game_id is not None
    barrier = Barrier(2)
    csrf = csrf_token(integration_settings.anonymous_session_secret, raw_token)

    def replace(reaction: str) -> int:
        app = create_app(integration_settings)
        with TestClient(app) as client:
            barrier.wait(timeout=10)
            response = client.put(
                f"/api/v1/me/games/{game_id}/feedback",
                headers={
                    "Origin": "http://testserver",
                    integration_settings.csrf_header_name: csrf,
                    "Cookie": (f"{integration_settings.anonymous_session_cookie_name}={raw_token}"),
                },
                json={
                    "reaction": reaction,
                    "played": False,
                    "wishlisted": False,
                    "rating": None,
                },
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(replace, ("liked", "disliked")))

    postgres_session.rollback()
    rows = list(
        postgres_session.scalars(
            select(Interaction)
            .where(
                Interaction.user_id == user.id,
                Interaction.game_id == game_id,
                Interaction.interaction_type.in_({InteractionType.LIKED, InteractionType.DISLIKED}),
            )
            .order_by(Interaction.id)
        )
    )
    assert statuses == [200, 200]
    assert len(rows) == 2
    assert sum(row.superseded_at is None for row in rows) == 1
    assert sum(row.superseded_at is not None for row in rows) == 1


def test_postgresql_bulk_revocation_uses_identity_creation_cohort_across_reconsent(
    postgres_session: Session,
    postgres_engine: Engine,
) -> None:
    now = datetime.now(UTC)
    created_before = now - timedelta(days=10)
    reconsented_old_identity = make_consented_user(
        "revocation-created-before",
        consented_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=179),
    )
    reconsented_old_identity.created_at = now - timedelta(days=20)
    new_identity = make_consented_user(
        "revocation-created-after",
        consented_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=179),
    )
    new_identity.created_at = now - timedelta(days=1)
    postgres_session.add_all([reconsented_old_identity, new_identity])
    postgres_session.commit()

    service = AnonymousSessionRevocationService(
        create_session_factory(postgres_engine),
        batch_size=1,
        clock=lambda: now,
    )
    preview = service.preview(created_before)
    result = service.revoke(created_before)

    assert preview.created_before == created_before
    assert preview.eligible == 1
    assert result.processed == 1
    assert result.remaining == 0
    postgres_session.rollback()
    postgres_session.expire_all()
    rows = {
        user.anonymous_token_digest: user
        for user in postgres_session.scalars(select(User).order_by(User.id))
    }
    assert rows[reconsented_old_identity.anonymous_token_digest].revoked_at == now
    assert rows[new_identity.anonymous_token_digest].revoked_at is None


def test_postgresql_retention_uses_resolved_identity_and_bounded_cascades(
    postgres_session: Session,
    postgres_engine: Engine,
    integration_settings: Settings,
) -> None:
    seed_database(postgres_session, load_seed_file())
    now = datetime.now(UTC)
    active = make_consented_user(
        "retention-active",
        consented_at=now - timedelta(days=30),
        expires_at=now + timedelta(days=150),
    )
    expired = make_consented_user(
        "retention-expired",
        consented_at=now - timedelta(days=181),
        expires_at=now - timedelta(days=1),
    )
    revoked = make_revoked_legacy_user(
        "retention-revoked",
        revoked_at=now - timedelta(days=10),
    )
    postgres_session.add_all([active, expired, revoked])
    postgres_session.flush()
    game_id = postgres_session.scalar(select(Game.id).order_by(Game.id))
    assert game_id is not None
    expired.preferences.append(
        UserPreference(preference_type="genre", value="strategy", weight=Decimal("1"))
    )
    postgres_session.add(
        Interaction(
            user_id=expired.id,
            game_id=game_id,
            interaction_type=InteractionType.PLAYED,
        )
    )
    old_event = make_recommendation_event(active.id, "retention-old")
    old_event.generated_at = now - timedelta(days=91)
    new_event = make_recommendation_event(active.id, "retention-new")
    new_event.generated_at = now - timedelta(days=89)
    expired_event = make_recommendation_event(expired.id, "retention-expired")
    expired_event.generated_at = now - timedelta(days=1)
    revoked_event = make_recommendation_event(revoked.id, "retention-revoked")
    revoked_event.event_schema_version = "legacy-v1"
    revoked_event.data_fingerprint = None
    revoked_event.ranking_policy_name = None
    revoked_event.ranking_policy_version = None
    revoked_event.generated_at = now - timedelta(days=1)
    postgres_session.add_all([old_event, new_event, expired_event, revoked_event])
    postgres_session.commit()

    resolved = resolve_database_identity(postgres_engine, integration_settings.database_url)
    assert resolved.database.endswith("_test")
    assert resolved.schema == "public"
    service = RetentionService(
        create_session_factory(postgres_engine),
        batch_size=1,
        clock=lambda: now,
    )
    cutoffs = RetentionCutoffs(
        events_before=now - timedelta(days=90),
        expired_before=now,
        revoked_before=now - timedelta(days=5),
    )
    preview = service.preview(cutoffs)
    result = service.purge(cutoffs)

    assert preview.eligible.events == 1
    assert preview.eligible.expired_users == 1
    assert preview.eligible.revoked_users == 1
    assert result.processed.events == 1
    assert result.processed.expired_users == 1
    assert result.processed.revoked_users == 1
    assert result.remaining.events == 0
    assert result.remaining.expired_users == 0
    assert result.remaining.revoked_users == 0
    postgres_session.rollback()
    assert set(postgres_session.scalars(select(User.id))) == {active.id}
    assert set(postgres_session.scalars(select(RecommendationEvent.generation_id))) == {
        new_event.generation_id
    }
    assert postgres_session.scalar(select(func.count()).select_from(Game)) == 30
