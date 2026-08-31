from copy import deepcopy
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from app.db.base import Base
from app.db.models import RecommendationEvent, User
from app.repositories.recommendation_events import (
    MAX_EVENT_CONTEXT_BYTES,
    MAX_EVENT_RESULT_BYTES,
    RecommendationEventRepository,
    _validated_json,
)
from app.schemas.recommendation_events import (
    Stage5RecommendationEventContext,
    Stage5RecommendationEventIdentity,
    Stage5RecommendationEventResultItem,
)
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def _hybrid_identity() -> dict[str, object]:
    return {
        "content_model_name": "gamelens-content-tfidf",
        "content_model_version": "1.0.0",
        "content_data_fingerprint": "a" * 64,
        "feedback_policy": {
            "name": "gamelens-feedback-adjustment",
            "version": "1.0.0",
        },
        "ranking_mode": "hybrid",
        "fallback_reason": None,
        "hybrid_policy": {
            "name": "gamelens-hybrid-ranking",
            "version": "1.0.0",
        },
        "collaborative_model": {
            "name": "item-item-cosine",
            "version": "1.0.0",
            "interaction_fingerprint": "b" * 64,
            "scoring_policy": {
                "name": "gamelens-collaborative-scoring",
                "version": "1.0.0",
            },
        },
    }


def _fallback_identity() -> dict[str, object]:
    payload = _hybrid_identity()
    payload.update(
        {
            "ranking_mode": "stage_4_fallback",
            "fallback_reason": "artifact_missing",
            "hybrid_policy": None,
            "collaborative_model": None,
        }
    )
    return payload


def _context(*, fallback: bool = False) -> dict[str, object]:
    return {
        "top_k": 5,
        "ranking_mode": "stage_4_fallback" if fallback else "hybrid",
        "fallback_reason": "artifact_missing" if fallback else None,
        "selected_game_slugs": ["emberfall-tactics"],
        "preferred_genres": ["strategy"],
        "preferred_tags": [],
        "preferred_platforms": ["pc"],
        "positive_source_slugs": ["emberfall-tactics"],
        "disliked_count": 1,
        "played_count": 2,
        "positive_source_count": 1,
        "effective_state_fingerprint": "c" * 64,
    }


def _hybrid_result(*, slug: str = "starbound-couriers", rank: int = 1) -> dict[str, object]:
    return {
        "slug": slug,
        "rank": rank,
        "candidate_origin": "both",
        "base_units": 400_000,
        "base_weight_units": 800_000,
        "base_contribution_units": 320_000,
        "affinity_units": 200_000,
        "affinity_weight_units": 100_000,
        "affinity_contribution_units": 20_000,
        "collaborative_supported": True,
        "collaborative_units": 500_000,
        "collaborative_weight_units": 100_000,
        "collaborative_contribution_units": 50_000,
        "collaborative_item_support": 12,
        "collaborative_source_edge_count": 1,
        "pre_played_units": 390_000,
        "played_factor_units": 900_000,
        "played_delta_units": -39_000,
        "final_units": 351_000,
    }


def _fallback_result() -> dict[str, object]:
    payload = _hybrid_result()
    payload.update(
        {
            "candidate_origin": "content",
            "base_weight_units": 1_000_000,
            "base_contribution_units": 400_000,
            "affinity_units": 0,
            "affinity_weight_units": 0,
            "affinity_contribution_units": 0,
            "collaborative_supported": False,
            "collaborative_units": 0,
            "collaborative_weight_units": 0,
            "collaborative_contribution_units": 0,
            "collaborative_item_support": None,
            "collaborative_source_edge_count": 0,
            "pre_played_units": 400_000,
            "played_factor_units": 1_000_000,
            "played_delta_units": 0,
            "final_units": 400_000,
        }
    )
    return payload


def _repository() -> tuple[RecommendationEventRepository, Mock]:
    session = Mock(spec=Session)
    return RecommendationEventRepository(session), session


def test_stage_5_event_identity_requires_truthful_mode_specific_components() -> None:
    hybrid = Stage5RecommendationEventIdentity.model_validate(_hybrid_identity())
    fallback = Stage5RecommendationEventIdentity.model_validate(_fallback_identity())

    assert hybrid.collaborative_model is not None
    assert fallback.fallback_reason == "artifact_missing"
    assert fallback.hybrid_policy is None

    missing_component = _hybrid_identity()
    missing_component["collaborative_model"] = None
    with pytest.raises(ValidationError):
        Stage5RecommendationEventIdentity.model_validate(missing_component)

    false_fallback = _fallback_identity()
    false_fallback["hybrid_policy"] = _hybrid_identity()["hybrid_policy"]
    with pytest.raises(ValidationError):
        Stage5RecommendationEventIdentity.model_validate(false_fallback)


def test_stage_5_event_context_is_bounded_distinct_and_counted() -> None:
    context = Stage5RecommendationEventContext.model_validate(_context())
    assert context.positive_source_count == 1

    duplicate = _context()
    duplicate["selected_game_slugs"] = ["same-game", "same-game"]
    with pytest.raises(ValidationError):
        Stage5RecommendationEventContext.model_validate(duplicate)

    bad_count = _context()
    bad_count["positive_source_count"] = 0
    with pytest.raises(ValidationError):
        Stage5RecommendationEventContext.model_validate(bad_count)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("collaborative_contribution_units", 50_001),
        ("pre_played_units", 389_999),
        ("final_units", 350_999),
        ("played_delta_units", -38_999),
        ("collaborative_source_edge_count", 0),
    ],
)
def test_stage_5_event_result_rejects_nonreconstructible_or_incomplete_units(
    field: str,
    value: object,
) -> None:
    payload = _hybrid_result()
    payload[field] = value

    with pytest.raises(ValidationError):
        Stage5RecommendationEventResultItem.model_validate(payload)


def test_add_stage_5_maps_complete_hybrid_identity_and_compact_payload() -> None:
    repository, session = _repository()
    identity = Stage5RecommendationEventIdentity.model_validate(_hybrid_identity())
    context = Stage5RecommendationEventContext.model_validate(_context())
    result = [Stage5RecommendationEventResultItem.model_validate(_hybrid_result())]

    event = repository.add_stage_5(
        generation_id="1" * 32,
        user_id=42,
        identity=identity,
        context=context,
        result=result,
    )

    session.add.assert_called_once_with(event)
    assert event.event_schema_version == "stage-5-v1"
    assert event.model_name == "gamelens-content-tfidf"
    assert event.ranking_mode == "hybrid"
    assert event.fallback_reason is None
    assert event.hybrid_policy_name == "gamelens-hybrid-ranking"
    assert event.collaborative_model_name == "item-item-cosine"
    assert event.collaborative_interaction_fingerprint == "b" * 64
    assert event.collaborative_policy_name == "gamelens-collaborative-scoring"
    assert event.request_context["ranking_mode"] == "hybrid"
    assert event.result_summary == [result[0].model_dump(mode="json")]
    assert "explanation" not in event.result_summary[0]
    assert "collaborative_source_edges" not in event.result_summary[0]


def test_add_stage_5_fallback_omits_unapplied_component_identity() -> None:
    repository, _session = _repository()
    event = repository.add_stage_5(
        generation_id="2" * 32,
        user_id=42,
        identity=Stage5RecommendationEventIdentity.model_validate(_fallback_identity()),
        context=Stage5RecommendationEventContext.model_validate(_context(fallback=True)),
        result=[Stage5RecommendationEventResultItem.model_validate(_fallback_result())],
    )

    assert event.ranking_mode == "stage_4_fallback"
    assert event.fallback_reason == "artifact_missing"
    assert event.hybrid_policy_name is None
    assert event.collaborative_model_name is None
    assert event.collaborative_policy_name is None


def test_add_stage_5_round_trips_through_the_orm_mapping() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as session:
            now = datetime(2026, 8, 31, tzinfo=UTC)
            user = User(
                anonymous_token_digest="f" * 64,
                consent_version="stage-4-v1",
                consented_at=now,
                expires_at=now + timedelta(days=1),
            )
            session.add(user)
            session.flush()
            _add_event = RecommendationEventRepository(session).add_stage_5
            _add_event(
                generation_id="4" * 32,
                user_id=user.id,
                identity=Stage5RecommendationEventIdentity.model_validate(_hybrid_identity()),
                context=Stage5RecommendationEventContext.model_validate(_context()),
                result=[Stage5RecommendationEventResultItem.model_validate(_hybrid_result())],
            )
            session.commit()

            stored = session.scalar(select(RecommendationEvent))
            assert stored is not None
            assert stored.event_schema_version == "stage-5-v1"
            assert stored.ranking_mode == "hybrid"
            assert stored.collaborative_policy_version == "1.0.0"
            assert stored.result_summary == [_hybrid_result()]
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.mark.parametrize(
    "mutation",
    ["empty", "mode", "reason", "rank", "duplicate", "fallback_weight"],
)
def test_add_stage_5_rejects_cross_payload_inconsistency(mutation: str) -> None:
    repository, session = _repository()
    identity_payload = _hybrid_identity()
    context_payload = _context()
    result_payloads = [_hybrid_result()]
    if mutation == "empty":
        result_payloads = []
    elif mutation == "mode":
        context_payload = _context(fallback=True)
    elif mutation == "reason":
        identity_payload = _fallback_identity()
        context_payload = _context(fallback=True)
        context_payload["fallback_reason"] = "artifact_corrupt"
        result_payloads = [_fallback_result()]
    elif mutation == "rank":
        result_payloads = [_hybrid_result(rank=2)]
    elif mutation == "duplicate":
        result_payloads = [_hybrid_result(), _hybrid_result(rank=2)]
    else:
        identity_payload = _fallback_identity()
        context_payload = _context(fallback=True)
        result_payload = _fallback_result()
        result_payload["collaborative_weight_units"] = 100_000
        result_payloads = [result_payload]

    identity = Stage5RecommendationEventIdentity.model_validate(identity_payload)
    context = Stage5RecommendationEventContext.model_validate(context_payload)
    result = [Stage5RecommendationEventResultItem.model_validate(item) for item in result_payloads]

    with pytest.raises(ValueError):
        repository.add_stage_5(
            generation_id="3" * 32,
            user_id=42,
            identity=identity,
            context=context,
            result=result,
        )
    session.add.assert_not_called()


def test_stage_5_event_contract_forbids_raw_or_unbounded_payloads() -> None:
    identity = _hybrid_identity()
    identity["build_id"] = "internal-build"
    with pytest.raises(ValidationError):
        Stage5RecommendationEventIdentity.model_validate(identity)

    nested_identity = _hybrid_identity()
    collaborative_model = nested_identity["collaborative_model"]
    assert isinstance(collaborative_model, dict)
    collaborative_model["build_id"] = "internal-build"
    with pytest.raises(ValidationError):
        Stage5RecommendationEventIdentity.model_validate(nested_identity)

    context = _context()
    context["raw_interactions"] = [{"game_id": 7, "rating": 10}]
    with pytest.raises(ValidationError):
        Stage5RecommendationEventContext.model_validate(context)

    result = _hybrid_result()
    result["explanation"] = "unbounded prose"
    with pytest.raises(ValidationError):
        Stage5RecommendationEventResultItem.model_validate(result)

    with pytest.raises(ValueError, match="byte limit"):
        _validated_json("x" * MAX_EVENT_CONTEXT_BYTES, maximum_bytes=MAX_EVENT_CONTEXT_BYTES)
    with pytest.raises(ValueError, match="byte limit"):
        _validated_json("x" * MAX_EVENT_RESULT_BYTES, maximum_bytes=MAX_EVENT_RESULT_BYTES)


def test_stage_5_event_fixtures_are_not_mutated_by_validation() -> None:
    identity = _hybrid_identity()
    context = _context()
    result = _hybrid_result()
    originals = deepcopy((identity, context, result))

    Stage5RecommendationEventIdentity.model_validate(identity)
    Stage5RecommendationEventContext.model_validate(context)
    Stage5RecommendationEventResultItem.model_validate(result)

    assert (identity, context, result) == originals
