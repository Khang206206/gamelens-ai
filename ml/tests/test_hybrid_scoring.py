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
    HYBRID_POLICY_CONFIG,
    HybridCandidateRanking,
    HybridCandidateUnion,
    HybridContractError,
    RankedHybridCandidate,
    materialize_hybrid_candidate_union,
    rank_hybrid_candidate_union,
)
from gamelens_recommender.ranking import contribution

NOW = datetime(2026, 8, 29, tzinfo=UTC)


def _ranker(snapshot, tmp_path) -> FeedbackRanker:
    return FeedbackRanker(load_artifact(build_artifact(snapshot, tmp_path / "model")))


def _liked(slug: str) -> ActiveGameFeedback:
    return ActiveGameFeedback(
        game_slug=slug,
        reaction="liked",
        reaction_occurred_at=NOW,
    )


def _collaborative_candidate(
    source,
    slug: str,
    score_units: int,
) -> CollaborativeCandidateScore:
    return CollaborativeCandidateScore(
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


def _collaborative_recommendations(
    prepared,
    candidates: tuple[tuple[str, int], ...],
) -> CollaborativeScoringResult:
    query_sources = prepared.collaborative_query_context.sources
    assert query_sources
    source = query_sources[0]
    scored = tuple(
        sorted(
            (_collaborative_candidate(source, slug, units) for slug, units in candidates),
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


def _union(ranker, prepared, candidates):
    return materialize_hybrid_candidate_union(
        ranker,
        prepared,
        _collaborative_recommendations(prepared, candidates),
    )


def test_hybrid_scoring_applies_request_wide_weights_and_played_after_blending(
    snapshot,
    tmp_path,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    prepared = ranker.prepare_ranking_context(
        UserContext(preferred_genres=("strategy",), top_k=3),
        (
            _liked("alpha-tactics"),
            ActiveGameFeedback(game_slug="beta-kingdom", played=True),
        ),
    )
    candidate_union = _union(
        ranker,
        prepared,
        (("beta-kingdom", 600_000), ("gamma-drift", 400_000)),
    )

    result = rank_hybrid_candidate_union(candidate_union, prepared)

    assert result.policy == HYBRID_POLICY_CONFIG.identity
    assert result.affinity_profile_active is True
    assert len(result.items) == 3
    assert tuple(
        (
            item.candidate.slug,
            item.rank,
            item.candidate.candidate_origin,
            item.candidate.base.base_score_units,
            item.candidate.affinity_score_units,
            item.candidate.collaborative_candidate.collaborative_score_units
            if item.candidate.collaborative_candidate is not None
            else 0,
            item.base_contribution_units,
            item.affinity_contribution_units,
            item.collaborative_contribution_units,
            item.pre_played_score_units,
            item.played_factor_units,
            item.played_delta_units,
            item.final_score_units,
            item.adjustment_reasons,
        )
        for item in result.items
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
            ("feedback_affinity",),
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
            (
                "feedback_affinity",
                "collaborative_similarity",
                "played_adjustment",
            ),
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
            ("feedback_affinity", "collaborative_similarity"),
        ),
    )
    by_slug = {item.candidate.slug: item for item in result.items}
    assert set(by_slug) == {"beta-kingdom", "delta-command", "gamma-drift"}
    for item in result.items:
        collaborative_score_units = (
            item.candidate.collaborative_candidate.collaborative_score_units
            if item.candidate.collaborative_candidate is not None
            else 0
        )
        assert (
            item.base_weight_units,
            item.affinity_weight_units,
            item.collaborative_weight_units,
        ) == (800_000, 100_000, 100_000)
        assert item.base_contribution_units == contribution(
            item.candidate.base.base_score_units,
            item.base_weight_units,
        )
        assert item.affinity_contribution_units == contribution(
            item.candidate.affinity_score_units,
            item.affinity_weight_units,
        )
        assert item.collaborative_contribution_units == contribution(
            collaborative_score_units,
            item.collaborative_weight_units,
        )
        assert item.pre_played_score_units == (
            item.base_contribution_units
            + item.affinity_contribution_units
            + item.collaborative_contribution_units
        )
        assert item.final_score_units == contribution(
            item.pre_played_score_units,
            item.played_factor_units,
        )
        assert item.played_delta_units == item.final_score_units - item.pre_played_score_units

    assert by_slug["delta-command"].collaborative_weight_units == 100_000
    assert by_slug["delta-command"].collaborative_contribution_units == 0
    assert by_slug["delta-command"].adjustment_reasons == ("feedback_affinity",)
    assert by_slug["gamma-drift"].adjustment_reasons == (
        "feedback_affinity",
        "collaborative_similarity",
    )
    assert by_slug["beta-kingdom"].played_factor_units == 500_000
    assert by_slug["beta-kingdom"].adjustment_reasons == (
        "feedback_affinity",
        "collaborative_similarity",
        "played_adjustment",
    )
    result.validate()


def test_hybrid_scoring_without_affinity_uses_90_0_10_for_every_candidate(
    snapshot,
    tmp_path,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    prepared = ranker.prepare_ranking_context(
        UserContext(selected_game_slugs=("alpha-tactics",), top_k=4),
        (),
    )
    result = rank_hybrid_candidate_union(
        _union(ranker, prepared, (("gamma-drift", 400_000),)),
        prepared,
    )

    assert result.affinity_profile_active is False
    assert all(
        (
            item.base_weight_units,
            item.affinity_weight_units,
            item.collaborative_weight_units,
        )
        == (900_000, 0, 100_000)
        for item in result.items
    )
    assert all(item.affinity_contribution_units == 0 for item in result.items)
    assert all("feedback_affinity" not in item.adjustment_reasons for item in result.items)


def test_hybrid_scoring_orders_after_played_adjustment_then_applies_top_k(
    snapshot,
    tmp_path,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    context = UserContext(preferred_genres=("strategy",), top_k=1)
    prepared = ranker.prepare_ranking_context(
        context,
        (
            _liked("alpha-tactics"),
            ActiveGameFeedback(game_slug="beta-kingdom", played=True),
        ),
    )
    candidate_union = _union(
        ranker,
        prepared,
        (("beta-kingdom", 600_000), ("gamma-drift", 400_000)),
    )

    result = rank_hybrid_candidate_union(candidate_union, prepared)

    assert len(candidate_union.candidates) == 3
    assert len(result.items) == 1
    assert result.items[0].rank == 1
    assert result.items[0].candidate.slug != "beta-kingdom"
    assert "played_adjustment" not in result.items[0].adjustment_reasons


def test_collaborative_contribution_precedes_affinity_in_frozen_ties(
    item_factory,
    tmp_path,
) -> None:
    snapshot = canonical_snapshot(
        item_factory(
            f"same-{suffix}",
            title="Same Game",
            description="identical tactical strategy",
            popularity=50,
        )
        for suffix in "abc"
    )
    ranker = _ranker(snapshot, tmp_path)
    prepared = ranker.prepare_ranking_context(
        UserContext(preferred_genres=("strategy",), top_k=2),
        (_liked("same-c"),),
    )
    candidate_union = _union(
        ranker,
        prepared,
        (("same-a", 600_000), ("same-b", 400_000)),
    )
    source = prepared.collaborative_query_context.sources[0]
    first, second = candidate_union.candidates
    tied_union = HybridCandidateUnion(
        affinity_profile_active=True,
        candidates=(
            replace(
                first,
                affinity_score_units=200_000,
                collaborative_candidate=_collaborative_candidate(source, "same-a", 600_000),
            ),
            replace(
                second,
                affinity_score_units=400_000,
                collaborative_candidate=_collaborative_candidate(source, "same-b", 400_000),
            ),
        ),
    )
    tied_union.validate()

    result = rank_hybrid_candidate_union(tied_union, prepared)

    assert [item.candidate.slug for item in result.items] == ["same-a", "same-b"]
    first_ranked, second_ranked = result.items
    assert first_ranked.final_score_units == second_ranked.final_score_units
    assert first_ranked.pre_played_score_units == second_ranked.pre_played_score_units
    assert first_ranked.base_contribution_units == second_ranked.base_contribution_units
    assert (
        first_ranked.collaborative_contribution_units
        > second_ranked.collaborative_contribution_units
    )


def test_full_hybrid_tie_break_ends_with_stable_slug(item_factory, tmp_path) -> None:
    snapshot = canonical_snapshot(
        item_factory(
            f"same-{suffix}",
            title="Same Game",
            description="identical tactical strategy",
            popularity=50,
        )
        for suffix in "abc"
    )
    ranker = _ranker(snapshot, tmp_path)
    prepared = ranker.prepare_ranking_context(
        UserContext(preferred_genres=("strategy",), top_k=2),
        (_liked("same-c"),),
    )
    candidate_union = _union(
        ranker,
        prepared,
        (("same-a", 500_000), ("same-b", 500_000)),
    )

    first = rank_hybrid_candidate_union(candidate_union, prepared)
    second = rank_hybrid_candidate_union(candidate_union, prepared)

    assert first == second
    assert [item.candidate.slug for item in first.items] == ["same-a", "same-b"]
    left, right = first.items
    assert (
        left.final_score_units,
        left.pre_played_score_units,
        left.base_contribution_units,
        left.collaborative_contribution_units,
        left.affinity_contribution_units,
        left.candidate.base.content_score_units,
        left.candidate.base.popularity_score_units,
    ) == (
        right.final_score_units,
        right.pre_played_score_units,
        right.base_contribution_units,
        right.collaborative_contribution_units,
        right.affinity_contribution_units,
        right.candidate.base.content_score_units,
        right.candidate.base.popularity_score_units,
    )


def test_hybrid_scoring_rejects_no_collaborative_candidate_or_context_drift(
    snapshot,
    tmp_path,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    prepared = ranker.prepare_ranking_context(
        UserContext(preferred_genres=("strategy",)),
        (_liked("alpha-tactics"),),
    )
    candidate_union = _union(
        ranker,
        prepared,
        (("gamma-drift", 400_000),),
    )
    content_only = HybridCandidateUnion(
        affinity_profile_active=True,
        candidates=tuple(
            candidate
            for candidate in candidate_union.candidates
            if candidate.collaborative_candidate is None
        ),
    )
    content_only.validate()
    inactive_candidates = tuple(
        replace(candidate, affinity_score_units=0) for candidate in candidate_union.candidates
    )
    affinity_drift = HybridCandidateUnion(
        affinity_profile_active=False,
        candidates=inactive_candidates,
    )
    affinity_drift.validate()

    for invalid, message in (
        (content_only, "eligible collaborative"),
        (affinity_drift, "affinity state"),
    ):
        with pytest.raises(HybridContractError) as captured:
            rank_hybrid_candidate_union(invalid, prepared)
        assert captured.value.code == "hybrid_input_invalid"
        assert message in str(captured.value)


def test_hybrid_candidate_ranking_is_frozen_reconstructible_and_internal(
    snapshot,
    tmp_path,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    prepared = ranker.prepare_ranking_context(
        UserContext(preferred_genres=("strategy",), top_k=3),
        (_liked("alpha-tactics"),),
    )
    result = rank_hybrid_candidate_union(
        _union(ranker, prepared, (("gamma-drift", 400_000),)),
        prepared,
    )

    assert type(result) is HybridCandidateRanking
    assert all(type(item) is RankedHybridCandidate for item in result.items)
    assert not hasattr(result.items[0], "explanation_summary")
    with pytest.raises(FrozenInstanceError):
        result.items[0].rank = 2
    with pytest.raises(HybridContractError) as captured:
        replace(
            result.items[0],
            base_contribution_units=result.items[0].base_contribution_units + 1,
        ).validate()
    assert captured.value.code == "hybrid_result_invalid"
    with pytest.raises(HybridContractError) as captured:
        replace(result, items=tuple(reversed(result.items))).validate()
    assert captured.value.code == "hybrid_result_invalid"

    assert {
        "HybridCandidateRanking",
        "RankedHybridCandidate",
        "rank_hybrid_candidate_union",
    }.isdisjoint(gamelens_recommender.__all__)
