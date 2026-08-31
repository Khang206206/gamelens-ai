from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import Settings
from app.db.models import CollaborativeDataRevision, RecommendationEvent, User
from app.db.session import EXPECTED_SCHEMA_REVISION
from app.repositories.recommendation_events import RecommendationEventRepository
from app.schemas.recommendation_events import (
    Stage5RecommendationEventContext,
    Stage5RecommendationEventIdentity,
    Stage5RecommendationEventResultItem,
)
from app.services.retention import RetentionCutoffs, RetentionService
from sqlalchemy import Engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import make_consented_user, make_recommendation_event
from tests.integration.conftest import (
    assert_connection_targets_guarded_database,
    truncate_application_tables,
)

pytestmark = pytest.mark.integration


def _identity(*, fallback: bool = False) -> Stage5RecommendationEventIdentity:
    return Stage5RecommendationEventIdentity(
        content_model_name="gamelens-content-tfidf",
        content_model_version="1.0.0",
        content_data_fingerprint="a" * 64,
        feedback_policy={
            "name": "gamelens-feedback-adjustment",
            "version": "1.0.0",
        },
        ranking_mode="stage_4_fallback" if fallback else "hybrid",
        fallback_reason="artifact_missing" if fallback else None,
        hybrid_policy=(
            None if fallback else {"name": "gamelens-hybrid-ranking", "version": "1.0.0"}
        ),
        collaborative_model=(
            None
            if fallback
            else {
                "name": "item-item-cosine",
                "version": "1.0.0",
                "interaction_fingerprint": "b" * 64,
                "scoring_policy": {
                    "name": "gamelens-collaborative-scoring",
                    "version": "1.0.0",
                },
            }
        ),
    )


def _context(*, fallback: bool = False) -> Stage5RecommendationEventContext:
    return Stage5RecommendationEventContext(
        top_k=5,
        ranking_mode="stage_4_fallback" if fallback else "hybrid",
        fallback_reason="artifact_missing" if fallback else None,
        selected_game_slugs=["emberfall-tactics"],
        preferred_genres=["strategy"],
        preferred_tags=[],
        preferred_platforms=["pc"],
        positive_source_slugs=["emberfall-tactics"],
        disliked_count=1,
        played_count=2,
        positive_source_count=1,
        effective_state_fingerprint="c" * 64,
    )


def _result(*, fallback: bool = False) -> Stage5RecommendationEventResultItem:
    if fallback:
        return Stage5RecommendationEventResultItem(
            slug="starbound-couriers",
            rank=1,
            candidate_origin="content",
            base_units=400_000,
            base_weight_units=1_000_000,
            base_contribution_units=400_000,
            affinity_units=0,
            affinity_weight_units=0,
            affinity_contribution_units=0,
            collaborative_supported=False,
            collaborative_units=0,
            collaborative_weight_units=0,
            collaborative_contribution_units=0,
            collaborative_item_support=None,
            collaborative_source_edge_count=0,
            pre_played_units=400_000,
            played_factor_units=1_000_000,
            played_delta_units=0,
            final_units=400_000,
        )
    return Stage5RecommendationEventResultItem(
        slug="starbound-couriers",
        rank=1,
        candidate_origin="both",
        base_units=400_000,
        base_weight_units=800_000,
        base_contribution_units=320_000,
        affinity_units=200_000,
        affinity_weight_units=100_000,
        affinity_contribution_units=20_000,
        collaborative_supported=True,
        collaborative_units=500_000,
        collaborative_weight_units=100_000,
        collaborative_contribution_units=50_000,
        collaborative_item_support=12,
        collaborative_source_edge_count=1,
        pre_played_units=390_000,
        played_factor_units=900_000,
        played_delta_units=-39_000,
        final_units=351_000,
    )


def _add_event(
    session: Session,
    *,
    user_id: int,
    generation_id: str,
    fallback: bool = False,
) -> RecommendationEvent:
    return RecommendationEventRepository(session).add_stage_5(
        generation_id=generation_id,
        user_id=user_id,
        identity=_identity(fallback=fallback),
        context=_context(fallback=fallback),
        result=[_result(fallback=fallback)],
    )


def _alembic_config(connection: object) -> Config:
    config = Config("alembic.ini")
    config.attributes["connection"] = connection
    return config


def test_0010_populated_upgrade_and_downgrade_preserve_prior_event_rows(
    postgres_engine: Engine,
    integration_settings: Settings,
) -> None:
    truncate_application_tables(postgres_engine, integration_settings)
    try:
        with postgres_engine.connect() as connection:
            assert_connection_targets_guarded_database(connection, integration_settings)
            connection.rollback()
            config = _alembic_config(connection)
            command.downgrade(config, "0009_stage_5_label_changes")
            user_id = connection.scalar(
                text(
                    """
                    INSERT INTO users (
                        anonymous_token_digest, consent_version, consented_at, expires_at
                    ) VALUES (
                        :digest, 'stage-4-v1', :consented_at, :expires_at
                    ) RETURNING id
                    """
                ),
                {
                    "digest": "d" * 64,
                    "consented_at": datetime(2026, 1, 1, tzinfo=UTC),
                    "expires_at": datetime(2026, 7, 1, tzinfo=UTC),
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO recommendation_events (
                        user_id, generation_id, event_schema_version,
                        model_name, model_version, data_fingerprint,
                        ranking_policy_name, ranking_policy_version,
                        request_context, result_summary
                    ) VALUES
                    (
                        :user_id, 'prior-legacy', 'legacy-v1',
                        'legacy-model', '1', NULL, NULL, NULL,
                        '{}'::jsonb, '[]'::jsonb
                    ),
                    (
                        :user_id, 'prior-stage-4', 'stage-4-v1',
                        'content-model', '1', :fingerprint, 'feedback-policy', '1',
                        '{}'::jsonb, '[]'::jsonb
                    )
                    """
                ),
                {"user_id": user_id, "fingerprint": "e" * 64},
            )
            connection.commit()

            command.upgrade(config, "head")
            command.check(config)
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                EXPECTED_SCHEMA_REVISION
            )
            rows = connection.execute(
                text(
                    """
                    SELECT event_schema_version, ranking_mode, fallback_reason,
                           hybrid_policy_name, collaborative_model_name
                    FROM recommendation_events
                    ORDER BY generation_id
                    """
                )
            ).mappings()
            assert [dict(row) for row in rows] == [
                {
                    "event_schema_version": "legacy-v1",
                    "ranking_mode": None,
                    "fallback_reason": None,
                    "hybrid_policy_name": None,
                    "collaborative_model_name": None,
                },
                {
                    "event_schema_version": "stage-4-v1",
                    "ranking_mode": None,
                    "fallback_reason": None,
                    "hybrid_policy_name": None,
                    "collaborative_model_name": None,
                },
            ]
            connection.rollback()

            command.downgrade(config, "0009_stage_5_label_changes")
            assert connection.scalar(text("SELECT count(*) FROM recommendation_events")) == 2
            assert "ranking_mode" not in {
                column["name"]
                for column in inspect(connection).get_columns("recommendation_events")
            }
            connection.rollback()

            command.upgrade(config, "head")
            assert connection.scalar(text("SELECT count(*) FROM recommendation_events")) == 2
            connection.rollback()
    finally:
        with postgres_engine.connect() as connection:
            assert_connection_targets_guarded_database(connection, integration_settings)
            connection.rollback()
            command.upgrade(_alembic_config(connection), "head")
        truncate_application_tables(postgres_engine, integration_settings)


def test_stage_5_event_schema_columns_index_and_constraint(postgres_engine: Engine) -> None:
    inspector = inspect(postgres_engine)
    columns = {column["name"] for column in inspector.get_columns("recommendation_events")}
    assert {
        "ranking_mode",
        "fallback_reason",
        "hybrid_policy_name",
        "hybrid_policy_version",
        "collaborative_model_name",
        "collaborative_model_version",
        "collaborative_interaction_fingerprint",
        "collaborative_policy_name",
        "collaborative_policy_version",
    } <= columns
    assert "ix_recommendation_events_mode_generated_at" in {
        index["name"] for index in inspector.get_indexes("recommendation_events")
    }
    assert "ck_recommendation_events_event_identity_complete" in {
        constraint["name"]
        for constraint in inspector.get_check_constraints("recommendation_events")
    }


def test_stage_5_repository_persists_hybrid_and_fallback_without_advancing_labels(
    postgres_session: Session,
) -> None:
    user = make_consented_user("stage-5-event-persistence")
    postgres_session.add(user)
    postgres_session.commit()
    revision_before = postgres_session.scalar(select(CollaborativeDataRevision.revision))

    hybrid = _add_event(
        postgres_session,
        user_id=user.id,
        generation_id="stage-5-hybrid-event",
    )
    fallback = _add_event(
        postgres_session,
        user_id=user.id,
        generation_id="stage-5-fallback-event",
        fallback=True,
    )
    postgres_session.commit()
    revision_after = postgres_session.scalar(select(CollaborativeDataRevision.revision))

    assert revision_after == revision_before
    assert hybrid.ranking_mode == "hybrid"
    assert hybrid.hybrid_policy_name == "gamelens-hybrid-ranking"
    assert hybrid.collaborative_model_name == "item-item-cosine"
    assert hybrid.collaborative_policy_name == "gamelens-collaborative-scoring"
    assert hybrid.result_summary == [_result().model_dump(mode="json")]
    assert fallback.ranking_mode == "stage_4_fallback"
    assert fallback.fallback_reason == "artifact_missing"
    assert fallback.hybrid_policy_name is None
    assert fallback.collaborative_model_name is None
    assert fallback.collaborative_policy_name is None


@pytest.mark.parametrize(
    "invalid_shape",
    [
        "context_mode",
        "context_mode_missing",
        "fallback_identity",
        "fingerprint_missing",
        "mode_missing",
        "top_k",
    ],
)
def test_postgresql_rejects_invalid_stage_5_event_shapes(
    postgres_session: Session,
    invalid_shape: str,
) -> None:
    user = make_consented_user(f"stage-5-invalid-{invalid_shape}")
    postgres_session.add(user)
    postgres_session.flush()
    event = _add_event(
        postgres_session,
        user_id=user.id,
        generation_id=f"stage-5-invalid-{invalid_shape}",
    )
    if invalid_shape == "context_mode":
        event.request_context = {"ranking_mode": "stage_4_fallback", "fallback_reason": None}
    elif invalid_shape == "context_mode_missing":
        event.request_context = {"fallback_reason": None}
    elif invalid_shape == "fallback_identity":
        event.ranking_mode = "stage_4_fallback"
        event.fallback_reason = "artifact_missing"
        event.request_context = {
            "ranking_mode": "stage_4_fallback",
            "fallback_reason": "artifact_missing",
        }
    elif invalid_shape == "fingerprint_missing":
        event.data_fingerprint = None
    elif invalid_shape == "mode_missing":
        event.ranking_mode = None
    else:
        event.result_summary = [{} for _ in range(21)]

    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_stage_5_events_follow_existing_retention_and_user_cascade(
    postgres_session: Session,
    postgres_engine: Engine,
) -> None:
    now = datetime.now(UTC)
    old_user = make_consented_user("stage-5-retention-old", expires_at=now + timedelta(days=1))
    current_user = make_consented_user(
        "stage-5-retention-current", expires_at=now + timedelta(days=1)
    )
    postgres_session.add_all([old_user, current_user])
    postgres_session.flush()
    old_event = _add_event(
        postgres_session,
        user_id=old_user.id,
        generation_id="stage-5-retention-old",
    )
    _add_event(
        postgres_session,
        user_id=current_user.id,
        generation_id="stage-5-retention-current",
        fallback=True,
    )
    old_event.generated_at = now - timedelta(days=91)
    postgres_session.commit()

    factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)
    result = RetentionService(factory, batch_size=10, clock=lambda: now).purge(
        RetentionCutoffs(events_before=now - timedelta(days=90), expired_before=now)
    )
    postgres_session.rollback()
    assert result.processed.events == 1
    assert postgres_session.scalar(select(func.count()).select_from(RecommendationEvent)) == 1

    persisted_user = postgres_session.get(User, current_user.id)
    assert persisted_user is not None
    postgres_session.delete(persisted_user)
    postgres_session.commit()
    assert postgres_session.scalar(select(func.count()).select_from(RecommendationEvent)) == 0


def test_stage_4_rows_keep_all_stage_5_identity_columns_null(postgres_session: Session) -> None:
    user = make_consented_user("stage-4-event-compatibility")
    postgres_session.add(user)
    postgres_session.flush()
    event = make_recommendation_event(user.id, "stage-4-event-compatibility")
    postgres_session.add(event)
    postgres_session.commit()

    assert event.event_schema_version == "stage-4-v1"
    assert event.ranking_mode is None
    assert event.fallback_reason is None
    assert event.hybrid_policy_name is None
    assert event.collaborative_model_name is None
    assert event.collaborative_policy_name is None
