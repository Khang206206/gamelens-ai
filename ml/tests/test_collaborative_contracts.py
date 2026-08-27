from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime

import pytest

from gamelens_recommender.collaborative import (
    COLLABORATIVE_SCORING_CONFIG,
    CollaborativeCandidateScore,
    CollaborativeQueryContext,
    CollaborativeQuerySource,
    CollaborativeScoringDiagnostics,
    CollaborativeScoringError,
    CollaborativeScoringResult,
    CollaborativeSourceEdge,
    CollaborativeSourceState,
)
from gamelens_recommender.schemas import PositiveFeedbackSource

NOW = datetime(2026, 8, 27, tzinfo=UTC)


def _positive_source(
    slug: str = "alpha-source",
    *,
    kind: str = "liked",
    occurred_at: datetime = NOW,
) -> PositiveFeedbackSource:
    return PositiveFeedbackSource(game_slug=slug, kind=kind, occurred_at=occurred_at)


def _query_source(
    slug: str = "alpha-source",
    *,
    kind: str = "liked",
) -> CollaborativeQuerySource:
    return CollaborativeQuerySource(game_slug=slug, kind=kind)


def _edge(
    *,
    source_slug: str = "alpha-source",
    source_kind: str = "liked",
    candidate_slug: str = "beta-candidate",
    similarity_units: int = 800_000,
    pair_support: int = 2,
) -> CollaborativeSourceEdge:
    return CollaborativeSourceEdge(
        source_slug=source_slug,
        source_kind=source_kind,
        candidate_slug=candidate_slug,
        similarity_units=similarity_units,
        pair_support=pair_support,
    )


def _diagnostics(
    *,
    query_sources: int,
    supported: int,
    unsupported: int,
    zero_degree: int = 0,
    visited_edges: int = 0,
    candidates_before_exclusions: int = 0,
    source_exclusions: int = 0,
    dislike_exclusions: int = 0,
    returned: int = 0,
) -> CollaborativeScoringDiagnostics:
    return CollaborativeScoringDiagnostics(
        query_source_count=query_sources,
        supported_source_count=supported,
        unsupported_source_count=unsupported,
        zero_degree_source_count=zero_degree,
        visited_edge_count=visited_edges,
        candidate_count_before_exclusions=candidates_before_exclusions,
        query_source_exclusion_count=source_exclusions,
        dislike_exclusion_count=dislike_exclusions,
        returned_candidate_count=returned,
    )


def _recommendation_result() -> CollaborativeScoringResult:
    source = _query_source()
    candidate = CollaborativeCandidateScore(
        slug="beta-candidate",
        collaborative_score_units=800_000,
        item_support=3,
        source_edges=(_edge(),),
    )
    return CollaborativeScoringResult(
        reason="recommendations",
        identity=COLLABORATIVE_SCORING_CONFIG.identity,
        query_sources=(source,),
        supported_source_slugs=(source.game_slug,),
        unsupported_source_slugs=(),
        candidates=(candidate,),
        diagnostics=_diagnostics(
            query_sources=1,
            supported=1,
            unsupported=0,
            visited_edges=1,
            candidates_before_exclusions=1,
            returned=1,
        ),
    )


def test_scoring_config_freezes_identity_numeric_policy_bounds_and_ordering() -> None:
    config = COLLABORATIVE_SCORING_CONFIG

    config.validate()

    assert config.identity.name == "gamelens-collaborative-scoring"
    assert config.identity.version == "1.0.0"
    assert config.score_scale == 1_000_000
    assert (
        config.max_positive_sources,
        config.max_saved_game_sources,
        config.max_query_sources,
        config.max_neighbors_per_source,
        config.max_visited_edges,
        config.max_candidates,
        config.max_source_state_entries,
    ) == (5, 5, 10, 100, 1_000, 1_000, 100_000)
    assert config.source_precedence == ("dislike", "liked", "rating", "saved_game")
    assert config.aggregation == "available_similarity_mean_round_half_up"
    assert config.evidence_order == (
        "similarity_units_desc",
        "pair_support_desc",
        "source_slug_asc",
    )
    assert config.candidate_order == ("collaborative_score_units_desc", "slug_asc")
    with pytest.raises(FrozenInstanceError):
        config.version = "2.0.0"


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "unversioned-scorer"},
        {"version": "2.0.0"},
        {"score_scale": 100},
        {"max_query_sources": 11},
        {"max_source_state_entries": 99_999},
        {"max_visited_edges": 999},
        {"aggregation": "float_mean"},
        {"candidate_order": ("artifact_index_asc",)},
    ],
)
def test_scoring_config_rejects_identity_policy_or_limit_drift(changes: dict[str, object]) -> None:
    with pytest.raises(CollaborativeScoringError) as captured:
        replace(COLLABORATIVE_SCORING_CONFIG, **changes).validate()

    assert captured.value.code == "scoring_config_invalid"


def test_source_state_validates_immutable_positive_saved_and_dislike_inputs() -> None:
    state = CollaborativeSourceState(
        positive_sources=(
            _positive_source(),
            _positive_source("beta-source", kind="rating"),
        ),
        saved_game_slugs=("alpha-source", "saved-source"),
        disliked_slugs=("blocked-source",),
    )

    state.validate()

    assert state.positive_sources[0].occurred_at.tzinfo is UTC
    with pytest.raises(FrozenInstanceError):
        state.saved_game_slugs = ()


@pytest.mark.parametrize(
    "state",
    [
        pytest.param(
            CollaborativeSourceState(positive_sources=[_positive_source()]),
            id="mutable-positive-source-collection",
        ),
        pytest.param(
            CollaborativeSourceState(positive_sources=(_positive_source(kind="saved_game"),)),
            id="invalid-positive-source-kind",
        ),
        pytest.param(
            CollaborativeSourceState(
                positive_sources=(_positive_source(occurred_at=datetime(2026, 8, 27)),)
            ),
            id="naive-positive-source-timestamp",
        ),
        pytest.param(
            CollaborativeSourceState(saved_game_slugs=("Not-Canonical",)),
            id="noncanonical-saved-slug",
        ),
        pytest.param(
            CollaborativeSourceState(
                positive_sources=(_positive_source(),)
                * (COLLABORATIVE_SCORING_CONFIG.max_source_state_entries + 1)
            ),
            id="positive-source-input-bound",
        ),
        pytest.param(
            CollaborativeSourceState(
                saved_game_slugs=("saved-source",)
                * (COLLABORATIVE_SCORING_CONFIG.max_source_state_entries + 1)
            ),
            id="saved-source-input-bound",
        ),
    ],
)
def test_source_state_rejects_mutability_invalid_types_timestamps_slugs_and_bounds(
    state: CollaborativeSourceState,
) -> None:
    with pytest.raises(CollaborativeScoringError) as captured:
        state.validate()

    assert captured.value.code == "scoring_input_invalid"


def test_canonical_query_context_owns_timestamp_free_sources_and_sorted_exclusions() -> None:
    context = CollaborativeQueryContext(
        sources=(
            _query_source(),
            _query_source("beta-source", kind="rating"),
            _query_source("saved-source", kind="saved_game"),
        ),
        disliked_slugs=("blocked-a", "blocked-z"),
    )

    context.validate()

    assert tuple(field.name for field in fields(CollaborativeQuerySource)) == (
        "game_slug",
        "kind",
    )


@pytest.mark.parametrize(
    "context",
    [
        pytest.param(
            CollaborativeQueryContext(sources=[_query_source()]),
            id="mutable-query-source-collection",
        ),
        pytest.param(
            CollaborativeQueryContext(sources=(_query_source(), _query_source())),
            id="duplicate-canonical-source",
        ),
        pytest.param(
            CollaborativeQueryContext(sources=(_query_source(kind="unknown"),)),
            id="unknown-source-kind",
        ),
        pytest.param(
            CollaborativeQueryContext(
                sources=(_query_source(),),
                disliked_slugs=("alpha-source",),
            ),
            id="dislike-precedence-not-applied",
        ),
        pytest.param(
            CollaborativeQueryContext(disliked_slugs=("blocked-z", "blocked-a")),
            id="noncanonical-dislike-order",
        ),
    ],
)
def test_canonical_query_context_rejects_noncanonical_or_mutable_state(
    context: CollaborativeQueryContext,
) -> None:
    with pytest.raises(CollaborativeScoringError) as captured:
        context.validate()

    assert captured.value.code == "scoring_input_invalid"


def test_candidate_contract_freezes_integer_bounds_complete_evidence_and_ordering() -> None:
    candidate = CollaborativeCandidateScore(
        slug="target-game",
        collaborative_score_units=750_000,
        item_support=4,
        source_edges=(
            _edge(
                candidate_slug="target-game",
                similarity_units=800_000,
                pair_support=2,
            ),
            _edge(
                source_slug="zeta-source",
                source_kind="saved_game",
                candidate_slug="target-game",
                similarity_units=700_000,
                pair_support=3,
            ),
        ),
    )

    candidate.validate()

    assert all(type(edge.similarity_units) is int for edge in candidate.source_edges)
    assert all(type(edge.pair_support) is int for edge in candidate.source_edges)
    with pytest.raises(FrozenInstanceError):
        candidate.item_support = 5


def test_candidate_contract_rejects_misaligned_or_misordered_edge_evidence() -> None:
    low = _edge(candidate_slug="target-game", similarity_units=600_000)
    high = _edge(
        source_slug="zeta-source",
        source_kind="saved_game",
        candidate_slug="target-game",
        similarity_units=900_000,
    )
    candidate = CollaborativeCandidateScore(
        slug="target-game",
        collaborative_score_units=750_000,
        item_support=4,
        source_edges=(low, high),
    )

    with pytest.raises(CollaborativeScoringError) as captured:
        candidate.validate()

    assert captured.value.code == "scoring_result_invalid"


@pytest.mark.parametrize(
    "result",
    [
        pytest.param(_recommendation_result(), id="recommendations"),
        pytest.param(
            CollaborativeScoringResult(
                reason="no_query_sources",
                identity=COLLABORATIVE_SCORING_CONFIG.identity,
                query_sources=(),
                supported_source_slugs=(),
                unsupported_source_slugs=(),
                candidates=(),
                diagnostics=_diagnostics(query_sources=0, supported=0, unsupported=0),
            ),
            id="no-query-sources",
        ),
        pytest.param(
            CollaborativeScoringResult(
                reason="no_supported_sources",
                identity=COLLABORATIVE_SCORING_CONFIG.identity,
                query_sources=(_query_source(),),
                supported_source_slugs=(),
                unsupported_source_slugs=("alpha-source",),
                candidates=(),
                diagnostics=_diagnostics(query_sources=1, supported=0, unsupported=1),
            ),
            id="no-supported-sources",
        ),
        pytest.param(
            CollaborativeScoringResult(
                reason="no_candidate_edges",
                identity=COLLABORATIVE_SCORING_CONFIG.identity,
                query_sources=(_query_source(),),
                supported_source_slugs=("alpha-source",),
                unsupported_source_slugs=(),
                candidates=(),
                diagnostics=_diagnostics(
                    query_sources=1,
                    supported=1,
                    unsupported=0,
                    zero_degree=1,
                ),
            ),
            id="no-candidate-edges",
        ),
        pytest.param(
            CollaborativeScoringResult(
                reason="no_eligible_candidates",
                identity=COLLABORATIVE_SCORING_CONFIG.identity,
                query_sources=(_query_source(),),
                supported_source_slugs=("alpha-source",),
                unsupported_source_slugs=(),
                candidates=(),
                diagnostics=_diagnostics(
                    query_sources=1,
                    supported=1,
                    unsupported=0,
                    visited_edges=1,
                    candidates_before_exclusions=1,
                    source_exclusions=1,
                ),
            ),
            id="no-eligible-candidates",
        ),
    ],
)
def test_scoring_result_reason_taxonomy_matches_bounded_diagnostics(
    result: CollaborativeScoringResult,
) -> None:
    result.validate()


def test_scoring_result_rejects_mutable_partial_or_inconsistent_output() -> None:
    valid = _recommendation_result()
    invalid_values = (
        replace(valid, candidates=list(valid.candidates)),
        replace(valid, reason="no_candidate_edges"),
        replace(
            valid,
            diagnostics=replace(valid.diagnostics, returned_candidate_count=0),
        ),
        replace(
            valid,
            identity=replace(valid.identity, version="2.0.0"),
        ),
        replace(valid, supported_source_slugs=("Not-Canonical",)),
        replace(
            valid,
            diagnostics=replace(valid.diagnostics, visited_edge_count=True),
        ),
    )

    for value in invalid_values:
        with pytest.raises(CollaborativeScoringError) as captured:
            value.validate()
        assert captured.value.code == "scoring_result_invalid"


def test_hand_authored_neighborhood_fixture_freezes_csr_boundaries_and_storage_order(
    hand_authored_collaborative_artifact,
) -> None:
    artifact = hand_authored_collaborative_artifact
    arrays = (
        artifact.item_support,
        artifact.neighbor_indices,
        artifact.neighbor_indptr,
        artifact.similarity_units,
        artifact.pair_support,
    )

    assert artifact.item_slugs == (
        "alpha-source",
        "beta-candidate",
        "gamma-empty",
        "omega-candidate",
        "zeta-source",
    )
    assert artifact.neighbor_indptr.tolist() == [0, 3, 5, 5, 7, 10]
    assert [array.flags.writeable for array in arrays] == [False] * len(arrays)
    with pytest.raises(ValueError):
        artifact.neighbor_indices.setflags(write=True)

    rows = []
    for index in range(len(artifact.item_slugs)):
        start = int(artifact.neighbor_indptr[index])
        stop = int(artifact.neighbor_indptr[index + 1])
        rows.append(
            (
                artifact.neighbor_indices[start:stop].tolist(),
                artifact.similarity_units[start:stop].tolist(),
                artifact.pair_support[start:stop].tolist(),
            )
        )
    assert rows == [
        ([1, 3, 4], [577_350, 866_025, 500_000], [2, 3, 2]),
        ([0, 4], [577_350, 577_350], [2, 2]),
        ([], [], []),
        ([0, 4], [866_025, 577_350], [3, 2]),
        ([0, 1, 3], [500_000, 577_350, 577_350], [2, 2, 2]),
    ]
    first_row_slugs = tuple(artifact.item_slugs[index] for index in rows[0][0])
    first_row_evidence_order = tuple(
        artifact.item_slugs[index]
        for _, _, index in sorted(
            zip(rows[0][1], rows[0][2], rows[0][0], strict=True),
            key=lambda value: (-value[0], -value[1], artifact.item_slugs[value[2]]),
        )
    )
    assert first_row_slugs == ("beta-candidate", "omega-candidate", "zeta-source")
    assert first_row_evidence_order == (
        "omega-candidate",
        "beta-candidate",
        "zeta-source",
    )
