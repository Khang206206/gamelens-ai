from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from types import MappingProxyType

import numpy as np
import pytest

from gamelens_recommender.collaborative import (
    CollaborativeScoringError,
    CollaborativeSourceState,
    canonicalize_collaborative_query_sources,
    lookup_collaborative_neighborhoods,
)
from gamelens_recommender.collaborative_artifacts import LoadedCollaborativeArtifact
from gamelens_recommender.schemas import PositiveFeedbackSource


def _context(
    *saved_slugs: str,
    disliked_slugs: tuple[str, ...] = (),
):
    return canonicalize_collaborative_query_sources(
        CollaborativeSourceState(
            saved_game_slugs=tuple(saved_slugs),
            disliked_slugs=disliked_slugs,
        )
    )


def _edge_projection(result) -> tuple[tuple[str, int, int, int], ...]:
    return tuple(
        (
            edge.candidate_slug,
            edge.item_support,
            edge.similarity_units,
            edge.pair_support,
        )
        for edge in result.neighborhoods[0].edges
    )


@pytest.mark.parametrize(
    ("source_slug", "expected"),
    [
        pytest.param(
            "alpha-source",
            (
                ("omega-candidate", 3, 866_025, 3),
                ("beta-candidate", 3, 577_350, 2),
                ("zeta-source", 4, 500_000, 2),
            ),
            id="first-row-index-zero",
        ),
        pytest.param(
            "beta-candidate",
            (
                ("alpha-source", 4, 577_350, 2),
                ("zeta-source", 4, 577_350, 2),
            ),
            id="middle-row",
        ),
        pytest.param("gamma-empty", (), id="empty-row"),
        pytest.param(
            "zeta-source",
            (
                ("beta-candidate", 3, 577_350, 2),
                ("omega-candidate", 3, 577_350, 2),
                ("alpha-source", 4, 500_000, 2),
            ),
            id="last-row-final-indptr",
        ),
    ],
)
def test_lookup_copies_exact_first_middle_empty_and_last_csr_rows(
    hand_authored_collaborative_artifact: LoadedCollaborativeArtifact,
    source_slug: str,
    expected: tuple[tuple[str, int, int, int], ...],
) -> None:
    result = lookup_collaborative_neighborhoods(
        hand_authored_collaborative_artifact,
        _context(source_slug),
    )

    assert _edge_projection(result) == expected
    row = result.neighborhoods[0]
    assert row.supported is True
    assert result.diagnostics.visited_edge_count == len(expected)
    assert result.diagnostics.zero_degree_source_count == (not expected)
    assert all(type(edge.item_support) is int for edge in row.edges)
    assert all(type(edge.similarity_units) is int for edge in row.edges)
    assert all(type(edge.pair_support) is int for edge in row.edges)


def test_lookup_distinguishes_unsupported_and_zero_degree_sources_in_counters(
    hand_authored_collaborative_artifact: LoadedCollaborativeArtifact,
) -> None:
    context = _context("unsupported-source", "gamma-empty", "alpha-source")

    result = lookup_collaborative_neighborhoods(
        hand_authored_collaborative_artifact,
        context,
    )

    assert tuple(
        (row.source.game_slug, row.supported, len(row.edges)) for row in result.neighborhoods
    ) == (
        ("alpha-source", True, 3),
        ("gamma-empty", True, 0),
        ("unsupported-source", False, 0),
    )
    assert result.supported_source_slugs == ("alpha-source", "gamma-empty")
    assert result.unsupported_source_slugs == ("unsupported-source",)
    assert (
        result.diagnostics.query_source_count,
        result.diagnostics.supported_source_count,
        result.diagnostics.unsupported_source_count,
        result.diagnostics.zero_degree_source_count,
        result.diagnostics.visited_edge_count,
    ) == (3, 2, 1, 1, 3)


def test_lookup_preserves_source_kind_and_defers_exclusion_and_aggregation(
    hand_authored_collaborative_artifact: LoadedCollaborativeArtifact,
) -> None:
    context = canonicalize_collaborative_query_sources(
        CollaborativeSourceState(
            positive_sources=(
                PositiveFeedbackSource(
                    game_slug="alpha-source",
                    kind="liked",
                    occurred_at=datetime(2026, 8, 27, 2, tzinfo=UTC),
                ),
                PositiveFeedbackSource(
                    game_slug="zeta-source",
                    kind="rating",
                    occurred_at=datetime(2026, 8, 27, 1, tzinfo=UTC),
                ),
            ),
            disliked_slugs=("beta-candidate",),
        )
    )

    result = lookup_collaborative_neighborhoods(
        hand_authored_collaborative_artifact,
        context,
    )

    assert tuple((row.source.game_slug, row.source.kind) for row in result.neighborhoods) == (
        ("alpha-source", "liked"),
        ("zeta-source", "rating"),
    )
    assert [edge.candidate_slug for row in result.neighborhoods for edge in row.edges].count(
        "beta-candidate"
    ) == 2
    assert result.diagnostics.visited_edge_count == 6


class _TrackingArray(np.ndarray):
    reads: list[object]

    def __new__(cls, value: np.ndarray):
        result = value.view(cls)
        result.reads = []
        result.flags.writeable = False
        return result

    def __array_finalize__(self, source: np.ndarray | None) -> None:
        self.reads = getattr(source, "reads", [])

    def __getitem__(self, key: object):
        self.reads.append(key)
        return super().__getitem__(key)


def test_unsupported_source_performs_no_csr_row_or_edge_read(
    hand_authored_collaborative_artifact: LoadedCollaborativeArtifact,
) -> None:
    tracked_indptr = _TrackingArray(hand_authored_collaborative_artifact.neighbor_indptr)
    tracked_indices = _TrackingArray(hand_authored_collaborative_artifact.neighbor_indices)
    tracked_similarity = _TrackingArray(hand_authored_collaborative_artifact.similarity_units)
    tracked_pair_support = _TrackingArray(hand_authored_collaborative_artifact.pair_support)
    tracked_item_support = _TrackingArray(hand_authored_collaborative_artifact.item_support)
    artifact = replace(
        hand_authored_collaborative_artifact,
        item_support=tracked_item_support,
        neighbor_indices=tracked_indices,
        neighbor_indptr=tracked_indptr,
        similarity_units=tracked_similarity,
        pair_support=tracked_pair_support,
    )

    result = lookup_collaborative_neighborhoods(
        artifact,
        _context("unsupported-source"),
    )

    assert result.unsupported_source_slugs == ("unsupported-source",)
    assert tracked_indptr.reads == [0, -1]
    assert tracked_indices.reads == []
    assert tracked_similarity.reads == []
    assert tracked_pair_support.reads == []
    assert tracked_item_support.reads == []


def test_repeated_and_interleaved_lookups_do_not_mutate_artifact_or_results(
    hand_authored_collaborative_artifact: LoadedCollaborativeArtifact,
) -> None:
    artifact = hand_authored_collaborative_artifact
    arrays = (
        artifact.item_support,
        artifact.neighbor_indices,
        artifact.neighbor_indptr,
        artifact.similarity_units,
        artifact.pair_support,
    )
    snapshots = tuple(value.copy() for value in arrays)
    mapping_snapshot = dict(artifact.slug_to_index)
    first_context = _context("alpha-source", "gamma-empty", "unsupported-source")
    second_context = _context("beta-candidate", "zeta-source")

    first = lookup_collaborative_neighborhoods(artifact, first_context)
    lookup_collaborative_neighborhoods(artifact, second_context)
    repeated = lookup_collaborative_neighborhoods(artifact, first_context)

    assert repeated == first
    assert all(
        np.array_equal(value, snapshot) for value, snapshot in zip(arrays, snapshots, strict=True)
    )
    assert all(value.flags.writeable is False for value in arrays)
    assert dict(artifact.slug_to_index) == mapping_snapshot
    with pytest.raises(FrozenInstanceError):
        first.neighborhoods = ()
    with pytest.raises(FrozenInstanceError):
        first.neighborhoods[0].supported = False
    with pytest.raises(FrozenInstanceError):
        first.neighborhoods[0].edges[0].similarity_units = 1


def _immutable(values: list[int], dtype: str) -> np.ndarray:
    result = np.asarray(values, dtype=np.dtype(dtype))
    result.flags.writeable = False
    return result


@pytest.mark.parametrize(
    "artifact_factory",
    [
        pytest.param(lambda artifact: object(), id="invalid-artifact-type"),
        pytest.param(
            lambda artifact: replace(
                artifact,
                neighbor_indices=artifact.neighbor_indices.copy(),
            ),
            id="mutable-artifact-array",
        ),
        pytest.param(
            lambda artifact: replace(
                artifact,
                slug_to_index=dict(artifact.slug_to_index),
            ),
            id="mutable-slug-index",
        ),
        pytest.param(
            lambda artifact: replace(
                artifact,
                slug_to_index=MappingProxyType({**artifact.slug_to_index, "alpha-source": 1}),
            ),
            id="inconsistent-source-index",
        ),
        pytest.param(
            lambda artifact: replace(
                artifact,
                neighbor_indices=_immutable([0] * 101, "int32"),
                neighbor_indptr=_immutable([0, 101, 101, 101, 101, 101], "int32"),
                similarity_units=_immutable([1] * 101, "int32"),
                pair_support=_immutable([2] * 101, "int64"),
            ),
            id="row-over-neighbor-limit",
        ),
    ],
)
def test_lookup_rejects_incompatible_artifact_before_returning_partial_rows(
    hand_authored_collaborative_artifact: LoadedCollaborativeArtifact,
    artifact_factory,
) -> None:
    artifact = artifact_factory(hand_authored_collaborative_artifact)

    with pytest.raises(CollaborativeScoringError) as captured:
        lookup_collaborative_neighborhoods(artifact, _context("alpha-source"))

    assert captured.value.code == "scoring_artifact_incompatible"


def test_lookup_result_contract_rejects_physical_storage_order_as_evidence_order(
    hand_authored_collaborative_artifact: LoadedCollaborativeArtifact,
) -> None:
    result = lookup_collaborative_neighborhoods(
        hand_authored_collaborative_artifact,
        _context("alpha-source"),
    )
    row = result.neighborhoods[0]
    invalid = replace(result, neighborhoods=(replace(row, edges=tuple(reversed(row.edges))),))

    with pytest.raises(CollaborativeScoringError) as captured:
        invalid.validate()

    assert captured.value.code == "scoring_result_invalid"
