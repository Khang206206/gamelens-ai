from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest

import gamelens_recommender
from gamelens_recommender import (
    ActiveGameFeedback,
    CollaborativeScoringDiagnostics,
    CollaborativeScoringResult,
    CollaborativeSourceEdge,
    FeedbackPolicyIdentity,
    FeedbackRanker,
    PositiveFeedbackSource,
    UserContext,
    build_artifact,
    load_artifact,
)
from gamelens_recommender.collaborative import COLLABORATIVE_SCORING_CONFIG
from gamelens_recommender.hybrid import (
    COLLABORATIVE_NO_SUPPORT_REASONS,
    COLLABORATIVE_UNAVAILABLE_REASONS,
    HYBRID_CANDIDATE_ORIGINS,
    HYBRID_FALLBACK_REASONS,
    HYBRID_POLICY_CONFIG,
    HYBRID_RANKING_MODES,
    CollaborativeComponentReady,
    CollaborativeComponentUnavailable,
    HybridContractError,
    HybridPolicyConfig,
    HybridPolicyIdentity,
    HybridRecommendation,
    HybridRecommendationsResult,
    Stage4FallbackResult,
    validate_collaborative_component_outcome,
    validate_hybrid_ranking_result,
)
from gamelens_recommender.schemas import RecommendationEvidence, ScoreComponent

NOW = datetime(2026, 8, 28, tzinfo=UTC)


def _ranker(snapshot, tmp_path) -> FeedbackRanker:
    return FeedbackRanker(load_artifact(build_artifact(snapshot, tmp_path / "model")))


def _liked(slug: str) -> ActiveGameFeedback:
    return ActiveGameFeedback(
        game_slug=slug,
        reaction="liked",
        reaction_occurred_at=NOW,
    )


def _disliked(slug: str) -> ActiveGameFeedback:
    return ActiveGameFeedback(
        game_slug=slug,
        reaction="disliked",
        reaction_occurred_at=NOW,
    )


def _stage_4_signature(result):
    return (
        result.reason,
        tuple((source.game_slug, source.kind) for source in result.positive_sources),
        tuple(
            (
                item.slug,
                item.rank,
                item.base_score_units,
                item.base_weight_units,
                item.base_contribution_units,
                item.affinity_score_units,
                item.affinity_weight_units,
                item.affinity_contribution_units,
                item.pre_played_score_units,
                item.played_factor_units,
                item.played_delta_units,
                item.final_score_units,
                item.adjustment_reasons,
            )
            for item in result.items
        ),
    )


def _with_rank(signature, rank: int):
    return (signature[0], rank, *signature[2:])


def test_phase4_hybrid_policy_contract_is_frozen() -> None:
    HYBRID_POLICY_CONFIG.validate()

    assert HYBRID_POLICY_CONFIG.identity == HybridPolicyIdentity(
        name="gamelens-hybrid-ranking",
        version="1.0.0",
    )
    assert (
        HYBRID_POLICY_CONFIG.base_weight_units_with_affinity,
        HYBRID_POLICY_CONFIG.affinity_weight_units,
        HYBRID_POLICY_CONFIG.collaborative_weight_units,
    ) == (800_000, 100_000, 100_000)
    assert (
        HYBRID_POLICY_CONFIG.base_weight_units_without_affinity,
        HYBRID_POLICY_CONFIG.collaborative_weight_units,
    ) == (900_000, 100_000)
    assert HYBRID_POLICY_CONFIG.played_factor_units == 500_000
    assert HYBRID_RANKING_MODES == ("hybrid", "stage_4_fallback")
    assert HYBRID_CANDIDATE_ORIGINS == ("content", "collaborative", "both")
    assert HYBRID_POLICY_CONFIG.tie_break == (
        "final_score_desc",
        "pre_played_score_desc",
        "base_contribution_desc",
        "collaborative_contribution_desc",
        "affinity_contribution_desc",
        "content_score_desc",
        "popularity_score_desc",
        "slug_asc",
    )


def test_phase4_contracts_remain_internal_until_the_public_ranker_exists() -> None:
    assert {
        "CollaborativeComponentOutcome",
        "HybridPolicyConfig",
        "HybridPolicyIdentity",
        "HybridRankingResult",
        "HybridRecommendation",
        "HybridRecommendationsResult",
        "Stage4FallbackResult",
    }.isdisjoint(gamelens_recommender.__all__)


def test_phase4_fallback_taxonomy_is_bounded_and_disjoint() -> None:
    assert COLLABORATIVE_UNAVAILABLE_REASONS == (
        "not_configured",
        "fixture_not_allowed",
        "insufficient_data",
        "artifact_missing",
        "artifact_corrupt",
        "artifact_incompatible",
        "artifact_stale",
        "privacy_invalid",
        "artifact_expired",
        "catalog_stale",
        "artifact_retired",
    )
    assert COLLABORATIVE_NO_SUPPORT_REASONS == (
        "no_query_sources",
        "no_supported_sources",
        "no_candidate_edges",
        "no_eligible_candidates",
    )
    assert not set(COLLABORATIVE_UNAVAILABLE_REASONS) & set(COLLABORATIVE_NO_SUPPORT_REASONS)
    assert (
        *COLLABORATIVE_UNAVAILABLE_REASONS,
        *COLLABORATIVE_NO_SUPPORT_REASONS,
    ) == HYBRID_FALLBACK_REASONS


@pytest.mark.parametrize(
    "config",
    [
        replace(HybridPolicyConfig(), name="other-policy"),
        replace(HybridPolicyConfig(), version="2.0.0"),
        replace(HybridPolicyConfig(), score_scale=True),
        replace(HybridPolicyConfig(), affinity_weight_units=99_999),
        replace(HybridPolicyConfig(), collaborative_weight_units=99_999),
        replace(HybridPolicyConfig(), base_weight_units_with_affinity=799_999),
        replace(HybridPolicyConfig(), base_weight_units_without_affinity=899_999),
        replace(HybridPolicyConfig(), played_factor_units=499_999),
        replace(HybridPolicyConfig(), ranking_modes=("hybrid",)),
        replace(HybridPolicyConfig(), candidate_origins=("content",)),
        replace(HybridPolicyConfig(), fallback_reasons=("not_configured",)),
        replace(HybridPolicyConfig(), tie_break=("slug_asc",)),
    ],
)
def test_phase4_hybrid_policy_rejects_version_drift(config) -> None:
    with pytest.raises(HybridContractError) as captured:
        config.validate()

    assert captured.value.code == "hybrid_config_invalid"


def test_phase4_component_outcome_contract_is_immutable_and_typed() -> None:
    outcome = CollaborativeComponentUnavailable(reason="not_configured")
    validate_collaborative_component_outcome(outcome)

    with pytest.raises(FrozenInstanceError):
        outcome.reason = "artifact_missing"
    with pytest.raises(HybridContractError) as captured:
        validate_collaborative_component_outcome(
            CollaborativeComponentUnavailable(reason="unknown")  # type: ignore[arg-type]
        )

    assert captured.value.code == "hybrid_input_invalid"


def test_phase4_ready_component_requires_a_valid_scoring_result() -> None:
    diagnostics = CollaborativeScoringDiagnostics(0, 0, 0, 0, 0, 0, 0, 0, 0)
    scoring_result = CollaborativeScoringResult(
        reason="no_query_sources",
        identity=COLLABORATIVE_SCORING_CONFIG.identity,
        query_sources=(),
        supported_source_slugs=(),
        unsupported_source_slugs=(),
        candidates=(),
        diagnostics=diagnostics,
    )
    outcome = CollaborativeComponentReady(scoring_result=scoring_result)

    validate_collaborative_component_outcome(outcome)

    with pytest.raises(FrozenInstanceError):
        outcome.scoring_result = scoring_result
    with pytest.raises(HybridContractError) as captured:
        validate_collaborative_component_outcome(
            CollaborativeComponentReady(scoring_result=object())  # type: ignore[arg-type]
        )

    assert captured.value.code == "hybrid_input_invalid"


def test_phase4_stage4_fallback_contract_preserves_the_original_payload(
    snapshot,
    tmp_path,
) -> None:
    stage_4 = _ranker(snapshot, tmp_path).rank(
        UserContext(preferred_genres=("strategy",), top_k=3),
        (_liked("gamma-drift"),),
    )
    fallback = Stage4FallbackResult(
        mode="stage_4_fallback",
        fallback_reason="no_candidate_edges",
        stage_4_result=stage_4,
    )

    validate_hybrid_ranking_result(fallback)

    assert fallback.stage_4_result is stage_4
    assert not hasattr(fallback, "policy")
    assert not hasattr(fallback, "items")
    with pytest.raises(FrozenInstanceError):
        fallback.fallback_reason = "artifact_missing"
    for invalid in (
        replace(fallback, mode="hybrid"),
        replace(fallback, fallback_reason="unknown"),
        replace(fallback, stage_4_result=object()),
    ):
        with pytest.raises(HybridContractError) as captured:
            validate_hybrid_ranking_result(invalid)  # type: ignore[arg-type]
        assert captured.value.code == "hybrid_result_invalid"


def test_phase4_hybrid_result_contract_is_additive_and_immutable() -> None:
    edge = CollaborativeSourceEdge(
        source_slug="source-game",
        source_kind="liked",
        candidate_slug="candidate-game",
        similarity_units=400_000,
        pair_support=2,
    )
    item = HybridRecommendation(
        slug="candidate-game",
        rank=1,
        candidate_origin="both",
        base_score_units=500_000,
        base_components=(
            ScoreComponent("content", 500_000, 800_000, 400_000),
            ScoreComponent("platform", 0, 100_000, 0),
            ScoreComponent("popularity", 1_000_000, 100_000, 100_000),
        ),
        base_evidence=RecommendationEvidence((), (), (), (), 1_000_000),
        base_weight_units=800_000,
        base_contribution_units=400_000,
        affinity_score_units=200_000,
        affinity_weight_units=100_000,
        affinity_contribution_units=20_000,
        collaborative_supported=True,
        collaborative_score_units=400_000,
        collaborative_weight_units=100_000,
        collaborative_contribution_units=40_000,
        collaborative_item_support=3,
        collaborative_source_edges=(edge,),
        pre_played_score_units=460_000,
        played_factor_units=1_000_000,
        played_delta_units=0,
        final_score_units=460_000,
        explanation_summary="Structured evidence supports this candidate.",
        explanation_reasons=("Structured evidence supports this candidate.",),
        adjustment_reasons=("feedback_affinity", "collaborative_similarity"),
    )
    diagnostics = CollaborativeScoringDiagnostics(1, 1, 0, 0, 1, 1, 0, 0, 1)
    result = HybridRecommendationsResult(
        mode="hybrid",
        items=(item,),
        reason="recommendations",
        policy=HYBRID_POLICY_CONFIG.identity,
        feedback_policy=FeedbackPolicyIdentity("gamelens-feedback-adjustment", "1.0.0"),
        collaborative_policy=COLLABORATIVE_SCORING_CONFIG.identity,
        collaborative_diagnostics=diagnostics,
        positive_sources=(PositiveFeedbackSource("source-game", "liked", NOW),),
    )

    validate_hybrid_ranking_result(result)

    assert not hasattr(result, "fallback_reason")
    assert result.items[0].collaborative_source_edges == (edge,)
    content_only = replace(
        item,
        slug="content-candidate",
        rank=2,
        candidate_origin="content",
        collaborative_supported=False,
        collaborative_score_units=0,
        collaborative_contribution_units=0,
        collaborative_item_support=None,
        collaborative_source_edges=(),
        pre_played_score_units=420_000,
        final_score_units=420_000,
        adjustment_reasons=("feedback_affinity",),
    )
    expanded = replace(result, items=(item, content_only))
    validate_hybrid_ranking_result(expanded)
    assert len(expanded.items) > expanded.collaborative_diagnostics.returned_candidate_count

    with pytest.raises(FrozenInstanceError):
        item.rank = 2
    with pytest.raises(HybridContractError) as captured:
        validate_hybrid_ranking_result(replace(result, mode="stage_4_fallback"))

    assert captured.value.code == "hybrid_result_invalid"
    for invalid_item in (
        replace(item, base_contribution_units=399_999),
        replace(item, collaborative_contribution_units=39_999),
        replace(item, pre_played_score_units=459_999),
        replace(item, final_score_units=459_999),
        replace(item, adjustment_reasons=("feedback_affinity",)),
    ):
        with pytest.raises(HybridContractError) as captured:
            validate_hybrid_ranking_result(replace(result, items=(invalid_item,)))
        assert captured.value.code == "hybrid_result_invalid"


def test_phase4_stage4_branch_characterization_matrix(snapshot, tmp_path) -> None:
    ranker = _ranker(snapshot, tmp_path)
    context = UserContext(preferred_genres=("strategy",), top_k=4)
    cases = {
        "no_feedback": (),
        "affinity": (_liked("gamma-drift"),),
        "affinity_and_played": (
            _liked("gamma-drift"),
            ActiveGameFeedback(game_slug="alpha-tactics", played=True),
        ),
        "wishlist_neutral": (ActiveGameFeedback(game_slug="beta-kingdom", wishlisted=True),),
        "dislike_exclusion": (_disliked("beta-kingdom"),),
    }

    signatures = {
        name: _stage_4_signature(ranker.rank(context, feedback)) for name, feedback in cases.items()
    }

    baseline = (
        "recommendations",
        (),
        (
            (
                "beta-kingdom",
                1,
                263_230,
                1_000_000,
                263_230,
                0,
                0,
                0,
                263_230,
                1_000_000,
                0,
                263_230,
                (),
            ),
            (
                "alpha-tactics",
                2,
                258_320,
                1_000_000,
                258_320,
                0,
                0,
                0,
                258_320,
                1_000_000,
                0,
                258_320,
                (),
            ),
            (
                "delta-command",
                3,
                257_370,
                1_000_000,
                257_370,
                0,
                0,
                0,
                257_370,
                1_000_000,
                0,
                257_370,
                (),
            ),
        ),
    )
    affinity = (
        "recommendations",
        (("gamma-drift", "liked"),),
        (
            (
                "beta-kingdom",
                1,
                263_230,
                900_000,
                236_907,
                36_098,
                100_000,
                3_610,
                240_517,
                1_000_000,
                0,
                240_517,
                ("feedback_affinity",),
            ),
            (
                "alpha-tactics",
                2,
                258_320,
                900_000,
                232_488,
                38_481,
                100_000,
                3_848,
                236_336,
                1_000_000,
                0,
                236_336,
                ("feedback_affinity",),
            ),
            (
                "delta-command",
                3,
                257_370,
                900_000,
                231_633,
                24_832,
                100_000,
                2_483,
                234_116,
                1_000_000,
                0,
                234_116,
                ("feedback_affinity",),
            ),
        ),
    )
    affinity_and_played = (
        "recommendations",
        (("gamma-drift", "liked"),),
        (
            affinity[2][0],
            _with_rank(affinity[2][2], 2),
            (
                "alpha-tactics",
                3,
                258_320,
                900_000,
                232_488,
                38_481,
                100_000,
                3_848,
                236_336,
                500_000,
                -118_168,
                118_168,
                ("feedback_affinity", "played_adjustment"),
            ),
        ),
    )
    dislike_exclusion = (
        "recommendations",
        (),
        (
            _with_rank(baseline[2][1], 1),
            _with_rank(baseline[2][2], 2),
        ),
    )

    assert signatures == {
        "no_feedback": baseline,
        "affinity": affinity,
        "affinity_and_played": affinity_and_played,
        "wishlist_neutral": baseline,
        "dislike_exclusion": dislike_exclusion,
    }
