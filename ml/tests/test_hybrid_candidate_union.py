from dataclasses import FrozenInstanceError, replace
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
    canonical_snapshot,
    load_artifact,
)
from gamelens_recommender.collaborative import COLLABORATIVE_SCORING_CONFIG
from gamelens_recommender.hybrid import (
    HybridCandidateComponents,
    HybridCandidateUnion,
    HybridContractError,
    materialize_hybrid_candidate_union,
)

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


def _no_candidate_edges(prepared) -> CollaborativeScoringResult:
    query_sources = prepared.collaborative_query_context.sources
    assert len(query_sources) == 1
    result = CollaborativeScoringResult(
        reason="no_candidate_edges",
        identity=COLLABORATIVE_SCORING_CONFIG.identity,
        query_sources=query_sources,
        supported_source_slugs=(query_sources[0].game_slug,),
        unsupported_source_slugs=(),
        candidates=(),
        diagnostics=CollaborativeScoringDiagnostics(
            query_source_count=1,
            supported_source_count=1,
            unsupported_source_count=0,
            zero_degree_source_count=1,
            visited_edge_count=0,
            candidate_count_before_exclusions=0,
            query_source_exclusion_count=0,
            dislike_exclusion_count=0,
            returned_candidate_count=0,
        ),
    )
    result.validate()
    return result


def test_candidate_union_materializes_exact_components_and_origins_before_top_k(
    snapshot,
    tmp_path,
    monkeypatch,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    prepared = ranker.prepare_ranking_context(
        UserContext(preferred_genres=("strategy",), top_k=1),
        (_liked("alpha-tactics"),),
    )
    collaborative = _collaborative_recommendations(
        prepared,
        (("beta-kingdom", 600_000), ("gamma-drift", 400_000)),
    )
    original_base = ranker.content_ranker.materialize_base_candidates
    original_affinity = ranker.materialize_affinity_candidates
    base_calls: list[tuple[str, ...]] = []
    affinity_calls: list[tuple[str, ...]] = []

    def recording_base(context, candidate_slugs):
        base_calls.append(candidate_slugs)
        return original_base(context, candidate_slugs)

    def recording_affinity(positive_sources, candidate_slugs):
        affinity_calls.append(candidate_slugs)
        return original_affinity(positive_sources, candidate_slugs)

    def unexpected_final_stage(*_args, **_kwargs):
        raise AssertionError("Candidate union must not apply final Stage 4 or hybrid ranking")

    monkeypatch.setattr(ranker.content_ranker, "materialize_base_candidates", recording_base)
    monkeypatch.setattr(ranker, "materialize_affinity_candidates", recording_affinity)
    monkeypatch.setattr(ranker.content_ranker, "materialize_candidate", unexpected_final_stage)
    monkeypatch.setattr(ranker, "rank", unexpected_final_stage)

    result = materialize_hybrid_candidate_union(ranker, prepared, collaborative)

    assert tuple(candidate.slug for candidate in result.candidates) == (
        "beta-kingdom",
        "delta-command",
        "gamma-drift",
    )
    assert tuple(candidate.candidate_origin for candidate in result.candidates) == (
        "both",
        "content",
        "collaborative",
    )
    assert result.collaborative_candidate_count == 2
    assert result.affinity_profile_active is True
    assert result.candidates[-1].base.content_score_units == 0
    assert base_calls == [("beta-kingdom", "delta-command", "gamma-drift")]
    assert affinity_calls == base_calls
    assert len(result.candidates) > prepared.effective_context.top_k
    result.validate()


def test_candidate_union_applies_prepared_hard_exclusions_after_union(
    snapshot,
    tmp_path,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    prepared = ranker.prepare_ranking_context(
        UserContext(
            selected_game_slugs=("delta-command",),
            preferred_genres=("strategy",),
            top_k=1,
        ),
        (_liked("alpha-tactics"), _disliked("gamma-drift")),
    )
    collaborative = _collaborative_recommendations(
        prepared,
        (("beta-kingdom", 600_000), ("gamma-drift", 400_000)),
    )

    result = materialize_hybrid_candidate_union(ranker, prepared, collaborative)

    assert prepared.candidate_exclusion_slugs == (
        "alpha-tactics",
        "delta-command",
        "gamma-drift",
    )
    assert tuple(candidate.slug for candidate in result.candidates) == ("beta-kingdom",)
    assert result.candidates[0].candidate_origin == "both"


def test_saved_source_union_has_no_feedback_affinity(snapshot, tmp_path) -> None:
    ranker = _ranker(snapshot, tmp_path)
    prepared = ranker.prepare_ranking_context(
        UserContext(selected_game_slugs=("alpha-tactics",), top_k=4),
        (),
    )
    collaborative = _collaborative_recommendations(
        prepared,
        (("gamma-drift", 400_000),),
    )

    result = materialize_hybrid_candidate_union(ranker, prepared, collaborative)

    assert result.affinity_profile_active is False
    assert all(candidate.affinity_score_units == 0 for candidate in result.candidates)
    assert result.collaborative_candidate_count == 1


def test_candidate_union_chunks_exact_materialization_at_the_phase3_row_bound(
    item_factory,
    tmp_path,
    monkeypatch,
) -> None:
    snapshot = canonical_snapshot(item_factory(f"game-{index:04d}") for index in range(1_002))
    ranker = _ranker(snapshot, tmp_path)
    prepared = ranker.prepare_ranking_context(
        UserContext(preferred_genres=("strategy",), top_k=1),
        (_liked("game-0000"),),
    )
    collaborative = _collaborative_recommendations(
        prepared,
        (("game-0001", 400_000),),
    )
    original_base = ranker.content_ranker.materialize_base_candidates
    original_affinity = ranker.materialize_affinity_candidates
    base_chunk_sizes: list[int] = []
    affinity_chunk_sizes: list[int] = []

    def recording_base(context, candidate_slugs):
        base_chunk_sizes.append(len(candidate_slugs))
        return original_base(context, candidate_slugs)

    def recording_affinity(positive_sources, candidate_slugs):
        affinity_chunk_sizes.append(len(candidate_slugs))
        return original_affinity(positive_sources, candidate_slugs)

    monkeypatch.setattr(ranker.content_ranker, "materialize_base_candidates", recording_base)
    monkeypatch.setattr(ranker, "materialize_affinity_candidates", recording_affinity)

    result = materialize_hybrid_candidate_union(ranker, prepared, collaborative)

    assert len(result.candidates) == 1_001
    assert base_chunk_sizes == [1_000, 1]
    assert affinity_chunk_sizes == base_chunk_sizes


def test_candidate_union_rejects_mismatched_query_before_content_scoring(
    snapshot,
    tmp_path,
    monkeypatch,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    prepared = ranker.prepare_ranking_context(
        UserContext(preferred_genres=("strategy",)),
        (_liked("alpha-tactics"),),
    )
    other_prepared = ranker.prepare_ranking_context(
        UserContext(preferred_genres=("strategy",)),
        (_liked("beta-kingdom"),),
    )
    collaborative = _collaborative_recommendations(
        other_prepared,
        (("gamma-drift", 400_000),),
    )

    def unexpected_call(*_args, **_kwargs):
        raise AssertionError("Mismatched input must fail before candidate scoring")

    monkeypatch.setattr(ranker.content_ranker, "score_candidates", unexpected_call)

    with pytest.raises(HybridContractError) as captured:
        materialize_hybrid_candidate_union(ranker, prepared, collaborative)

    assert captured.value.code == "hybrid_input_invalid"
    assert "query sources" in str(captured.value)


def test_candidate_union_rejects_catalog_mismatch_before_content_scoring(
    snapshot,
    tmp_path,
    monkeypatch,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    prepared = ranker.prepare_ranking_context(
        UserContext(preferred_genres=("strategy",)),
        (_liked("alpha-tactics"),),
    )
    collaborative = _collaborative_recommendations(
        prepared,
        (("unknown-game", 400_000),),
    )

    def unexpected_call(*_args, **_kwargs):
        raise AssertionError("Catalog mismatch must fail before candidate scoring")

    monkeypatch.setattr(ranker.content_ranker, "score_candidates", unexpected_call)

    with pytest.raises(HybridContractError) as captured:
        materialize_hybrid_candidate_union(ranker, prepared, collaborative)

    assert captured.value.code == "hybrid_input_invalid"
    assert "content artifact" in str(captured.value)


def test_candidate_union_requires_collaborative_recommendation_support(
    snapshot,
    tmp_path,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    prepared = ranker.prepare_ranking_context(
        UserContext(preferred_genres=("strategy",)),
        (_liked("alpha-tactics"),),
    )

    with pytest.raises(HybridContractError) as captured:
        materialize_hybrid_candidate_union(ranker, prepared, _no_candidate_edges(prepared))

    assert captured.value.code == "hybrid_input_invalid"
    assert "recommendation support" in str(captured.value)


def test_candidate_union_contract_is_frozen_canonical_and_internal(snapshot, tmp_path) -> None:
    ranker = _ranker(snapshot, tmp_path)
    prepared = ranker.prepare_ranking_context(
        UserContext(preferred_genres=("strategy",)),
        (_liked("alpha-tactics"),),
    )
    result = materialize_hybrid_candidate_union(
        ranker,
        prepared,
        _collaborative_recommendations(prepared, (("gamma-drift", 400_000),)),
    )

    assert type(result) is HybridCandidateUnion
    assert all(type(candidate) is HybridCandidateComponents for candidate in result.candidates)
    with pytest.raises(FrozenInstanceError):
        result.affinity_profile_active = False
    with pytest.raises(HybridContractError) as captured:
        replace(result, candidates=tuple(reversed(result.candidates))).validate()
    assert captured.value.code == "hybrid_result_invalid"

    collaborative_candidate = result.candidates[-1]
    with pytest.raises(HybridContractError) as captured:
        replace(collaborative_candidate, candidate_origin="content").validate()
    assert captured.value.code == "hybrid_result_invalid"

    assert {
        "HybridCandidateComponents",
        "HybridCandidateUnion",
        "materialize_hybrid_candidate_union",
    }.isdisjoint(gamelens_recommender.__all__)
