from dataclasses import replace
from datetime import UTC, datetime

import pytest

from gamelens_recommender import (
    COLLABORATIVE_NO_SUPPORT_REASONS,
    COLLABORATIVE_UNAVAILABLE_REASONS,
    HYBRID_POLICY_CONFIG,
    ActiveGameFeedback,
    CollaborativeCandidateScore,
    CollaborativeComponentReady,
    CollaborativeComponentUnavailable,
    CollaborativeScoringDiagnostics,
    CollaborativeScoringResult,
    CollaborativeSourceEdge,
    FeedbackRanker,
    HybridContractError,
    HybridPolicyConfig,
    HybridRanker,
    HybridRecommendationsResult,
    Stage4FallbackResult,
    UserContext,
    build_artifact,
    load_artifact,
)
from gamelens_recommender.collaborative import COLLABORATIVE_SCORING_CONFIG

NOW = datetime(2026, 8, 29, tzinfo=UTC)


def _feedback_ranker(snapshot, tmp_path) -> FeedbackRanker:
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


def _collaborative_recommendations(
    prepared,
    candidates: tuple[tuple[str, int], ...],
) -> CollaborativeScoringResult:
    query_sources = prepared.collaborative_query_context.sources
    assert query_sources
    source = query_sources[0]
    scored = tuple(
        sorted(
            (
                CollaborativeCandidateScore(
                    slug=slug,
                    collaborative_score_units=score_units,
                    item_support=3,
                    source_edges=(
                        CollaborativeSourceEdge(
                            source_slug=source.game_slug,
                            source_kind=source.kind,
                            candidate_slug=slug,
                            similarity_units=score_units,
                            pair_support=2,
                        ),
                    ),
                )
                for slug, score_units in candidates
            ),
            key=lambda candidate: (-candidate.collaborative_score_units, candidate.slug),
        )
    )
    result = CollaborativeScoringResult(
        reason="recommendations",
        identity=COLLABORATIVE_SCORING_CONFIG.identity,
        query_sources=query_sources,
        supported_source_slugs=(source.game_slug,),
        unsupported_source_slugs=tuple(
            value.game_slug for value in query_sources if value.game_slug != source.game_slug
        ),
        candidates=scored,
        diagnostics=CollaborativeScoringDiagnostics(
            query_source_count=len(query_sources),
            supported_source_count=1,
            unsupported_source_count=len(query_sources) - 1,
            zero_degree_source_count=0,
            visited_edge_count=len(scored),
            candidate_count_before_exclusions=len(scored),
            query_source_exclusion_count=0,
            dislike_exclusion_count=0,
            returned_candidate_count=len(scored),
        ),
    )
    result.validate()
    return result


def _no_support_result(prepared, reason: str) -> CollaborativeScoringResult:
    query_sources = prepared.collaborative_query_context.sources
    if reason == "no_query_sources":
        supported: tuple[str, ...] = ()
        unsupported: tuple[str, ...] = ()
        diagnostics = CollaborativeScoringDiagnostics(0, 0, 0, 0, 0, 0, 0, 0, 0)
    elif reason == "no_supported_sources":
        supported = ()
        unsupported = tuple(source.game_slug for source in query_sources)
        diagnostics = CollaborativeScoringDiagnostics(
            len(query_sources),
            0,
            len(query_sources),
            0,
            0,
            0,
            0,
            0,
            0,
        )
    elif reason == "no_candidate_edges":
        supported = (query_sources[0].game_slug,)
        unsupported = tuple(source.game_slug for source in query_sources[1:])
        diagnostics = CollaborativeScoringDiagnostics(
            len(query_sources),
            1,
            len(query_sources) - 1,
            1,
            0,
            0,
            0,
            0,
            0,
        )
    else:
        assert reason == "no_eligible_candidates"
        supported = (query_sources[0].game_slug,)
        unsupported = tuple(source.game_slug for source in query_sources[1:])
        diagnostics = CollaborativeScoringDiagnostics(
            len(query_sources),
            1,
            len(query_sources) - 1,
            0,
            1,
            1,
            1,
            0,
            0,
        )
    result = CollaborativeScoringResult(
        reason=reason,  # type: ignore[arg-type]
        identity=COLLABORATIVE_SCORING_CONFIG.identity,
        query_sources=query_sources,
        supported_source_slugs=supported,
        unsupported_source_slugs=unsupported,
        candidates=(),
        diagnostics=diagnostics,
    )
    result.validate()
    return result


def test_hybrid_ranker_exposes_frozen_policy_identity(snapshot, tmp_path) -> None:
    feedback_ranker = _feedback_ranker(snapshot, tmp_path)
    ranker = HybridRanker(feedback_ranker)

    assert ranker.feedback_ranker is feedback_ranker
    assert ranker.config is HYBRID_POLICY_CONFIG
    assert ranker.identity == HYBRID_POLICY_CONFIG.identity
    with pytest.raises(HybridContractError) as captured:
        HybridRanker(object())  # type: ignore[arg-type]
    assert captured.value.code == "hybrid_input_invalid"
    with pytest.raises(HybridContractError) as captured:
        HybridRanker(
            feedback_ranker,
            replace(HybridPolicyConfig(), version="2.0.0"),
        )
    assert captured.value.code == "hybrid_config_invalid"


@pytest.mark.parametrize("reason", COLLABORATIVE_UNAVAILABLE_REASONS)
def test_every_unavailable_reason_returns_the_exact_stage4_payload(
    snapshot,
    tmp_path,
    monkeypatch,
    reason,
) -> None:
    feedback_ranker = _feedback_ranker(snapshot, tmp_path)
    context = UserContext(preferred_genres=("strategy",), top_k=3)
    feedback = (_liked("gamma-drift"),)
    original_rank = feedback_ranker.rank
    expected = original_rank(context, feedback)
    returned = []

    def tracked_stage4_rank(actual_context, actual_feedback):
        result = original_rank(actual_context, actual_feedback)
        returned.append(result)
        return result

    monkeypatch.setattr(feedback_ranker, "rank", tracked_stage4_rank)

    result = HybridRanker(feedback_ranker).rank(
        context,
        feedback,
        CollaborativeComponentUnavailable(reason=reason),
    )

    assert type(result) is Stage4FallbackResult
    assert result.mode == "stage_4_fallback"
    assert result.fallback_reason == reason
    assert len(returned) == 1
    assert result.stage_4_result is returned[0]
    assert result.stage_4_result == expected


@pytest.mark.parametrize("reason", COLLABORATIVE_NO_SUPPORT_REASONS)
def test_every_ready_no_support_reason_returns_the_exact_stage4_payload(
    snapshot,
    tmp_path,
    monkeypatch,
    reason,
) -> None:
    feedback_ranker = _feedback_ranker(snapshot, tmp_path)
    context = UserContext(preferred_genres=("strategy",), top_k=3)
    feedback = () if reason == "no_query_sources" else (_liked("alpha-tactics"),)
    prepared = feedback_ranker.prepare_ranking_context(context, feedback)
    scoring_result = _no_support_result(prepared, reason)
    original_rank = feedback_ranker.rank
    expected = original_rank(context, feedback)
    returned = []

    def tracked_stage4_rank(actual_context, actual_feedback):
        result = original_rank(actual_context, actual_feedback)
        returned.append(result)
        return result

    monkeypatch.setattr(feedback_ranker, "rank", tracked_stage4_rank)

    result = HybridRanker(feedback_ranker).rank(
        context,
        feedback,
        CollaborativeComponentReady(scoring_result),
    )

    assert type(result) is Stage4FallbackResult
    assert result.fallback_reason == reason
    assert len(returned) == 1
    assert result.stage_4_result is returned[0]
    assert result.stage_4_result == expected


def test_hybrid_ranker_runs_the_complete_supported_pipeline_without_stage4_fallback(
    snapshot,
    tmp_path,
    monkeypatch,
) -> None:
    feedback_ranker = _feedback_ranker(snapshot, tmp_path)
    context = UserContext(preferred_genres=("strategy",), top_k=3)
    feedback = (
        _liked("alpha-tactics"),
        ActiveGameFeedback(game_slug="beta-kingdom", played=True),
    )
    prepared = feedback_ranker.prepare_ranking_context(context, feedback)
    scoring_result = _collaborative_recommendations(
        prepared,
        (("beta-kingdom", 600_000), ("gamma-drift", 400_000)),
    )

    def unexpected_stage4_fallback(_context, _feedback):
        raise AssertionError("Supported hybrid ranking must not invoke the Stage 4 wrapper")

    monkeypatch.setattr(feedback_ranker, "rank", unexpected_stage4_fallback)

    first = HybridRanker(feedback_ranker).rank(
        context,
        feedback,
        CollaborativeComponentReady(scoring_result),
    )
    second = HybridRanker(feedback_ranker).rank(
        context,
        feedback,
        CollaborativeComponentReady(scoring_result),
    )

    assert type(first) is HybridRecommendationsResult
    assert first == second
    assert first.mode == "hybrid"
    assert tuple(
        (
            item.slug,
            item.rank,
            item.candidate_origin,
            item.base_score_units,
            item.affinity_score_units,
            item.collaborative_score_units,
            item.base_contribution_units,
            item.affinity_contribution_units,
            item.collaborative_contribution_units,
            item.pre_played_score_units,
            item.played_factor_units,
            item.played_delta_units,
            item.final_score_units,
        )
        for item in first.items
    ) == (
        (
            "delta-command",
            1,
            "content",
            257_370,
            389_497,
            0,
            205_896,
            38_950,
            0,
            244_846,
            1_000_000,
            0,
            244_846,
        ),
        (
            "beta-kingdom",
            2,
            "both",
            263_230,
            341_166,
            600_000,
            210_584,
            34_117,
            60_000,
            304_701,
            500_000,
            -152_350,
            152_351,
        ),
        (
            "gamma-drift",
            3,
            "collaborative",
            35_000,
            38_481,
            400_000,
            28_000,
            3_848,
            40_000,
            71_848,
            1_000_000,
            0,
            71_848,
        ),
    )
    first.validate()


def test_fixture_comparison_freezes_stage4_and_hybrid_candidate_diagnostics(
    snapshot,
    tmp_path,
) -> None:
    """Functional diagnostic only; these literals are not ranking-quality evidence."""

    feedback_ranker = _feedback_ranker(snapshot, tmp_path)
    context = UserContext(preferred_genres=("strategy",), top_k=3)
    feedback = (
        _liked("alpha-tactics"),
        ActiveGameFeedback(game_slug="beta-kingdom", played=True),
    )
    baseline = feedback_ranker.rank(context, feedback)
    prepared = feedback_ranker.prepare_ranking_context(context, feedback)
    collaborative = _collaborative_recommendations(
        prepared,
        (("beta-kingdom", 600_000), ("gamma-drift", 400_000)),
    )
    hybrid = HybridRanker(feedback_ranker).rank(
        context,
        feedback,
        CollaborativeComponentReady(collaborative),
    )
    fallback = HybridRanker(feedback_ranker).rank(
        context,
        feedback,
        CollaborativeComponentUnavailable(reason="not_configured"),
    )

    comparison = (
        (
            "stage_4_baseline",
            tuple(
                (
                    item.slug,
                    item.rank,
                    item.base_score_units,
                    item.affinity_score_units,
                    item.base_contribution_units,
                    item.affinity_contribution_units,
                    item.pre_played_score_units,
                    item.played_factor_units,
                    item.played_delta_units,
                    item.final_score_units,
                )
                for item in baseline.items
            ),
        ),
        (
            "hybrid_functional_diagnostic",
            tuple(
                (
                    item.slug,
                    item.rank,
                    item.candidate_origin,
                    item.base_score_units,
                    item.affinity_score_units,
                    item.collaborative_score_units,
                    item.final_score_units,
                )
                for item in hybrid.items
            ),
        ),
        (
            "fallback_functional_diagnostic",
            fallback.mode,
            fallback.fallback_reason,
            tuple(
                (item.slug, item.rank, item.final_score_units)
                for item in fallback.stage_4_result.items
            ),
        ),
    )
    assert comparison == (
        (
            "stage_4_baseline",
            (
                (
                    "delta-command",
                    1,
                    257_370,
                    389_497,
                    231_633,
                    38_950,
                    270_583,
                    1_000_000,
                    0,
                    270_583,
                ),
                (
                    "beta-kingdom",
                    2,
                    263_230,
                    341_166,
                    236_907,
                    34_117,
                    271_024,
                    500_000,
                    -135_512,
                    135_512,
                ),
            ),
        ),
        (
            "hybrid_functional_diagnostic",
            (
                ("delta-command", 1, "content", 257_370, 389_497, 0, 244_846),
                ("beta-kingdom", 2, "both", 263_230, 341_166, 600_000, 152_351),
                ("gamma-drift", 3, "collaborative", 35_000, 38_481, 400_000, 71_848),
            ),
        ),
        (
            "fallback_functional_diagnostic",
            "stage_4_fallback",
            "not_configured",
            (("delta-command", 1, 270_583), ("beta-kingdom", 2, 135_512)),
        ),
    )


def test_ready_context_or_exclusion_mismatch_fails_without_silent_fallback(
    snapshot,
    tmp_path,
    monkeypatch,
) -> None:
    feedback_ranker = _feedback_ranker(snapshot, tmp_path)
    context = UserContext(preferred_genres=("strategy",), top_k=3)
    alpha_feedback = (_liked("alpha-tactics"),)
    prepared = feedback_ranker.prepare_ranking_context(context, alpha_feedback)
    collaborative = _collaborative_recommendations(
        prepared,
        (("gamma-drift", 400_000),),
    )
    unknown_candidate = _collaborative_recommendations(
        prepared,
        (("unknown-game", 400_000),),
    )
    disliked_feedback = (_liked("alpha-tactics"), _disliked("gamma-drift"))

    def unexpected_stage4_fallback(_context, _feedback):
        raise AssertionError("Invalid ready state must not become Stage 4 fallback")

    monkeypatch.setattr(feedback_ranker, "rank", unexpected_stage4_fallback)

    for feedback, scoring_result in (
        ((_liked("beta-kingdom"),), collaborative),
        (disliked_feedback, collaborative),
        (alpha_feedback, unknown_candidate),
    ):
        with pytest.raises(HybridContractError) as captured:
            HybridRanker(feedback_ranker).rank(
                context,
                feedback,
                CollaborativeComponentReady(scoring_result),
            )
        assert captured.value.code == "hybrid_input_invalid"


def test_invalid_component_outcome_fails_before_any_ranking(
    snapshot,
    tmp_path,
    monkeypatch,
) -> None:
    feedback_ranker = _feedback_ranker(snapshot, tmp_path)

    def unexpected_stage4_rank(_context, _feedback):
        raise AssertionError("Invalid outcome must fail before ranking")

    monkeypatch.setattr(feedback_ranker, "rank", unexpected_stage4_rank)
    with pytest.raises(HybridContractError) as captured:
        HybridRanker(feedback_ranker).rank(
            UserContext(preferred_genres=("strategy",)),
            (),
            object(),  # type: ignore[arg-type]
        )

    assert captured.value.code == "hybrid_input_invalid"
