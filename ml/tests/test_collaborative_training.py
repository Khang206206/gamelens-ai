from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from scipy import sparse

from gamelens_recommender import collaborative_training
from gamelens_recommender import quantize_similarity as package_quantize_similarity
from gamelens_recommender.collaborative_training import (
    CollaborativeTrainingError,
    build_binary_interaction_matrix,
    fit_collaborative_neighborhoods,
    fit_item_item_cosine,
    quantize_similarity,
    validate_binary_interaction_matrix,
    validate_collaborative_neighborhoods,
)
from gamelens_recommender.interaction_snapshot import (
    load_fixture,
    prune_supported_profiles,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPOSITORY_ROOT / "data" / "catalog" / "games.json"
FIXTURE_PATH = (
    REPOSITORY_ROOT / "data" / "fixtures" / "interactions" / "collaborative-interactions.json"
)


def _catalog_slugs() -> frozenset[str]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return frozenset(game["slug"] for game in payload["games"])


def _golden_profiles() -> tuple[tuple[str, ...], ...]:
    return (
        ("a", "b"),
        ("a", "b"),
        ("b", "c"),
        ("b", "c"),
    )


def test_support_pruning_reaches_the_same_cascading_fixed_point() -> None:
    supported = prune_supported_profiles(
        (
            ("a", "b"),
            ("a", "b", "c"),
            ("c", "d"),
            ("d", "e"),
        )
    )

    assert supported.profiles == (("a", "b"), ("a", "b"))
    assert supported.source_indices == (0, 1)
    assert supported.item_support == (("a", 2), ("b", 2))
    assert supported.fixed_point_passes == 4


def test_support_pruning_retains_original_identity_free_row_indices() -> None:
    supported = prune_supported_profiles(
        (
            ("orphan",),
            ("a", "b"),
            ("a", "b"),
            ("c", "d"),
        )
    )

    assert supported.profiles == (("a", "b"), ("a", "b"))
    assert supported.source_indices == (1, 2)


def test_binary_matrix_is_int64_canonical_and_preserves_duplicate_profiles() -> None:
    value = build_binary_interaction_matrix(_golden_profiles())

    assert value.item_slugs == ("a", "b", "c")
    assert value.matrix.shape == (4, 3)
    assert value.matrix.dtype == np.dtype(np.int64)
    np.testing.assert_array_equal(value.matrix.data, np.ones(8, dtype=np.int64))
    np.testing.assert_array_equal(
        value.matrix.indices,
        np.asarray([0, 1, 0, 1, 1, 2, 1, 2], dtype=np.int32),
    )
    np.testing.assert_array_equal(
        value.matrix.indptr,
        np.asarray([0, 2, 4, 6, 8], dtype=np.int32),
    )
    np.testing.assert_array_equal(value.item_support, np.asarray([2, 4, 2], dtype=np.int64))
    assert value.retained_contributors == 4
    assert value.retained_positive_edges == 8
    assert value.pair_contributions == 4
    assert value.matrix.has_canonical_format


def test_hand_calculated_cosine_quantizes_half_up_to_707107() -> None:
    value = fit_item_item_cosine(build_binary_interaction_matrix(_golden_profiles()))

    assert value.item_slugs == ("a", "b", "c")
    np.testing.assert_array_equal(value.item_support, np.asarray([2, 4, 2], dtype=np.int64))
    np.testing.assert_array_equal(value.neighbor_indices, np.asarray([1, 0, 2, 1], dtype=np.int32))
    np.testing.assert_array_equal(value.neighbor_indptr, np.asarray([0, 1, 3, 4], dtype=np.int32))
    np.testing.assert_array_equal(
        value.similarity_units,
        np.asarray([707_107, 707_107, 707_107, 707_107], dtype=np.int32),
    )
    np.testing.assert_array_equal(value.pair_support, np.asarray([2, 2, 2, 2]))
    for array in (
        value.item_support,
        value.neighbor_indices,
        value.neighbor_indptr,
        value.similarity_units,
        value.pair_support,
    ):
        assert array.flags.writeable is False
        with pytest.raises(ValueError):
            array.setflags(write=True)


def test_pair_support_one_is_missing_support_not_a_zero_similarity() -> None:
    matrix = build_binary_interaction_matrix((("a", "b"), ("a", "c"), ("b", "c")))

    with pytest.raises(CollaborativeTrainingError, match="No item pair") as error:
        fit_item_item_cosine(matrix)

    assert error.value.code == "insufficient_data"


def test_int64_pair_arithmetic_does_not_overflow_at_256_contributors() -> None:
    value = fit_item_item_cosine(build_binary_interaction_matrix((("a", "b"),) * 256))

    np.testing.assert_array_equal(value.item_support, np.asarray([256, 256], dtype=np.int64))
    np.testing.assert_array_equal(value.pair_support, np.asarray([256, 256], dtype=np.int64))
    np.testing.assert_array_equal(
        value.similarity_units, np.asarray([1_000_000, 1_000_000], dtype=np.int32)
    )


def test_top_k_uses_rank_key_then_serializes_true_index_sorted_csr() -> None:
    profiles = (("a", "b"),) * 2 + (("a", "c"),) * 3
    matrix = build_binary_interaction_matrix(profiles)
    value = fit_item_item_cosine(matrix, maximum_neighbors=2)

    # For source a, c ranks ahead of b, but the physical CSR row is b then c.
    np.testing.assert_array_equal(value.neighbor_indices[:2], np.asarray([1, 2], dtype=np.int32))
    np.testing.assert_array_equal(
        value.similarity_units[:2], np.asarray([632_456, 774_597], dtype=np.int32)
    )
    assert np.all(np.diff(value.neighbor_indices[:2]) > 0)


def test_top_k_slug_tie_break_selects_lexicographically_first_neighbor() -> None:
    profiles = (("a", "b"),) * 2 + (("a", "c"),) * 2 + (("a", "d"),) * 2
    value = fit_item_item_cosine(build_binary_interaction_matrix(profiles), maximum_neighbors=2)

    first_row = value.neighbor_indices[value.neighbor_indptr[0] : value.neighbor_indptr[1]]
    np.testing.assert_array_equal(first_row, np.asarray([1, 2], dtype=np.int32))
    assert 3 not in first_row


def test_project_fixture_matches_all_support_and_sparse_neighbor_goldens() -> None:
    fixture = load_fixture(FIXTURE_PATH, catalog_slugs=_catalog_slugs())
    value = fit_collaborative_neighborhoods(
        fixture.profiles,
        catalog_slugs=_catalog_slugs(),
    )

    assert value.item_slugs == (
        "clockwork-orchard",
        "emberfall-tactics",
        "neon-drift-circuit",
        "paper-kingdoms",
        "starbound-couriers",
        "verdant-vale",
    )
    np.testing.assert_array_equal(
        value.item_support, np.asarray([6, 7, 7, 2, 7, 7], dtype=np.int64)
    )
    np.testing.assert_array_equal(
        value.neighbor_indptr, np.asarray([0, 4, 8, 12, 12, 16, 20], dtype=np.int32)
    )
    np.testing.assert_array_equal(
        value.neighbor_indices,
        np.asarray(
            [1, 2, 4, 5, 0, 2, 4, 5, 0, 1, 4, 5, 0, 1, 2, 5, 0, 1, 2, 4],
            dtype=np.int32,
        ),
    )
    np.testing.assert_array_equal(
        value.similarity_units,
        np.asarray(
            [
                462_910,
                462_910,
                462_910,
                462_910,
                462_910,
                571_429,
                428_571,
                428_571,
                462_910,
                571_429,
                428_571,
                428_571,
                462_910,
                428_571,
                428_571,
                571_429,
                462_910,
                428_571,
                428_571,
                571_429,
            ],
            dtype=np.int32,
        ),
    )
    np.testing.assert_array_equal(
        value.pair_support,
        np.asarray(
            [3, 3, 3, 3, 3, 4, 3, 3, 3, 4, 3, 3, 3, 3, 3, 4, 3, 3, 3, 4],
            dtype=np.int64,
        ),
    )
    assert value.retained_contributors == 12
    assert value.retained_positive_edges == 36
    assert value.pair_contributions == 36


def test_reordered_equivalent_input_produces_identical_semantic_arrays() -> None:
    first = fit_collaborative_neighborhoods(
        _golden_profiles(), catalog_slugs=frozenset({"a", "b", "c"})
    )
    second = fit_collaborative_neighborhoods(
        tuple(tuple(reversed(profile)) for profile in reversed(_golden_profiles())),
        catalog_slugs=frozenset({"a", "b", "c"}),
    )

    assert first.item_slugs == second.item_slugs
    assert first.retained_contributors == second.retained_contributors
    assert first.retained_positive_edges == second.retained_positive_edges
    assert first.pair_contributions == second.pair_contributions
    for name in (
        "item_support",
        "neighbor_indices",
        "neighbor_indptr",
        "similarity_units",
        "pair_support",
    ):
        np.testing.assert_array_equal(getattr(first, name), getattr(second, name))


def test_training_wrapper_rejects_catalog_mismatch_with_typed_error() -> None:
    with pytest.raises(CollaborativeTrainingError, match="unknown game slug") as error:
        fit_collaborative_neighborhoods(_golden_profiles(), catalog_slugs=frozenset({"a", "b"}))

    assert error.value.code == "catalog_mismatch"


def test_pair_contribution_cap_is_checked_before_sparse_multiplication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(collaborative_training, "MAX_PAIR_CONTRIBUTIONS", 3)

    with pytest.raises(CollaborativeTrainingError, match="Pair contribution") as error:
        build_binary_interaction_matrix(_golden_profiles())

    assert error.value.code == "matrix_limit_exceeded"


def test_duplicate_raw_entries_are_bounded_before_profile_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(collaborative_training, "MAX_POSITIVE_EDGES", 3)

    with pytest.raises(CollaborativeTrainingError, match="Raw positive entry") as error:
        build_binary_interaction_matrix((("a", "a", "a", "a"),))

    assert error.value.code == "snapshot_limit_exceeded"


def test_distinct_pair_cap_is_checked_before_sparse_multiplication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(collaborative_training, "MAX_DISTINCT_PAIRS", 1)

    with pytest.raises(CollaborativeTrainingError, match="Distinct item-pair") as error:
        build_binary_interaction_matrix((("a", "b"),) * 2 + (("a", "c"),) * 2)

    assert error.value.code == "matrix_limit_exceeded"


def test_fit_rechecks_distinct_pair_cap_for_a_caller_supplied_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    matrix = build_binary_interaction_matrix((("a", "b"),) * 2 + (("a", "c"),) * 2)
    monkeypatch.setattr(collaborative_training, "MAX_DISTINCT_PAIRS", 1)

    with pytest.raises(CollaborativeTrainingError, match="Distinct item-pair") as error:
        fit_item_item_cosine(matrix)

    assert error.value.code == "matrix_limit_exceeded"


def test_binary_validator_rejects_noncanonical_and_nonbinary_csr() -> None:
    value = build_binary_interaction_matrix(_golden_profiles())
    indices = value.matrix.indices.copy()
    indices[:2] = indices[1::-1]
    noncanonical = sparse.csr_matrix(
        (value.matrix.data.copy(), indices, value.matrix.indptr.copy()),
        shape=value.matrix.shape,
    )
    with pytest.raises(CollaborativeTrainingError, match="not canonical") as error:
        validate_binary_interaction_matrix(replace(value, matrix=noncanonical))
    assert error.value.code == "matrix_format_invalid"

    data = value.matrix.data.copy()
    data[0] = 2
    nonbinary = sparse.csr_matrix(
        (data, value.matrix.indices.copy(), value.matrix.indptr.copy()),
        shape=value.matrix.shape,
    )
    with pytest.raises(CollaborativeTrainingError, match="binary") as error:
        validate_binary_interaction_matrix(replace(value, matrix=nonbinary))
    assert error.value.code == "matrix_numeric_invalid"


def test_neighborhood_validator_rejects_self_edge_and_wrong_cosine() -> None:
    value = fit_item_item_cosine(build_binary_interaction_matrix(_golden_profiles()))
    indices = value.neighbor_indices.copy()
    indices[0] = 0
    with pytest.raises(CollaborativeTrainingError, match="Self-neighbors") as error:
        validate_collaborative_neighborhoods(replace(value, neighbor_indices=indices))
    assert error.value.code == "neighborhood_format_invalid"

    units = value.similarity_units.copy()
    units[0] -= 1
    with pytest.raises(CollaborativeTrainingError, match="does not match") as error:
        validate_collaborative_neighborhoods(replace(value, similarity_units=units))
    assert error.value.code == "neighborhood_numeric_invalid"


def test_neighborhood_validator_rejects_impossible_graph_semantics() -> None:
    fixture = load_fixture(FIXTURE_PATH, catalog_slugs=_catalog_slugs())
    value = fit_collaborative_neighborhoods(
        fixture.profiles,
        catalog_slugs=_catalog_slugs(),
    )
    pair_support = value.pair_support.copy()
    similarity_units = value.similarity_units.copy()
    reverse_offset = 4  # emberfall-tactics -> clockwork-orchard.
    pair_support[reverse_offset] = 2
    similarity_units[reverse_offset] = quantize_similarity(
        np.float64(pair_support[reverse_offset])
        / np.sqrt(np.float64(value.item_support[0] * value.item_support[1]))
    )
    with pytest.raises(CollaborativeTrainingError, match="Mutual") as mutual:
        validate_collaborative_neighborhoods(
            replace(
                value,
                pair_support=pair_support,
                similarity_units=similarity_units,
            )
        )
    assert mutual.value.code == "neighborhood_numeric_invalid"

    complete = fit_item_item_cosine(build_binary_interaction_matrix((("a", "b", "c"),) * 2))
    with pytest.raises(CollaborativeTrainingError, match="exceeds pair contributions") as total:
        validate_collaborative_neighborhoods(replace(complete, pair_contributions=2))
    assert total.value.code == "neighborhood_numeric_invalid"


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0000005, 1), (0.5, 500_000), (1.0, 1_000_000)],
)
def test_shared_quantizer_uses_round_half_up(value: float, expected: int) -> None:
    assert quantize_similarity(value) == expected
    assert package_quantize_similarity(value) == expected


def test_similarity_units_use_int32_and_reject_an_unrepresentable_scale() -> None:
    value = fit_item_item_cosine(build_binary_interaction_matrix((("a", "b"),) * 2))

    assert value.similarity_units.dtype == np.dtype(np.int32)
    assert int(value.similarity_units.max()) == 1_000_000
    with pytest.raises(CollaborativeTrainingError, match="finite and bounded") as error:
        quantize_similarity(1.0, scale=int(np.iinfo(np.int32).max) + 1)
    assert error.value.code == "similarity_invalid"


@pytest.mark.parametrize("profiles", [(), ((),), (("a", "b"),), (("a",),) * 2])
def test_empty_single_user_and_single_item_have_no_supported_matrix(profiles) -> None:
    with pytest.raises(CollaborativeTrainingError) as error:
        build_binary_interaction_matrix(profiles)
    assert error.value.code == "insufficient_data"


@pytest.mark.parametrize(
    "profiles",
    [None, (None,), ("ab",), (b"ab",), (("",),), ((" a",),), ((1,),), ((float("nan"),),)],
)
def test_invalid_profiles_fail_with_typed_input_error(profiles) -> None:
    with pytest.raises(CollaborativeTrainingError) as error:
        build_binary_interaction_matrix(profiles)
    assert error.value.code == "snapshot_invalid"


def test_duplicate_entries_collapse_to_binary_but_duplicate_contributors_remain() -> None:
    value = build_binary_interaction_matrix((("b", "a", "a"), ("b", "b", "a")))
    assert value.item_slugs == ("a", "b")
    assert value.matrix.indptr.tolist() == [0, 2, 4]
    assert value.matrix.indices.tolist() == [0, 1, 0, 1]
    assert value.matrix.data.tolist() == [1, 1, 1, 1]
    assert value.item_support.tolist() == [2, 2]
    assert (value.retained_contributors, value.retained_positive_edges) == (2, 4)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), -0.1, 1.1, None])
def test_quantizer_rejects_nonfinite_out_of_range_and_nonnumeric_values(value) -> None:
    with pytest.raises(CollaborativeTrainingError) as error:
        quantize_similarity(value)
    assert error.value.code == "similarity_invalid"


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0, 0), (0.000000499999, 0), (0.000000500001, 1), (0.9999995, 1_000_000)],
)
def test_quantizer_boundaries_have_independent_decimal_goldens(value, expected) -> None:
    assert quantize_similarity(value) == expected


def test_pair_threshold_and_diagonal_removal_precede_top_neighbor_pruning() -> None:
    # a has support 3, b 2, c 10. a-b = 1/sqrt(6) > a-c = 2/sqrt(30),
    # but a-b has only one co-positive; neither it nor the diagonal may consume K=1.
    profiles = (("a", "b"),) + (("a", "c"),) * 2 + (("b", "d"),) + (("c", "d"),) * 8
    value = fit_item_item_cosine(build_binary_interaction_matrix(profiles), maximum_neighbors=1)
    assert value.item_slugs == ("a", "b", "c", "d")
    assert value.item_support.tolist() == [3, 2, 10, 9]
    assert value.neighbor_indptr.tolist() == [0, 1, 1, 2, 3]
    assert value.neighbor_indices.tolist() == [2, 3, 2]
    assert value.pair_support.tolist() == [2, 8, 8]
    assert value.similarity_units.tolist() == [365_148, 843_274, 843_274]


def test_equal_cosine_uses_pair_support_before_slug_for_top_neighbor() -> None:
    # a-b = 2/sqrt(6*2), a-c = 4/sqrt(6*8): both 1/sqrt(3).
    # c wins on pair support 4 versus 2 even though b sorts first.
    profiles = (("a", "b"),) * 2 + (("a", "c"),) * 4 + (("c", "d"),) * 4
    value = fit_item_item_cosine(build_binary_interaction_matrix(profiles), maximum_neighbors=1)
    assert value.neighbor_indices[0] == 2
    assert value.pair_support[0] == 4
    assert value.similarity_units[0] == 577_350


@pytest.mark.parametrize(
    ("limit", "maximum", "code"),
    [
        ("MAX_PROFILES", 4, "snapshot_limit_exceeded"),
        ("MAX_POSITIVE_EDGES", 8, "snapshot_limit_exceeded"),
        ("MAX_UNIQUE_ITEMS", 3, "snapshot_limit_exceeded"),
        ("MAX_PAIR_CONTRIBUTIONS", 4, "matrix_limit_exceeded"),
    ],
)
def test_matrix_resource_boundaries_reject_before_array_allocation(
    monkeypatch: pytest.MonkeyPatch, limit: str, maximum: int, code: str
) -> None:
    # Inject small caps so both sides of each boundary use the same real input
    # without allocating production-sized matrices in the fast suite.
    monkeypatch.setattr(collaborative_training, limit, maximum)
    assert build_binary_interaction_matrix(_golden_profiles()).retained_positive_edges == 8
    monkeypatch.setattr(collaborative_training, limit, maximum - 1)

    def forbidden(*args, **kwargs):
        pytest.fail("Resource rejection must precede sparse array allocation")

    monkeypatch.setattr(collaborative_training.np, "empty", forbidden)
    monkeypatch.setattr(collaborative_training.np, "ones", forbidden)
    with pytest.raises(CollaborativeTrainingError) as error:
        build_binary_interaction_matrix(_golden_profiles())
    assert error.value.code == code


def test_distinct_pair_boundary_rejects_before_sparse_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(collaborative_training, "MAX_DISTINCT_PAIRS", 2)
    matrix = build_binary_interaction_matrix(_golden_profiles())
    assert fit_item_item_cosine(matrix).pair_support.tolist() == [2, 2, 2, 2]
    monkeypatch.setattr(collaborative_training, "MAX_DISTINCT_PAIRS", 1)

    def forbidden(*args, **kwargs):
        pytest.fail("Distinct-pair rejection must precede the sparse product")

    monkeypatch.setattr(sparse.csc_matrix, "__matmul__", forbidden)
    with pytest.raises(CollaborativeTrainingError) as error:
        fit_item_item_cosine(matrix)
    assert error.value.code == "matrix_limit_exceeded"


@pytest.mark.parametrize("item_count", [101, 102])
def test_real_hundred_neighbor_boundary_prunes_stable_ties_without_dense_conversion(
    monkeypatch: pytest.MonkeyPatch, item_count: int
) -> None:
    def forbidden(*args, **kwargs):
        pytest.fail("Training must not convert sparse matrices to dense arrays")

    monkeypatch.setattr(sparse.csr_matrix, "toarray", forbidden)
    monkeypatch.setattr(sparse.csc_matrix, "toarray", forbidden)
    slugs = tuple(f"item-{index:03d}" for index in range(item_count))
    value = fit_item_item_cosine(build_binary_interaction_matrix((slugs,) * 2))
    assert np.diff(value.neighbor_indptr).tolist() == [100] * item_count
    for row in range(item_count):
        start, stop = value.neighbor_indptr[row : row + 2]
        assert (
            value.neighbor_indices[start:stop].tolist()
            == [index for index in range(item_count) if index != row][:100]
        )
    assert value.similarity_units.tolist() == [1_000_000] * (100 * item_count)
    assert value.pair_support.tolist() == [2] * (100 * item_count)


@pytest.mark.parametrize(
    "options",
    [
        {"maximum_neighbors": 0},
        {"maximum_neighbors": 101},
        {"maximum_neighbors": True},
        {"minimum_pair_support": 1},
        {"minimum_pair_support": 3},
    ],
)
def test_invalid_fit_configuration_rejects_before_sparse_product(
    monkeypatch: pytest.MonkeyPatch, options
) -> None:
    matrix = build_binary_interaction_matrix(_golden_profiles())

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid configuration must fail before multiplication")

    monkeypatch.setattr(sparse.csc_matrix, "__matmul__", forbidden)
    with pytest.raises(CollaborativeTrainingError) as error:
        fit_item_item_cosine(matrix, **options)
    assert error.value.code == "training_config_invalid"


def test_total_neighbor_nonzero_boundary_rejects_before_output_array_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    matrix = build_binary_interaction_matrix(_golden_profiles())
    monkeypatch.setattr(collaborative_training, "MAX_NEIGHBOR_NONZERO", 4)
    assert fit_item_item_cosine(matrix).neighbor_indices.size == 4
    monkeypatch.setattr(collaborative_training, "MAX_NEIGHBOR_NONZERO", 3)

    def forbidden(*args, **kwargs):
        pytest.fail("Retained edge limit must precede immutable output allocation")

    monkeypatch.setattr(collaborative_training, "_immutable_array", forbidden)
    with pytest.raises(CollaborativeTrainingError) as error:
        fit_item_item_cosine(matrix)
    assert error.value.code == "matrix_limit_exceeded"
