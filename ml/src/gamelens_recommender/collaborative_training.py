from __future__ import annotations

import itertools
import math
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
from scipy import sparse

from gamelens_recommender.config import SCORE_SCALE
from gamelens_recommender.interaction_snapshot import (
    MAX_DISTINCT_PAIRS,
    MAX_PAIR_CONTRIBUTIONS,
    MAX_POSITIVE_EDGES,
    MAX_PROFILES,
    MAX_UNIQUE_ITEMS,
    MIN_ITEM_SUPPORT,
    MIN_PAIR_SUPPORT,
    MIN_PROFILE_ITEMS,
    SnapshotAuditError,
    canonicalize_profiles,
    prune_supported_profiles,
)

MAX_NEIGHBORS_PER_ITEM = 100
MAX_NEIGHBOR_NONZERO = min(
    MAX_UNIQUE_ITEMS * MAX_NEIGHBORS_PER_ITEM,
    MAX_DISTINCT_PAIRS * 2,
)


class CollaborativeTrainingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class BinaryInteractionMatrix:
    matrix: sparse.csr_matrix
    item_slugs: tuple[str, ...]
    item_support: np.ndarray
    retained_contributors: int
    retained_positive_edges: int
    pair_contributions: int


@dataclass(frozen=True)
class CollaborativeNeighborhoods:
    item_slugs: tuple[str, ...]
    item_support: np.ndarray
    neighbor_indices: np.ndarray
    neighbor_indptr: np.ndarray
    similarity_units: np.ndarray
    pair_support: np.ndarray
    retained_contributors: int
    retained_positive_edges: int
    pair_contributions: int


def _canonicalize_training_profiles(
    profiles: Iterable[Iterable[str]],
) -> tuple[tuple[str, ...], ...]:
    canonical: list[tuple[str, ...]] = []
    distinct_items: set[str] = set()
    raw_positive_entries = 0
    positive_edges = 0
    try:
        for raw_profile in profiles:
            if isinstance(raw_profile, (str, bytes)):
                raise CollaborativeTrainingError(
                    "snapshot_invalid", "A contributor profile must be an iterable of slugs"
                )
            values: set[str] = set()
            for value in raw_profile:
                raw_positive_entries += 1
                if raw_positive_entries > MAX_POSITIVE_EDGES:
                    raise CollaborativeTrainingError(
                        "snapshot_limit_exceeded", "Raw positive entry limit exceeded"
                    )
                if not isinstance(value, str) or not value or value != value.strip():
                    raise CollaborativeTrainingError(
                        "snapshot_invalid", "Game slugs must be non-empty trimmed strings"
                    )
                values.add(value)
                if len(values) > MAX_UNIQUE_ITEMS:
                    raise CollaborativeTrainingError(
                        "snapshot_limit_exceeded", "Unique item limit exceeded"
                    )
            profile = tuple(sorted(values))
            positive_edges += len(profile)
            if positive_edges > MAX_POSITIVE_EDGES:
                raise CollaborativeTrainingError(
                    "snapshot_limit_exceeded", "Positive edge limit exceeded"
                )
            distinct_items.update(profile)
            if len(distinct_items) > MAX_UNIQUE_ITEMS:
                raise CollaborativeTrainingError(
                    "snapshot_limit_exceeded", "Unique item limit exceeded"
                )
            canonical.append(profile)
            if len(canonical) > MAX_PROFILES:
                raise CollaborativeTrainingError(
                    "snapshot_limit_exceeded", "Contributor profile limit exceeded"
                )
    except CollaborativeTrainingError:
        raise
    except TypeError as error:
        raise CollaborativeTrainingError(
            "snapshot_invalid", "Contributor profiles must be iterable"
        ) from error
    return tuple(sorted(canonical))


def _strictly_increasing_rows(indices: np.ndarray, indptr: np.ndarray) -> bool:
    for start, stop in zip(indptr[:-1], indptr[1:], strict=True):
        row = indices[int(start) : int(stop)]
        if row.size > 1 and np.any(row[1:] <= row[:-1]):
            return False
    return True


def _canonical_item_axis(value: object) -> bool:
    return (
        isinstance(value, tuple)
        and bool(value)
        and all(isinstance(slug, str) and bool(slug) and slug == slug.strip() for slug in value)
        and len(set(value)) == len(value)
        and value == tuple(sorted(value))
    )


def _immutable_array(value: np.ndarray, dtype: np.dtype[object]) -> np.ndarray:
    contiguous = np.ascontiguousarray(value, dtype=dtype)
    return np.frombuffer(contiguous.tobytes(), dtype=dtype).reshape(contiguous.shape)


def _freeze_matrix(value: BinaryInteractionMatrix) -> None:
    for array in (
        value.matrix.data,
        value.matrix.indices,
        value.matrix.indptr,
        value.item_support,
    ):
        array.flags.writeable = False


def _freeze_neighborhoods(value: CollaborativeNeighborhoods) -> None:
    for array in (
        value.item_support,
        value.neighbor_indices,
        value.neighbor_indptr,
        value.similarity_units,
        value.pair_support,
    ):
        array.flags.writeable = False


def build_binary_interaction_matrix(
    profiles: Iterable[Iterable[str]],
) -> BinaryInteractionMatrix:
    """Build the canonical support-pruned binary contributor-item matrix."""

    canonical = _canonicalize_training_profiles(profiles)
    supported = prune_supported_profiles(canonical)
    if not supported.profiles or not supported.item_support:
        raise CollaborativeTrainingError(
            "insufficient_data", "No contributor-item two-core satisfies support thresholds"
        )

    item_slugs = tuple(item for item, _support in supported.item_support)
    slug_to_column = {slug: column for column, slug in enumerate(item_slugs)}
    retained_positive_edges = sum(len(profile) for profile in supported.profiles)
    if retained_positive_edges > MAX_POSITIVE_EDGES:
        raise CollaborativeTrainingError(
            "matrix_limit_exceeded", "Retained positive edge limit exceeded"
        )
    pair_contributions = sum(
        len(profile) * (len(profile) - 1) // 2 for profile in supported.profiles
    )
    if pair_contributions > MAX_PAIR_CONTRIBUTIONS:
        raise CollaborativeTrainingError(
            "matrix_limit_exceeded", "Pair contribution limit exceeded"
        )

    indices = np.empty(retained_positive_edges, dtype=np.int32)
    indptr = np.empty(len(supported.profiles) + 1, dtype=np.int32)
    indptr[0] = 0
    cursor = 0
    for row, profile in enumerate(supported.profiles):
        columns = tuple(slug_to_column[slug] for slug in profile)
        next_cursor = cursor + len(columns)
        indices[cursor:next_cursor] = columns
        indptr[row + 1] = next_cursor
        cursor = next_cursor

    data = np.ones(retained_positive_edges, dtype=np.int64)
    matrix = sparse.csr_matrix(
        (data, indices, indptr),
        shape=(len(supported.profiles), len(item_slugs)),
        dtype=np.int64,
    )
    item_support = np.asarray(
        [support for _item, support in supported.item_support], dtype=np.int64
    )
    result = BinaryInteractionMatrix(
        matrix=matrix,
        item_slugs=item_slugs,
        item_support=item_support,
        retained_contributors=len(supported.profiles),
        retained_positive_edges=retained_positive_edges,
        pair_contributions=pair_contributions,
    )
    validate_binary_interaction_matrix(result)
    _freeze_matrix(result)
    return result


def validate_binary_interaction_matrix(value: BinaryInteractionMatrix) -> None:
    matrix = value.matrix
    if not sparse.isspmatrix_csr(matrix) or matrix.ndim != 2:
        raise CollaborativeTrainingError(
            "matrix_format_invalid", "Interaction matrix must be two-dimensional CSR"
        )
    item_count = len(value.item_slugs)
    if not _canonical_item_axis(value.item_slugs):
        raise CollaborativeTrainingError(
            "matrix_shape_invalid", "Item slugs must be non-empty, unique, and canonical"
        )
    if item_count > MAX_UNIQUE_ITEMS or matrix.shape != (
        value.retained_contributors,
        item_count,
    ):
        raise CollaborativeTrainingError(
            "matrix_shape_invalid", "Interaction matrix shape is inconsistent"
        )
    if (
        not isinstance(value.item_support, np.ndarray)
        or matrix.data.dtype != np.dtype(np.int64)
        or matrix.indices.dtype != np.dtype(np.int32)
        or matrix.indptr.dtype != np.dtype(np.int32)
        or value.item_support.dtype != np.dtype(np.int64)
    ):
        raise CollaborativeTrainingError(
            "matrix_dtype_invalid", "Interaction matrix dtypes are incompatible"
        )
    if value.item_support.ndim != 1 or value.item_support.shape != (item_count,):
        raise CollaborativeTrainingError(
            "matrix_shape_invalid", "Item support shape is inconsistent"
        )
    try:
        matrix.check_format(full_check=True)
    except (TypeError, ValueError) as error:
        raise CollaborativeTrainingError(
            "matrix_format_invalid", "Interaction CSR structure is invalid"
        ) from error
    if not _strictly_increasing_rows(matrix.indices, matrix.indptr):
        raise CollaborativeTrainingError(
            "matrix_format_invalid", "Interaction CSR rows are not canonical"
        )
    if matrix.nnz != value.retained_positive_edges or not np.all(matrix.data == 1):
        raise CollaborativeTrainingError(
            "matrix_numeric_invalid", "Interaction matrix must contain exact binary values"
        )
    if (
        type(value.retained_contributors) is not int
        or not 1 <= value.retained_contributors <= MAX_PROFILES
        or type(value.retained_positive_edges) is not int
        or not 1 <= value.retained_positive_edges <= MAX_POSITIVE_EDGES
        or type(value.pair_contributions) is not int
        or not 0 <= value.pair_contributions <= MAX_PAIR_CONTRIBUTIONS
    ):
        raise CollaborativeTrainingError(
            "matrix_limit_exceeded", "Interaction matrix counts exceed resource limits"
        )
    row_sizes = np.diff(matrix.indptr).astype(np.int64, copy=False)
    if row_sizes.size != value.retained_contributors or np.any(row_sizes < MIN_PROFILE_ITEMS):
        raise CollaborativeTrainingError(
            "matrix_numeric_invalid", "Retained contributor support is invalid"
        )
    observed_support = np.asarray(matrix.sum(axis=0)).reshape(-1)
    if (
        observed_support.dtype != np.dtype(np.int64)
        or np.any(value.item_support < MIN_ITEM_SUPPORT)
        or not np.array_equal(observed_support, value.item_support)
        or int(value.item_support.sum()) != value.retained_positive_edges
    ):
        raise CollaborativeTrainingError(
            "matrix_numeric_invalid", "Item support does not match the interaction matrix"
        )
    observed_pair_contributions = sum(int(size) * (int(size) - 1) // 2 for size in row_sizes)
    if observed_pair_contributions != value.pair_contributions:
        raise CollaborativeTrainingError(
            "matrix_numeric_invalid", "Pair contribution count is inconsistent"
        )
    distinct_pairs: set[tuple[int, int]] = set()
    for start, stop in zip(matrix.indptr[:-1], matrix.indptr[1:], strict=True):
        row = matrix.indices[int(start) : int(stop)]
        for left, right in itertools.combinations(row, 2):
            distinct_pairs.add((int(left), int(right)))
            if len(distinct_pairs) > MAX_DISTINCT_PAIRS:
                raise CollaborativeTrainingError(
                    "matrix_limit_exceeded", "Distinct item-pair limit exceeded"
                )


def quantize_similarity(value: float | np.floating[object], *, scale: int = SCORE_SCALE) -> int:
    """Quantize one bounded float64 cosine with decimal round-half-up."""

    try:
        numeric = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise CollaborativeTrainingError(
            "similarity_invalid", "Cosine similarity must be numeric"
        ) from error
    if (
        type(scale) is not int
        or scale <= 0
        or scale > np.iinfo(np.int32).max
        or not math.isfinite(numeric)
        or not 0.0 <= numeric <= 1.0
    ):
        raise CollaborativeTrainingError(
            "similarity_invalid", "Cosine similarity and scale must be finite and bounded"
        )
    return int(
        (Decimal(str(numeric)) * Decimal(scale)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def fit_item_item_cosine(
    value: BinaryInteractionMatrix,
    *,
    minimum_pair_support: int = MIN_PAIR_SUPPORT,
    maximum_neighbors: int = MAX_NEIGHBORS_PER_ITEM,
) -> CollaborativeNeighborhoods:
    """Fit deterministic top-neighbor item-item cosine neighborhoods."""

    validate_binary_interaction_matrix(value)
    if (
        type(minimum_pair_support) is not int
        or minimum_pair_support != MIN_PAIR_SUPPORT
        or type(maximum_neighbors) is not int
        or not 1 <= maximum_neighbors <= MAX_NEIGHBORS_PER_ITEM
    ):
        raise CollaborativeTrainingError(
            "training_config_invalid", "Collaborative support or neighbor limit is invalid"
        )
    try:
        co_positive = (value.matrix.T @ value.matrix).tocsr()
        co_positive.sum_duplicates()
        co_positive.sort_indices()
        co_positive.check_format(full_check=True)
    except (MemoryError, TypeError, ValueError) as error:
        raise CollaborativeTrainingError(
            "matrix_numeric_invalid", "Sparse pair-support computation failed"
        ) from error
    if co_positive.dtype != np.dtype(np.int64):
        raise CollaborativeTrainingError(
            "matrix_dtype_invalid", "Pair-support arithmetic did not preserve int64"
        )
    off_diagonal_nonzero = int(
        sum(
            np.count_nonzero(co_positive.indices[int(start) : int(stop)] != row)
            for row, (start, stop) in enumerate(
                zip(co_positive.indptr[:-1], co_positive.indptr[1:], strict=True)
            )
        )
    )
    if off_diagonal_nonzero > MAX_DISTINCT_PAIRS * 2:
        raise CollaborativeTrainingError(
            "matrix_limit_exceeded", "Distinct item-pair limit exceeded"
        )

    neighbor_indices: list[int] = []
    similarity_units: list[int] = []
    pair_support_values: list[int] = []
    neighbor_indptr = [0]
    for item_index, (start, stop) in enumerate(
        zip(co_positive.indptr[:-1], co_positive.indptr[1:], strict=True)
    ):
        candidates: list[tuple[int, int, int]] = []
        left_support = int(value.item_support[item_index])
        for offset in range(int(start), int(stop)):
            neighbor_index = int(co_positive.indices[offset])
            if neighbor_index == item_index:
                continue
            support = int(co_positive.data[offset])
            if support < minimum_pair_support:
                continue
            right_support = int(value.item_support[neighbor_index])
            if support > min(left_support, right_support):
                raise CollaborativeTrainingError(
                    "matrix_numeric_invalid", "Pair support exceeds item support"
                )
            denominator = np.sqrt(np.float64(left_support) * np.float64(right_support))
            similarity = np.float64(support) / denominator
            units = quantize_similarity(similarity)
            candidates.append((neighbor_index, units, support))

        candidates.sort(
            key=lambda candidate: (
                -candidate[1],
                -candidate[2],
                value.item_slugs[candidate[0]],
            )
        )
        retained = candidates[:maximum_neighbors]
        retained.sort(key=lambda candidate: candidate[0])
        for neighbor_index, units, support in retained:
            neighbor_indices.append(neighbor_index)
            similarity_units.append(units)
            pair_support_values.append(support)
        neighbor_indptr.append(len(neighbor_indices))
        if len(neighbor_indices) > MAX_NEIGHBOR_NONZERO:
            raise CollaborativeTrainingError(
                "matrix_limit_exceeded", "Retained neighborhood limit exceeded"
            )

    if not neighbor_indices:
        raise CollaborativeTrainingError(
            "insufficient_data", "No item pair satisfies the minimum pair support"
        )
    result = CollaborativeNeighborhoods(
        item_slugs=value.item_slugs,
        item_support=_immutable_array(value.item_support, np.dtype(np.int64)),
        neighbor_indices=_immutable_array(np.asarray(neighbor_indices), np.dtype(np.int32)),
        neighbor_indptr=_immutable_array(np.asarray(neighbor_indptr), np.dtype(np.int32)),
        similarity_units=_immutable_array(np.asarray(similarity_units), np.dtype(np.int32)),
        pair_support=_immutable_array(np.asarray(pair_support_values), np.dtype(np.int64)),
        retained_contributors=value.retained_contributors,
        retained_positive_edges=value.retained_positive_edges,
        pair_contributions=value.pair_contributions,
    )
    validate_collaborative_neighborhoods(result)
    _freeze_neighborhoods(result)
    return result


def validate_collaborative_neighborhoods(value: CollaborativeNeighborhoods) -> None:
    item_count = len(value.item_slugs)
    if item_count > MAX_UNIQUE_ITEMS or not _canonical_item_axis(value.item_slugs):
        raise CollaborativeTrainingError(
            "neighborhood_shape_invalid", "Neighborhood item axis is not canonical"
        )
    arrays = (
        value.item_support,
        value.neighbor_indices,
        value.neighbor_indptr,
        value.similarity_units,
        value.pair_support,
    )
    if any(not isinstance(array, np.ndarray) or array.ndim != 1 for array in arrays):
        raise CollaborativeTrainingError(
            "neighborhood_shape_invalid", "Neighborhood arrays must be one-dimensional"
        )
    if (
        value.item_support.dtype != np.dtype(np.int64)
        or value.neighbor_indices.dtype != np.dtype(np.int32)
        or value.neighbor_indptr.dtype != np.dtype(np.int32)
        or value.similarity_units.dtype != np.dtype(np.int32)
        or value.pair_support.dtype != np.dtype(np.int64)
    ):
        raise CollaborativeTrainingError(
            "neighborhood_dtype_invalid", "Neighborhood array dtypes are incompatible"
        )
    nonzero = value.neighbor_indices.size
    if (
        value.item_support.shape != (item_count,)
        or value.neighbor_indptr.shape != (item_count + 1,)
        or value.similarity_units.shape != (nonzero,)
        or value.pair_support.shape != (nonzero,)
    ):
        raise CollaborativeTrainingError(
            "neighborhood_shape_invalid", "Neighborhood array shapes are inconsistent"
        )
    if (
        nonzero == 0
        or nonzero > MAX_NEIGHBOR_NONZERO
        or int(value.neighbor_indptr[0]) != 0
        or int(value.neighbor_indptr[-1]) != nonzero
        or np.any(value.neighbor_indptr[1:] < value.neighbor_indptr[:-1])
    ):
        raise CollaborativeTrainingError(
            "neighborhood_format_invalid", "Neighborhood row pointers are invalid"
        )
    if (
        np.any(value.neighbor_indices < 0)
        or np.any(value.neighbor_indices >= item_count)
        or not _strictly_increasing_rows(value.neighbor_indices, value.neighbor_indptr)
    ):
        raise CollaborativeTrainingError(
            "neighborhood_format_invalid", "Neighborhood indices are not canonical"
        )
    row_sizes = np.diff(value.neighbor_indptr).astype(np.int64, copy=False)
    if np.any(row_sizes > MAX_NEIGHBORS_PER_ITEM):
        raise CollaborativeTrainingError(
            "neighborhood_limit_exceeded", "An item exceeds the neighbor limit"
        )
    if (
        np.any(value.item_support < MIN_ITEM_SUPPORT)
        or np.any(value.item_support > MAX_PROFILES)
        or np.any(value.similarity_units <= 0)
        or np.any(value.similarity_units > SCORE_SCALE)
        or np.any(value.pair_support < MIN_PAIR_SUPPORT)
    ):
        raise CollaborativeTrainingError(
            "neighborhood_numeric_invalid", "Neighborhood values are out of bounds"
        )
    if (
        type(value.retained_contributors) is not int
        or not 1 <= value.retained_contributors <= MAX_PROFILES
        or type(value.retained_positive_edges) is not int
        or not 1 <= value.retained_positive_edges <= MAX_POSITIVE_EDGES
        or type(value.pair_contributions) is not int
        or not 0 <= value.pair_contributions <= MAX_PAIR_CONTRIBUTIONS
        or int(value.item_support.sum()) != value.retained_positive_edges
        or value.retained_positive_edges < MIN_PROFILE_ITEMS * value.retained_contributors
        or value.retained_positive_edges > value.retained_contributors * item_count
        or np.any(value.item_support > value.retained_contributors)
    ):
        raise CollaborativeTrainingError(
            "neighborhood_limit_exceeded", "Neighborhood aggregate counts are invalid"
        )
    if value.pair_contributions < value.retained_contributors:
        raise CollaborativeTrainingError(
            "neighborhood_numeric_invalid", "Pair contribution count is inconsistent"
        )
    maximum_pair_contributions = value.retained_contributors * item_count * (item_count - 1) // 2
    if value.pair_contributions > maximum_pair_contributions:
        raise CollaborativeTrainingError(
            "neighborhood_numeric_invalid", "Pair contribution count is inconsistent"
        )

    retained_pair_support = 0
    for item_index, (start, stop) in enumerate(
        zip(value.neighbor_indptr[:-1], value.neighbor_indptr[1:], strict=True)
    ):
        left_support = int(value.item_support[item_index])
        for offset in range(int(start), int(stop)):
            neighbor_index = int(value.neighbor_indices[offset])
            if neighbor_index == item_index:
                raise CollaborativeTrainingError(
                    "neighborhood_format_invalid", "Self-neighbors are prohibited"
                )
            support = int(value.pair_support[offset])
            right_support = int(value.item_support[neighbor_index])
            if support > min(left_support, right_support):
                raise CollaborativeTrainingError(
                    "neighborhood_numeric_invalid", "Pair support exceeds item support"
                )
            similarity = np.float64(support) / np.sqrt(
                np.float64(left_support) * np.float64(right_support)
            )
            if quantize_similarity(similarity) != int(value.similarity_units[offset]):
                raise CollaborativeTrainingError(
                    "neighborhood_numeric_invalid",
                    "Quantized cosine does not match recorded support",
                )
            if neighbor_index > item_index:
                reverse_start = int(value.neighbor_indptr[neighbor_index])
                reverse_stop = int(value.neighbor_indptr[neighbor_index + 1])
                reverse_indices = value.neighbor_indices[reverse_start:reverse_stop]
                reverse_position = int(np.searchsorted(reverse_indices, item_index))
                if (
                    reverse_position < len(reverse_indices)
                    and int(reverse_indices[reverse_position]) == item_index
                ):
                    reverse_offset = reverse_start + reverse_position
                    if (
                        value.pair_support[offset] != value.pair_support[reverse_offset]
                        or value.similarity_units[offset] != value.similarity_units[reverse_offset]
                    ):
                        raise CollaborativeTrainingError(
                            "neighborhood_numeric_invalid",
                            "Mutual collaborative neighbors are inconsistent",
                        )
            retained_pair_support += support
    if retained_pair_support > 2 * value.pair_contributions:
        raise CollaborativeTrainingError(
            "neighborhood_numeric_invalid",
            "Retained pair support exceeds pair contributions",
        )


def fit_collaborative_neighborhoods(
    profiles: Iterable[Iterable[str]],
    *,
    catalog_slugs: frozenset[str],
) -> CollaborativeNeighborhoods:
    """Canonicalize an eligible snapshot and fit its sparse neighborhoods."""

    normalized = _canonicalize_training_profiles(profiles)
    try:
        canonical = canonicalize_profiles(normalized, catalog_slugs=catalog_slugs)
    except SnapshotAuditError as error:
        raise CollaborativeTrainingError(error.code, str(error)) from error
    return fit_item_item_cosine(build_binary_interaction_matrix(canonical))
