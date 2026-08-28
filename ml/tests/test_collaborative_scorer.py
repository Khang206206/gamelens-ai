from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

import numpy as np
import pytest

from gamelens_recommender.collaborative import (
    CollaborativeQueryContext,
    CollaborativeQuerySource,
    CollaborativeScorer,
    CollaborativeScoringError,
    CollaborativeSourceState,
    canonicalize_collaborative_query_sources,
    lookup_collaborative_neighborhoods,
)
from gamelens_recommender.collaborative_artifacts import LoadedCollaborativeArtifact
from gamelens_recommender.schemas import PositiveFeedbackSource


def _positive(
    slug: str,
    *,
    hour: int,
    kind: str = "liked",
) -> PositiveFeedbackSource:
    return PositiveFeedbackSource(
        game_slug=slug,
        kind=kind,
        occurred_at=datetime(2026, 8, 28, hour, tzinfo=UTC),
    )


def _context(
    *,
    positive_sources: tuple[PositiveFeedbackSource, ...] = (),
    saved_game_slugs: tuple[str, ...] = (),
    disliked_slugs: tuple[str, ...] = (),
) -> CollaborativeQueryContext:
    return canonicalize_collaborative_query_sources(
        CollaborativeSourceState(
            positive_sources=positive_sources,
            saved_game_slugs=saved_game_slugs,
            disliked_slugs=disliked_slugs,
        )
    )


def _candidate_projection(result) -> tuple[object, ...]:
    return tuple(
        (
            candidate.slug,
            candidate.collaborative_score_units,
            candidate.item_support,
            tuple(
                (
                    edge.source_slug,
                    edge.source_kind,
                    edge.similarity_units,
                    edge.pair_support,
                )
                for edge in candidate.source_edges
            ),
        )
        for candidate in result.candidates
    )


def test_multi_source_score_rounds_half_up_and_returns_complete_ordered_evidence(
    hand_authored_collaborative_artifact: LoadedCollaborativeArtifact,
) -> None:
    context = _context(
        positive_sources=(
            _positive("alpha-source", hour=2),
            _positive("zeta-source", hour=1, kind="rating"),
        )
    )
    scorer = CollaborativeScorer(hand_authored_collaborative_artifact)

    result = scorer.score(context)

    assert result.reason == "recommendations"
    assert result.identity == scorer.identity
    assert _candidate_projection(result) == (
        (
            "omega-candidate",
            721_688,
            3,
            (
                ("alpha-source", "liked", 866_025, 3),
                ("zeta-source", "rating", 577_350, 2),
            ),
        ),
        (
            "beta-candidate",
            577_350,
            3,
            (
                ("alpha-source", "liked", 577_350, 2),
                ("zeta-source", "rating", 577_350, 2),
            ),
        ),
    )
    assert (
        result.diagnostics.query_source_count,
        result.diagnostics.supported_source_count,
        result.diagnostics.unsupported_source_count,
        result.diagnostics.zero_degree_source_count,
        result.diagnostics.visited_edge_count,
        result.diagnostics.candidate_count_before_exclusions,
        result.diagnostics.query_source_exclusion_count,
        result.diagnostics.dislike_exclusion_count,
        result.diagnostics.returned_candidate_count,
    ) == (2, 2, 0, 0, 6, 4, 2, 0, 2)
    assert {candidate.slug for candidate in result.candidates}.isdisjoint(
        source.game_slug for source in context.sources
    )

    lookup = lookup_collaborative_neighborhoods(
        hand_authored_collaborative_artifact,
        context,
    )
    raw_by_candidate = {
        candidate.slug: tuple(
            sorted(
                (
                    edge.source_slug,
                    edge.source_kind,
                    edge.similarity_units,
                    edge.pair_support,
                )
                for row in lookup.neighborhoods
                for edge in row.edges
                if edge.candidate_slug == candidate.slug
            )
        )
        for candidate in result.candidates
    }
    assert raw_by_candidate == {
        candidate.slug: tuple(
            sorted(
                (
                    edge.source_slug,
                    edge.source_kind,
                    edge.similarity_units,
                    edge.pair_support,
                )
                for edge in candidate.source_edges
            )
        )
        for candidate in result.candidates
    }
    for candidate in result.candidates:
        edge_sum = sum(edge.similarity_units for edge in candidate.source_edges)
        edge_count = len(candidate.source_edges)
        assert candidate.collaborative_score_units == (2 * edge_sum + edge_count) // (
            2 * edge_count
        )


def test_available_edge_mean_ignores_missing_edges_instead_of_adding_zero(
    hand_authored_collaborative_artifact: LoadedCollaborativeArtifact,
) -> None:
    context = _context(saved_game_slugs=("alpha-source", "beta-candidate"))

    result = CollaborativeScorer(hand_authored_collaborative_artifact).score(context)

    assert _candidate_projection(result) == (
        (
            "omega-candidate",
            866_025,
            3,
            (("alpha-source", "saved_game", 866_025, 3),),
        ),
        (
            "zeta-source",
            538_675,
            4,
            (
                ("beta-candidate", "saved_game", 577_350, 2),
                ("alpha-source", "saved_game", 500_000, 2),
            ),
        ),
    )


def test_equal_candidate_scores_use_slug_order(
    hand_authored_collaborative_artifact: LoadedCollaborativeArtifact,
) -> None:
    result = CollaborativeScorer(hand_authored_collaborative_artifact).score(
        _context(saved_game_slugs=("beta-candidate",))
    )

    assert tuple(
        (candidate.slug, candidate.collaborative_score_units) for candidate in result.candidates
    ) == (
        ("alpha-source", 577_350),
        ("zeta-source", 577_350),
    )


@pytest.mark.parametrize(
    ("context", "reason", "counts"),
    [
        pytest.param(
            _context(),
            "no_query_sources",
            (0, 0, 0, 0, 0),
            id="empty-sources",
        ),
        pytest.param(
            _context(saved_game_slugs=("unsupported-source",)),
            "no_supported_sources",
            (1, 0, 1, 0, 0),
            id="all-unsupported",
        ),
        pytest.param(
            _context(saved_game_slugs=("gamma-empty",)),
            "no_candidate_edges",
            (1, 1, 0, 1, 0),
            id="supported-zero-degree",
        ),
    ],
)
def test_expected_sparse_states_return_most_specific_typed_reason(
    hand_authored_collaborative_artifact: LoadedCollaborativeArtifact,
    context: CollaborativeQueryContext,
    reason: str,
    counts: tuple[int, int, int, int, int],
) -> None:
    result = CollaborativeScorer(hand_authored_collaborative_artifact).score(context)

    assert result.reason == reason
    assert result.candidates == ()
    assert (
        result.diagnostics.query_source_count,
        result.diagnostics.supported_source_count,
        result.diagnostics.unsupported_source_count,
        result.diagnostics.zero_degree_source_count,
        result.diagnostics.visited_edge_count,
    ) == counts


def test_source_then_dislike_exclusions_are_disjoint_and_can_remove_every_candidate(
    hand_authored_collaborative_artifact: LoadedCollaborativeArtifact,
) -> None:
    context = _context(
        saved_game_slugs=("alpha-source", "zeta-source"),
        disliked_slugs=("beta-candidate", "omega-candidate"),
    )

    result = CollaborativeScorer(hand_authored_collaborative_artifact).score(context)

    assert result.reason == "no_eligible_candidates"
    assert result.candidates == ()
    assert (
        result.diagnostics.candidate_count_before_exclusions,
        result.diagnostics.query_source_exclusion_count,
        result.diagnostics.dislike_exclusion_count,
        result.diagnostics.returned_candidate_count,
    ) == (4, 2, 2, 0)


def test_equivalent_source_permutations_and_row_visit_order_keep_candidate_output_equal(
    hand_authored_collaborative_artifact: LoadedCollaborativeArtifact,
) -> None:
    first_state = CollaborativeSourceState(
        positive_sources=(
            _positive("alpha-source", hour=2),
            _positive("zeta-source", hour=1, kind="rating"),
        ),
        disliked_slugs=("beta-candidate",),
    )
    second_state = CollaborativeSourceState(
        positive_sources=tuple(reversed(first_state.positive_sources)),
        disliked_slugs=tuple(reversed(first_state.disliked_slugs)),
    )
    first_context = canonicalize_collaborative_query_sources(first_state)
    second_context = canonicalize_collaborative_query_sources(second_state)
    scorer = CollaborativeScorer(hand_authored_collaborative_artifact)

    first = scorer.score(first_context)
    second = scorer.score(second_context)
    reversed_rows = scorer.score(
        replace(first_context, sources=tuple(reversed(first_context.sources)))
    )

    assert second == first
    assert reversed_rows.candidates == first.candidates
    assert reversed_rows.diagnostics == first.diagnostics


def test_candidate_contract_rejects_a_score_not_reconstructed_from_all_edges(
    hand_authored_collaborative_artifact: LoadedCollaborativeArtifact,
) -> None:
    result = CollaborativeScorer(hand_authored_collaborative_artifact).score(
        _context(saved_game_slugs=("alpha-source", "zeta-source"))
    )
    invalid = replace(
        result.candidates[0],
        collaborative_score_units=result.candidates[0].collaborative_score_units - 1,
    )

    with pytest.raises(CollaborativeScoringError) as captured:
        invalid.validate()

    assert captured.value.code == "scoring_result_invalid"


def _immutable(values: list[int], dtype: str) -> np.ndarray:
    payload = np.asarray(values, dtype=np.dtype(dtype)).tobytes()
    return np.frombuffer(payload, dtype=np.dtype(dtype))


def _maximum_edge_artifact() -> LoadedCollaborativeArtifact:
    source_slugs = tuple(f"source-{index}" for index in range(10))
    candidate_slugs = tuple(f"candidate-{index:03d}" for index in range(100))
    item_slugs = source_slugs + candidate_slugs
    neighbor_indices = list(range(10, 110)) * 10
    indptr = [0]
    for row in range(len(item_slugs)):
        indptr.append(indptr[-1] + (100 if row < 10 else 0))
    return LoadedCollaborativeArtifact(
        root=Path("phase-3d-maximum-edge-artifact"),
        manifest=MappingProxyType(
            {
                "build": MappingProxyType({"id": "phase-3d-maximum-edge-artifact"}),
                "catalog_fingerprint": "c" * 64,
                "interaction_fingerprint": "d" * 64,
                "model": MappingProxyType(
                    {"name": "gamelens-item-item-cosine", "version": "1.0.0"}
                ),
            }
        ),
        item_slugs=item_slugs,
        item_support=_immutable([10] * len(item_slugs), "int64"),
        neighbor_indices=_immutable(neighbor_indices, "int32"),
        neighbor_indptr=_immutable(indptr, "int32"),
        similarity_units=_immutable([500_000] * 1_000, "int32"),
        pair_support=_immutable([2] * 1_000, "int64"),
        slug_to_index=MappingProxyType({slug: index for index, slug in enumerate(item_slugs)}),
    )


def test_scorer_accepts_exact_one_thousand_edge_boundary() -> None:
    artifact = _maximum_edge_artifact()
    context = _context(
        positive_sources=tuple(_positive(f"source-{index}", hour=5 - index) for index in range(5)),
        saved_game_slugs=tuple(f"source-{index}" for index in range(5, 10)),
    )

    result = CollaborativeScorer(artifact).score(context)

    assert result.reason == "recommendations"
    assert result.diagnostics.visited_edge_count == 1_000
    assert result.diagnostics.candidate_count_before_exclusions == 100
    assert result.diagnostics.returned_candidate_count == 100
    assert len(result.candidates) == 100
    assert all(candidate.collaborative_score_units == 500_000 for candidate in result.candidates)
    assert all(len(candidate.source_edges) == 10 for candidate in result.candidates)


def test_scorer_rejects_one_over_query_source_limit_before_lookup(
    hand_authored_collaborative_artifact: LoadedCollaborativeArtifact,
) -> None:
    context = CollaborativeQueryContext(
        sources=tuple(
            CollaborativeQuerySource(game_slug=f"source-{index}", kind="saved_game")
            for index in range(11)
        )
    )

    with pytest.raises(CollaborativeScoringError) as captured:
        CollaborativeScorer(hand_authored_collaborative_artifact).score(context)

    assert captured.value.code == "scoring_input_invalid"
