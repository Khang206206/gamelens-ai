from dataclasses import replace
from datetime import UTC, datetime

import pytest

import gamelens_recommender
from gamelens_recommender import (
    ActiveGameFeedback,
    CollaborativeCandidateScore,
    CollaborativeScoringDiagnostics,
    CollaborativeScoringResult,
    CollaborativeSourceEdge,
    FeedbackRanker,
    UserContext,
    build_artifact,
    load_artifact,
)
from gamelens_recommender.collaborative import COLLABORATIVE_SCORING_CONFIG
from gamelens_recommender.hybrid import (
    AFFINITY_EXPLANATION,
    COLLABORATIVE_EXPLANATION,
    PLAYED_EXPLANATION,
    HybridContractError,
    materialize_hybrid_candidate_union,
    materialize_hybrid_recommendations,
    rank_hybrid_candidate_union,
)

NOW = datetime(2026, 8, 29, tzinfo=UTC)


def _ranker(snapshot, tmp_path) -> FeedbackRanker:
    return FeedbackRanker(load_artifact(build_artifact(snapshot, tmp_path / "model")))


def _liked(slug: str) -> ActiveGameFeedback:
    return ActiveGameFeedback(
        game_slug=slug,
        reaction="liked",
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


def _successful_pipeline(ranker: FeedbackRanker):
    prepared = ranker.prepare_ranking_context(
        UserContext(preferred_genres=("strategy",), top_k=3),
        (
            _liked("alpha-tactics"),
            ActiveGameFeedback(game_slug="beta-kingdom", played=True),
        ),
    )
    collaborative = _collaborative_recommendations(
        prepared,
        (("beta-kingdom", 600_000), ("gamma-drift", 400_000)),
    )
    candidate_union = materialize_hybrid_candidate_union(
        ranker,
        prepared,
        collaborative,
    )
    ranking = rank_hybrid_candidate_union(candidate_union, prepared)
    return prepared, collaborative, ranking


def test_hybrid_materialization_returns_exact_ranked_components_and_evidence(
    snapshot,
    tmp_path,
    monkeypatch,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    prepared, collaborative, ranking = _successful_pipeline(ranker)
    original_materialize = ranker.content_ranker.materialize_candidate
    calls: list[tuple[str, int]] = []

    def track_materialization(candidate, context, *, rank):
        calls.append((candidate.slug, rank))
        return original_materialize(candidate, context, rank=rank)

    monkeypatch.setattr(
        ranker.content_ranker,
        "materialize_candidate",
        track_materialization,
    )

    result = materialize_hybrid_recommendations(
        ranker,
        prepared,
        collaborative,
        ranking,
    )

    assert result.mode == "hybrid"
    assert result.reason == "recommendations"
    assert result.policy == ranking.policy
    assert result.feedback_policy == ranker.identity
    assert result.collaborative_policy == collaborative.identity
    assert result.collaborative_diagnostics == collaborative.diagnostics
    assert result.positive_sources == prepared.positive_sources
    assert calls == [(ranked.candidate.slug, ranked.rank) for ranked in ranking.items]
    for actual, ranked in zip(result.items, ranking.items, strict=True):
        candidate = ranked.candidate
        collaborative_candidate = candidate.collaborative_candidate
        expected_base = original_materialize(
            candidate.base,
            prepared.effective_context,
            rank=ranked.rank,
        )
        assert (
            actual.slug,
            actual.rank,
            actual.candidate_origin,
            actual.base_score_units,
            actual.base_components,
            actual.base_evidence,
            actual.base_weight_units,
            actual.base_contribution_units,
            actual.affinity_score_units,
            actual.affinity_weight_units,
            actual.affinity_contribution_units,
            actual.collaborative_supported,
            actual.collaborative_score_units,
            actual.collaborative_weight_units,
            actual.collaborative_contribution_units,
            actual.collaborative_item_support,
            actual.collaborative_source_edges,
            actual.pre_played_score_units,
            actual.played_factor_units,
            actual.played_delta_units,
            actual.final_score_units,
            actual.adjustment_reasons,
        ) == (
            candidate.slug,
            ranked.rank,
            candidate.candidate_origin,
            candidate.base.base_score_units,
            expected_base.components,
            expected_base.evidence,
            ranked.base_weight_units,
            ranked.base_contribution_units,
            candidate.affinity_score_units,
            ranked.affinity_weight_units,
            ranked.affinity_contribution_units,
            collaborative_candidate is not None,
            collaborative_candidate.collaborative_score_units
            if collaborative_candidate is not None
            else 0,
            ranked.collaborative_weight_units,
            ranked.collaborative_contribution_units,
            collaborative_candidate.item_support if collaborative_candidate is not None else None,
            collaborative_candidate.source_edges if collaborative_candidate is not None else (),
            ranked.pre_played_score_units,
            ranked.played_factor_units,
            ranked.played_delta_units,
            ranked.final_score_units,
            ranked.adjustment_reasons,
        )
    result.validate()


def test_hybrid_explanations_are_deterministic_cautious_and_evidence_backed(
    snapshot,
    tmp_path,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    prepared, collaborative, ranking = _successful_pipeline(ranker)

    first = materialize_hybrid_recommendations(
        ranker,
        prepared,
        collaborative,
        ranking,
    )
    second = materialize_hybrid_recommendations(
        ranker,
        prepared,
        collaborative,
        ranking,
    )

    assert first == second
    by_slug = {item.slug: item for item in first.items}
    collaborative_only = by_slug["gamma-drift"]
    assert collaborative_only.candidate_origin == "collaborative"
    assert collaborative_only.base_components[0].raw_units == 0
    assert collaborative_only.base_evidence.matching_genres == ()
    assert collaborative_only.base_evidence.matching_tags == ()
    assert collaborative_only.base_evidence.preferred_platforms == ()
    assert collaborative_only.base_evidence.similar_selected_games == ()
    assert collaborative_only.explanation_reasons == (
        AFFINITY_EXPLANATION,
        COLLABORATIVE_EXPLANATION,
    )

    content_only = by_slug["delta-command"]
    assert content_only.candidate_origin == "content"
    assert COLLABORATIVE_EXPLANATION not in content_only.explanation_reasons
    assert AFFINITY_EXPLANATION in content_only.explanation_reasons

    played = by_slug["beta-kingdom"]
    assert played.played_delta_units < 0
    assert played.explanation_reasons[-1] == PLAYED_EXPLANATION
    prose = " ".join(reason.lower() for item in first.items for reason in item.explanation_reasons)
    assert not any(
        unsupported in prose
        for unsupported in ("users like you", "popular with players", "other users", "quality")
    )


def test_zero_applied_collaborative_contribution_has_no_collaborative_prose(
    snapshot,
    tmp_path,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    prepared = ranker.prepare_ranking_context(
        UserContext(selected_game_slugs=("alpha-tactics",), top_k=3),
        (),
    )
    collaborative = _collaborative_recommendations(
        prepared,
        (("gamma-drift", 1),),
    )
    candidate_union = materialize_hybrid_candidate_union(
        ranker,
        prepared,
        collaborative,
    )
    ranking = rank_hybrid_candidate_union(candidate_union, prepared)

    result = materialize_hybrid_recommendations(
        ranker,
        prepared,
        collaborative,
        ranking,
    )

    candidate = next(item for item in result.items if item.slug == "gamma-drift")
    assert candidate.collaborative_supported is True
    assert candidate.collaborative_score_units == 1
    assert candidate.collaborative_contribution_units == 0
    assert COLLABORATIVE_EXPLANATION not in candidate.explanation_reasons
    ranked = next(item for item in ranking.items if item.candidate.slug == "gamma-drift")
    base = ranker.content_ranker.materialize_candidate(
        ranked.candidate.base,
        prepared.effective_context,
        rank=ranked.rank,
    )
    assert candidate.explanation_reasons == base.explanation_reasons


def test_hybrid_result_rejects_explanation_drift(snapshot, tmp_path) -> None:
    ranker = _ranker(snapshot, tmp_path)
    prepared, collaborative, ranking = _successful_pipeline(ranker)
    result = materialize_hybrid_recommendations(
        ranker,
        prepared,
        collaborative,
        ranking,
    )

    invalid_item = replace(
        result.items[0],
        explanation_summary="Unsupported personalized claim.",
    )
    with pytest.raises(HybridContractError) as captured:
        replace(result, items=(invalid_item, *result.items[1:])).validate()

    assert captured.value.code == "hybrid_result_invalid"


def test_hybrid_materialization_rejects_mismatched_inputs(snapshot, tmp_path) -> None:
    ranker = _ranker(snapshot, tmp_path)
    prepared, collaborative, ranking = _successful_pipeline(ranker)
    mismatched_collaborative = _collaborative_recommendations(
        prepared,
        (("beta-kingdom", 600_000),),
    )
    reduced_top_k = replace(
        prepared,
        effective_context=replace(prepared.effective_context, top_k=1),
    )

    for invalid_prepared, invalid_collaborative in (
        (prepared, mismatched_collaborative),
        (reduced_top_k, collaborative),
    ):
        with pytest.raises(HybridContractError) as captured:
            materialize_hybrid_recommendations(
                ranker,
                invalid_prepared,
                invalid_collaborative,
                ranking,
            )
        assert captured.value.code == "hybrid_input_invalid"


def test_hybrid_materialization_rejects_stage4_evidence_drift(
    snapshot,
    tmp_path,
    monkeypatch,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    prepared, collaborative, ranking = _successful_pipeline(ranker)
    original_materialize = ranker.content_ranker.materialize_candidate

    def drifted_materialization(candidate, context, *, rank):
        return replace(
            original_materialize(candidate, context, rank=rank),
            components=(),
        )

    monkeypatch.setattr(
        ranker.content_ranker,
        "materialize_candidate",
        drifted_materialization,
    )

    with pytest.raises(HybridContractError) as captured:
        materialize_hybrid_recommendations(
            ranker,
            prepared,
            collaborative,
            ranking,
        )

    assert captured.value.code == "hybrid_input_invalid"


def test_hybrid_materializer_remains_internal_until_public_orchestration_exists() -> None:
    assert not hasattr(gamelens_recommender, "materialize_hybrid_recommendations")
