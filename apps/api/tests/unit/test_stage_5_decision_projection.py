import json
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from app.commands.collaborative_artifact import build_fixture_artifact
from app.commands.collaborative_snapshot import catalog_from_seed
from app.core.config import PROJECT_ROOT, Settings
from app.schemas.games import GameSummary
from app.schemas.personalized_recommendations import RecommendationEventContext
from app.schemas.recommendation_events import (
    MAX_EVENT_CONTEXT_BYTES,
    MAX_EVENT_RESULT_BYTES,
)
from app.schemas.recommendations import RecommendationModelIdentity
from app.services.recommendation import (
    CollaborativeReadiness,
    LifecycleAwareHybridOrchestrator,
    create_collaborative_component,
    evaluate_collaborative_readiness,
)
from app.services.recommendation.content import ContentRecommendationService
from app.services.recommendation.decision import PersonalizedRankingDecision
from app.services.recommendation.projection import (
    SCORE_SCALE,
    Stage5DecisionProjection,
    project_stage_5_decision,
)
from gamelens_recommender import (
    HYBRID_FALLBACK_REASONS,
    ActiveGameFeedback,
    HybridRecommendationsResult,
    PersonalizedRankingResult,
    Stage4FallbackResult,
    UserContext,
    build_artifact,
    load_artifact,
)
from pydantic import ValidationError

CATALOG_PATH = PROJECT_ROOT / "data" / "catalog" / "games.json"
FIXTURE_PATH = (
    PROJECT_ROOT / "data" / "fixtures" / "interactions" / "collaborative-interactions.json"
)
BUILT_AT = datetime(2026, 8, 25, tzinfo=UTC)
FEEDBACK_AT = datetime(2026, 8, 24, tzinfo=UTC)


class _CountingOrchestrator:
    def __init__(self, delegate: LifecycleAwareHybridOrchestrator) -> None:
        self.delegate = delegate
        self.call_count = 0

    def rank(self, **kwargs):  # type: ignore[no-untyped-def]
        self.call_count += 1
        return self.delegate.rank(**kwargs)


@dataclass(frozen=True, slots=True)
class _ProjectionFixture:
    decision: PersonalizedRankingDecision
    legacy_result: PersonalizedRankingResult
    readiness: CollaborativeReadiness
    games_by_slug: dict[str, GameSummary]
    content_model: RecommendationModelIdentity
    event_context: RecommendationEventContext
    hybrid_rank_calls: int


def _game(slug: str, game_id: int) -> GameSummary:
    return GameSummary(
        id=game_id,
        title=slug.replace("-", " ").title(),
        slug=slug,
        release_date=None,
        developer="Fixture Studio",
        publisher=None,
        average_rating=8.0,
        rating_count=100,
        popularity_score=50.0,
        genres=[],
        tags=[],
        platforms=[],
        cover_image_url=None,
    )


def _event_context(
    decision: PersonalizedRankingDecision | None,
    *,
    top_k: int = 20,
    selected_game_slugs: list[str] | None = None,
) -> RecommendationEventContext:
    positive_sources = (
        []
        if decision is None
        else [source.game_slug for source in decision.result.positive_sources]
    )
    return RecommendationEventContext(
        top_k=top_k,
        selected_game_slugs=(
            ["emberfall-tactics"] if selected_game_slugs is None else selected_game_slugs
        ),
        preferred_genres=["strategy"],
        preferred_tags=[],
        preferred_platforms=["windows"],
        positive_source_slugs=positive_sources,
        disliked_count=0,
        played_count=0,
        positive_source_count=len(positive_sources),
        effective_state_fingerprint="c" * 64,
    )


@pytest.fixture(scope="module")
def projection_fixture(tmp_path_factory: pytest.TempPathFactory) -> _ProjectionFixture:
    root = tmp_path_factory.mktemp("stage-5-decision-projection")
    snapshot = catalog_from_seed(CATALOG_PATH)
    content_root = build_artifact(snapshot, root / "content", built_at=BUILT_AT)
    content = ContentRecommendationService(load_artifact(content_root))
    collaborative_root = root / "collaborative"
    settings = Settings(
        _env_file=None,
        environment="test",
        collaborative_allow_test_fixture=True,
    )
    build_fixture_artifact(
        settings,
        collaborative_root,
        fixture_path=FIXTURE_PATH,
        catalog_path=CATALOG_PATH,
        built_at=BUILT_AT,
    )
    component = create_collaborative_component(
        collaborative_root,
        environment="test",
        allow_test_fixture=True,
    )
    readiness = evaluate_collaborative_readiness(
        component,
        catalog_fingerprint=snapshot.fingerprint,
        current_consent_version=None,
        now=BUILT_AT,
    )
    context = UserContext(
        preferred_genres=("strategy",),
        preferred_platforms=("windows",),
        top_k=20,
    )
    feedback = (
        ActiveGameFeedback(
            game_slug="emberfall-tactics",
            reaction="liked",
            reaction_occurred_at=FEEDBACK_AT,
        ),
    )
    orchestrator = _CountingOrchestrator(LifecycleAwareHybridOrchestrator(content))
    result = orchestrator.rank(
        snapshot=snapshot,
        context=context,
        feedback=feedback,
        collaborative_readiness=readiness,
    )
    assert type(result) is HybridRecommendationsResult
    legacy_result = content.recommend_personalized(
        snapshot=snapshot,
        context=context,
        feedback=feedback,
    )
    decision = PersonalizedRankingDecision(
        result=result,
        collaborative_readiness=readiness,
        legacy_stage_4_result=legacy_result,
    )
    games_by_slug = {
        item.slug: _game(item.slug, game_id) for game_id, item in enumerate(result.items, start=1)
    }
    active = content.status(snapshot).active_model
    assert active is not None
    content_model = RecommendationModelIdentity(
        name=active.name,
        version=active.version,
        data_fingerprint=active.data_fingerprint,
    )
    return _ProjectionFixture(
        decision=decision,
        legacy_result=legacy_result,
        readiness=readiness,
        games_by_slug=games_by_slug,
        content_model=content_model,
        event_context=_event_context(decision),
        hybrid_rank_calls=orchestrator.call_count,
    )


def _project(
    fixture: _ProjectionFixture,
    *,
    decision: PersonalizedRankingDecision | None = None,
    event_context: RecommendationEventContext | None = None,
) -> Stage5DecisionProjection:
    return project_stage_5_decision(
        fixture.decision if decision is None else decision,
        generation_id="1" * 32,
        content_model=fixture.content_model,
        games_by_slug=fixture.games_by_slug,
        event_context=fixture.event_context if event_context is None else event_context,
    )


def _units(value: float) -> int:
    return round(value * SCORE_SCALE)


def _assert_response_event_equality(projection: Stage5DecisionProjection) -> None:
    response = projection.response
    assert response.ranking_mode == projection.event_identity.ranking_mode
    assert response.fallback_reason == projection.event_identity.fallback_reason
    assert response.ranking_mode == projection.event_context.ranking_mode
    assert response.fallback_reason == projection.event_context.fallback_reason
    assert response.policy.model_dump() == projection.event_identity.feedback_policy.model_dump()
    assert (None if response.hybrid_policy is None else response.hybrid_policy.model_dump()) == (
        None
        if projection.event_identity.hybrid_policy is None
        else projection.event_identity.hybrid_policy.model_dump()
    )
    assert (
        None if response.collaborative_model is None else response.collaborative_model.model_dump()
    ) == (
        None
        if projection.event_identity.collaborative_model is None
        else projection.event_identity.collaborative_model.model_dump()
    )
    assert len(response.items) == len(projection.event_result)
    for response_item, event_item in zip(
        response.items,
        projection.event_result,
        strict=True,
    ):
        assert response_item.game.slug == event_item.slug
        assert response_item.rank == event_item.rank
        assert response_item.candidate_origin == event_item.candidate_origin
        assert _units(response_item.base_ranking_score) == event_item.base_units
        assert _units(response_item.base_weight) == event_item.base_weight_units
        assert _units(response_item.base_contribution) == event_item.base_contribution_units
        assert _units(response_item.feedback_affinity_score) == event_item.affinity_units
        assert _units(response_item.feedback_affinity_weight) == event_item.affinity_weight_units
        assert (
            _units(response_item.feedback_affinity_contribution)
            == event_item.affinity_contribution_units
        )
        assert response_item.collaborative_supported == event_item.collaborative_supported
        assert _units(response_item.collaborative_score) == event_item.collaborative_units
        assert _units(response_item.collaborative_weight) == event_item.collaborative_weight_units
        assert (
            _units(response_item.collaborative_contribution)
            == event_item.collaborative_contribution_units
        )
        assert response_item.collaborative_item_support == event_item.collaborative_item_support
        assert (
            len(response_item.collaborative_source_edges)
            == event_item.collaborative_source_edge_count
        )
        assert _units(response_item.pre_played_score) == event_item.pre_played_units
        assert _units(response_item.played_factor) == event_item.played_factor_units
        assert _units(response_item.played_delta) == event_item.played_delta_units
        assert _units(response_item.ranking_score) == event_item.final_units
        assert event_item.pre_played_units == (
            event_item.base_contribution_units
            + event_item.affinity_contribution_units
            + event_item.collaborative_contribution_units
        )
        assert (
            event_item.final_units
            == (event_item.pre_played_units * event_item.played_factor_units + SCORE_SCALE // 2)
            // SCORE_SCALE
        )


def _unavailable_readiness(reason: str) -> CollaborativeReadiness:
    if reason == "not_configured":
        state = "not_configured"
        source_kind = None
    elif reason == "insufficient_data":
        state = "insufficient_data"
        source_kind = "fixture"
    elif reason in {"fixture_not_allowed", "artifact_missing", "artifact_corrupt"}:
        state = "unavailable"
        source_kind = None
    else:
        state = "stale"
        source_kind = "live"
    return CollaborativeReadiness(
        state=state,  # type: ignore[arg-type]
        reason=reason,  # type: ignore[arg-type]
        source_kind=source_kind,  # type: ignore[arg-type]
        artifact=None,
    )


def test_real_hybrid_decision_projects_once_into_equal_deterministic_contracts(
    projection_fixture: _ProjectionFixture,
) -> None:
    first = _project(projection_fixture)
    second = _project(projection_fixture)

    assert projection_fixture.hybrid_rank_calls == 1
    assert first == second
    assert first.response.ranking_mode == "hybrid"
    assert any(item.collaborative_supported for item in first.response.items)
    assert len(first.response.items) <= first.response.requested_top_k
    assert [item.rank for item in first.response.items] == list(
        range(1, len(first.response.items) + 1)
    )
    _assert_response_event_equality(first)

    context_json = first.event_context.model_dump(mode="json")
    result_json = [item.model_dump(mode="json") for item in first.event_result]
    assert len(json.dumps(context_json, ensure_ascii=False).encode()) <= MAX_EVENT_CONTEXT_BYTES
    assert len(json.dumps(result_json, ensure_ascii=False).encode()) <= MAX_EVENT_RESULT_BYTES


@pytest.mark.parametrize("fallback_reason", HYBRID_FALLBACK_REASONS)
def test_every_fallback_projects_the_exact_stage_4_records_without_identity_leakage(
    projection_fixture: _ProjectionFixture,
    fallback_reason: str,
) -> None:
    result = Stage4FallbackResult(
        mode="stage_4_fallback",
        fallback_reason=fallback_reason,  # type: ignore[arg-type]
        stage_4_result=projection_fixture.legacy_result,
    )
    readiness = (
        projection_fixture.readiness
        if fallback_reason.startswith("no_")
        else _unavailable_readiness(fallback_reason)
    )
    decision = PersonalizedRankingDecision(
        result=result,
        collaborative_readiness=readiness,
        legacy_stage_4_result=projection_fixture.legacy_result,
    )
    games = {
        item.slug: _game(item.slug, game_id)
        for game_id, item in enumerate(result.stage_4_result.items, start=1)
    }
    projection = project_stage_5_decision(
        decision,
        generation_id="2" * 32,
        content_model=projection_fixture.content_model,
        games_by_slug=games,
        event_context=projection_fixture.event_context,
    )

    assert projection.response.ranking_mode == "stage_4_fallback"
    assert projection.response.fallback_reason == fallback_reason
    assert projection.response.hybrid_policy is None
    assert projection.response.collaborative_model is None
    assert projection.event_identity.hybrid_policy is None
    assert projection.event_identity.collaborative_model is None
    assert all(item.candidate_origin == "content" for item in projection.response.items)
    assert all(item.collaborative_weight == 0 for item in projection.response.items)
    assert all(item.collaborative_weight_units == 0 for item in projection.event_result)
    _assert_response_event_equality(projection)


def test_projection_enforces_top_k_and_compact_json_bounds(
    projection_fixture: _ProjectionFixture,
) -> None:
    too_small = projection_fixture.event_context.model_copy(update={"top_k": 1})
    with pytest.raises(ValidationError):
        _project(projection_fixture, event_context=too_small)

    long_slugs = [f"{'a' * 218}{index:02}" for index in range(25)]
    oversized = projection_fixture.event_context.model_copy(
        update={
            "selected_game_slugs": long_slugs,
            "preferred_genres": long_slugs[:20],
            "preferred_tags": long_slugs,
            "preferred_platforms": long_slugs[:10],
        }
    )
    with pytest.raises(
        ValueError,
        match="Recommendation event payload exceeds its byte limit",
    ):
        _project(projection_fixture, event_context=oversized)


def test_projection_rejects_context_sources_from_a_different_decision(
    projection_fixture: _ProjectionFixture,
) -> None:
    mismatched = projection_fixture.event_context.model_copy(
        update={
            "positive_source_slugs": [],
            "positive_source_count": 0,
        }
    )

    with pytest.raises(
        ValueError,
        match="Event context positive sources do not match the ranking decision",
    ):
        _project(projection_fixture, event_context=mismatched)
