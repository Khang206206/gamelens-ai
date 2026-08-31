from collections.abc import Mapping
from dataclasses import dataclass

from gamelens_recommender import (
    HybridRecommendation,
    HybridRecommendationsResult,
    PersonalizedRecommendation,
    Stage4FallbackResult,
)

from app.schemas.games import GameSummary
from app.schemas.personalized_recommendations import (
    SCORE_SCALE,
    CollaborativeModelIdentityResponse,
    CollaborativeSourceEdgeResponse,
    RecommendationEventContext,
    Stage5PersonalizedRecommendationItem,
    Stage5PersonalizedRecommendationResponse,
    Stage5PolicyIdentity,
    Stage5PositiveFeedbackSourceResponse,
    Stage5ScoreComponentResponse,
)
from app.schemas.recommendation_events import (
    MAX_EVENT_CONTEXT_BYTES,
    MAX_EVENT_RESULT_BYTES,
    Stage5RecommendationEventCollaborativeIdentity,
    Stage5RecommendationEventContext,
    Stage5RecommendationEventIdentity,
    Stage5RecommendationEventResultItem,
    validated_recommendation_event_json,
)
from app.schemas.recommendations import (
    EvidenceValue,
    RecommendationEvidenceResponse,
    RecommendationExplanationResponse,
    RecommendationModelIdentity,
    SimilarSelectedGameResponse,
)
from app.services.recommendation.decision import PersonalizedRankingDecision


@dataclass(frozen=True, slots=True)
class Stage5DecisionProjection:
    response: Stage5PersonalizedRecommendationResponse
    event_identity: Stage5RecommendationEventIdentity
    event_context: Stage5RecommendationEventContext
    event_result: tuple[Stage5RecommendationEventResultItem, ...]


def _score(units: int) -> float:
    return units / SCORE_SCALE


def _game_summary(value: object) -> GameSummary:
    return value if type(value) is GameSummary else GameSummary.model_validate(value)


def _evidence(
    item: HybridRecommendation | PersonalizedRecommendation,
) -> RecommendationEvidenceResponse:
    evidence = item.base_evidence
    return RecommendationEvidenceResponse(
        matching_genres=[
            EvidenceValue(slug=value.slug, name=value.name) for value in evidence.matching_genres
        ],
        matching_tags=[
            EvidenceValue(slug=value.slug, name=value.name) for value in evidence.matching_tags
        ],
        preferred_platforms=[
            EvidenceValue(slug=value.slug, name=value.name)
            for value in evidence.preferred_platforms
        ],
        similar_selected_games=[
            SimilarSelectedGameResponse(
                slug=value.slug,
                title=value.title,
                similarity_score=_score(value.similarity_units),
            )
            for value in evidence.similar_selected_games
        ],
        popularity_score=_score(evidence.popularity_percentile_units),
    )


def _project_item(
    item: HybridRecommendation | PersonalizedRecommendation,
    *,
    game: object,
) -> tuple[Stage5PersonalizedRecommendationItem, Stage5RecommendationEventResultItem]:
    is_hybrid = type(item) is HybridRecommendation
    if is_hybrid:
        hybrid_item = item
        candidate_origin = hybrid_item.candidate_origin
        collaborative_supported = hybrid_item.collaborative_supported
        collaborative_score_units = hybrid_item.collaborative_score_units
        collaborative_weight_units = hybrid_item.collaborative_weight_units
        collaborative_contribution_units = hybrid_item.collaborative_contribution_units
        collaborative_item_support = hybrid_item.collaborative_item_support
        collaborative_source_edges = hybrid_item.collaborative_source_edges
    else:
        candidate_origin = "content"
        collaborative_supported = False
        collaborative_score_units = 0
        collaborative_weight_units = 0
        collaborative_contribution_units = 0
        collaborative_item_support = None
        collaborative_source_edges = ()

    response_item = Stage5PersonalizedRecommendationItem(
        rank=item.rank,
        game=_game_summary(game),
        base_ranking_score=_score(item.base_score_units),
        base_components=[
            Stage5ScoreComponentResponse(
                name=component.name,
                raw_score=_score(component.raw_units),
                weight=_score(component.weight_units),
                contribution=_score(component.contribution_units),
            )
            for component in item.base_components
        ],
        base_weight=_score(item.base_weight_units),
        base_contribution=_score(item.base_contribution_units),
        feedback_affinity_score=_score(item.affinity_score_units),
        feedback_affinity_weight=_score(item.affinity_weight_units),
        feedback_affinity_contribution=_score(item.affinity_contribution_units),
        candidate_origin=candidate_origin,
        collaborative_supported=collaborative_supported,
        collaborative_score=_score(collaborative_score_units),
        collaborative_weight=_score(collaborative_weight_units),
        collaborative_contribution=_score(collaborative_contribution_units),
        collaborative_item_support=collaborative_item_support,
        collaborative_source_edges=[
            CollaborativeSourceEdgeResponse(
                source_game_slug=edge.source_slug,
                source_kind=edge.source_kind,
                similarity_score=_score(edge.similarity_units),
                pair_support=edge.pair_support,
            )
            for edge in collaborative_source_edges
        ],
        pre_played_score=_score(item.pre_played_score_units),
        played_factor=_score(item.played_factor_units),
        played_delta=_score(item.played_delta_units),
        ranking_score=_score(item.final_score_units),
        adjustment_reasons=list(item.adjustment_reasons),
        evidence=_evidence(item),
        explanation=RecommendationExplanationResponse(
            summary=item.explanation_summary,
            reasons=list(item.explanation_reasons),
        ),
    )
    event_item = Stage5RecommendationEventResultItem(
        slug=item.slug,
        rank=item.rank,
        candidate_origin=candidate_origin,
        base_units=item.base_score_units,
        base_weight_units=item.base_weight_units,
        base_contribution_units=item.base_contribution_units,
        affinity_units=item.affinity_score_units,
        affinity_weight_units=item.affinity_weight_units,
        affinity_contribution_units=item.affinity_contribution_units,
        collaborative_supported=collaborative_supported,
        collaborative_units=collaborative_score_units,
        collaborative_weight_units=collaborative_weight_units,
        collaborative_contribution_units=collaborative_contribution_units,
        collaborative_item_support=collaborative_item_support,
        collaborative_source_edge_count=len(collaborative_source_edges),
        pre_played_units=item.pre_played_score_units,
        played_factor_units=item.played_factor_units,
        played_delta_units=item.played_delta_units,
        final_units=item.final_score_units,
    )
    return response_item, event_item


def project_stage_5_decision(
    decision: PersonalizedRankingDecision,
    *,
    generation_id: str,
    content_model: RecommendationModelIdentity,
    games_by_slug: Mapping[str, object],
    event_context: RecommendationEventContext,
) -> Stage5DecisionProjection:
    """Project one validated ranking decision into matching public and audit contracts."""

    if type(decision) is not PersonalizedRankingDecision:
        raise TypeError("Stage 5 projection requires a personalized ranking decision")
    if type(content_model) is not RecommendationModelIdentity:
        raise TypeError("Stage 5 projection requires a content model identity")
    if type(event_context) is not RecommendationEventContext:
        raise TypeError("Stage 5 projection requires a recommendation event context")

    result = decision.result
    if type(result) is HybridRecommendationsResult:
        artifact = decision.collaborative_readiness.artifact
        if not decision.collaborative_readiness.usable or artifact is None:
            raise ValueError("Hybrid projection requires the exact usable collaborative artifact")
        items = result.items
        feedback_policy = result.feedback_policy
        positive_sources = result.positive_sources
        ranking_mode = "hybrid"
        fallback_reason = None
        hybrid_policy = Stage5PolicyIdentity(
            name=result.policy.name,
            version=result.policy.version,
        )
        collaborative_model = CollaborativeModelIdentityResponse(
            name=artifact.model_name,
            version=artifact.model_version,
            interaction_fingerprint=artifact.interaction_fingerprint,
            scoring_policy=Stage5PolicyIdentity(
                name=result.collaborative_policy.name,
                version=result.collaborative_policy.version,
            ),
        )
        event_collaborative_model = Stage5RecommendationEventCollaborativeIdentity(
            name=collaborative_model.name,
            version=collaborative_model.version,
            interaction_fingerprint=collaborative_model.interaction_fingerprint,
            scoring_policy=collaborative_model.scoring_policy,
        )
        response_reason = result.reason
    elif type(result) is Stage4FallbackResult:
        stage_4_result = result.stage_4_result
        items = stage_4_result.items
        feedback_policy = stage_4_result.policy
        positive_sources = stage_4_result.positive_sources
        ranking_mode = "stage_4_fallback"
        fallback_reason = result.fallback_reason
        hybrid_policy = None
        collaborative_model = None
        event_collaborative_model = None
        response_reason = stage_4_result.reason
    else:
        raise TypeError("Stage 5 projection received an unsupported ranking result")

    expected_positive_source_slugs = [source.game_slug for source in positive_sources]
    if (
        event_context.positive_source_slugs != expected_positive_source_slugs
        or event_context.positive_source_count != len(expected_positive_source_slugs)
    ):
        raise ValueError("Event context positive sources do not match the ranking decision")

    response_items: list[Stage5PersonalizedRecommendationItem] = []
    event_items: list[Stage5RecommendationEventResultItem] = []
    for item in items:
        try:
            game = games_by_slug[item.slug]
        except KeyError as error:
            raise ValueError(
                f"Recommendation game is missing from the catalog: {item.slug}"
            ) from error
        response_item, event_item = _project_item(item, game=game)
        response_items.append(response_item)
        event_items.append(event_item)

    policy = Stage5PolicyIdentity(name=feedback_policy.name, version=feedback_policy.version)
    response = Stage5PersonalizedRecommendationResponse(
        generation_id=generation_id,
        model_name=content_model.name,
        model_version=content_model.version,
        data_fingerprint=content_model.data_fingerprint,
        policy=policy,
        ranking_mode=ranking_mode,
        fallback_reason=fallback_reason,
        hybrid_policy=hybrid_policy,
        collaborative_model=collaborative_model,
        response_reason=response_reason,
        requested_top_k=event_context.top_k,
        positive_feedback_sources=[
            Stage5PositiveFeedbackSourceResponse(
                game_slug=source.game_slug,
                kind=source.kind,
            )
            for source in positive_sources
        ],
        items=response_items,
    )
    identity = Stage5RecommendationEventIdentity(
        content_model_name=content_model.name,
        content_model_version=content_model.version,
        content_data_fingerprint=content_model.data_fingerprint,
        feedback_policy=policy,
        ranking_mode=ranking_mode,
        fallback_reason=fallback_reason,
        hybrid_policy=hybrid_policy,
        collaborative_model=event_collaborative_model,
    )
    context = Stage5RecommendationEventContext(
        **event_context.model_dump(mode="python"),
        ranking_mode=ranking_mode,
        fallback_reason=fallback_reason,
    )
    event_result = tuple(event_items)
    validated_recommendation_event_json(
        context.model_dump(mode="json"),
        maximum_bytes=MAX_EVENT_CONTEXT_BYTES,
    )
    validated_recommendation_event_json(
        [item.model_dump(mode="json") for item in event_result],
        maximum_bytes=MAX_EVENT_RESULT_BYTES,
    )
    return Stage5DecisionProjection(
        response=response,
        event_identity=identity,
        event_context=context,
        event_result=event_result,
    )
