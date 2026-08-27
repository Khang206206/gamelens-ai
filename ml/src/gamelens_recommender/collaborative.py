from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from gamelens_recommender.collaborative_artifacts import MAX_GAME_SLUG_LENGTH
from gamelens_recommender.collaborative_training import MAX_NEIGHBORS_PER_ITEM
from gamelens_recommender.config import SCORE_SCALE
from gamelens_recommender.interaction_snapshot import MAX_PROFILES, MAX_UNIQUE_ITEMS
from gamelens_recommender.schemas import SLUG_PATTERN, PositiveFeedbackSource

CollaborativeQuerySourceKind = Literal["liked", "rating", "saved_game"]
CollaborativeScoringReason = Literal[
    "recommendations",
    "no_query_sources",
    "no_supported_sources",
    "no_candidate_edges",
    "no_eligible_candidates",
]

COLLABORATIVE_SCORING_POLICY_NAME = "gamelens-collaborative-scoring"
COLLABORATIVE_SCORING_POLICY_VERSION = "1.0.0"


class CollaborativeScoringError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _contract_error(code: str, message: str) -> None:
    raise CollaborativeScoringError(code, message)


def _validate_slug(
    value: object,
    *,
    label: str,
    code: str = "scoring_input_invalid",
) -> str:
    if (
        type(value) is not str
        or len(value) > MAX_GAME_SLUG_LENGTH
        or SLUG_PATTERN.fullmatch(value) is None
    ):
        _contract_error(code, f"{label} must be a canonical game slug")
    return value


def _validate_slug_tuple(
    value: object,
    *,
    label: str,
    maximum: int,
    require_distinct: bool = True,
    require_sorted: bool = False,
    code: str = "scoring_input_invalid",
) -> tuple[str, ...]:
    if type(value) is not tuple or len(value) > maximum:
        _contract_error(code, f"{label} must be a bounded immutable tuple")
    slugs = tuple(_validate_slug(slug, label=label, code=code) for slug in value)
    if require_distinct and len(slugs) != len(set(slugs)):
        _contract_error(code, f"{label} must contain distinct game slugs")
    if require_sorted and slugs != tuple(sorted(slugs)):
        _contract_error(code, f"{label} must use canonical slug order")
    return slugs


def _validate_aware_datetime(value: object, *, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        _contract_error("scoring_input_invalid", f"{label} must be timezone-aware")
    return value


def _validate_bounded_int(
    value: object,
    *,
    label: str,
    minimum: int,
    maximum: int,
    code: str = "scoring_result_invalid",
) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        _contract_error(code, f"{label} is outside its integer bound")
    return value


@dataclass(frozen=True)
class CollaborativeScoringIdentity:
    name: str
    version: str


@dataclass(frozen=True)
class CollaborativeScoringConfig:
    name: str = COLLABORATIVE_SCORING_POLICY_NAME
    version: str = COLLABORATIVE_SCORING_POLICY_VERSION
    score_scale: int = SCORE_SCALE
    max_positive_sources: int = 5
    max_saved_game_sources: int = 5
    max_query_sources: int = 10
    max_neighbors_per_source: int = MAX_NEIGHBORS_PER_ITEM
    max_visited_edges: int = 1_000
    max_candidates: int = 1_000
    max_disliked_slugs: int = MAX_UNIQUE_ITEMS
    max_source_state_entries: int = MAX_UNIQUE_ITEMS
    source_precedence: tuple[str, ...] = ("dislike", "liked", "rating", "saved_game")
    aggregation: str = "available_similarity_mean_round_half_up"
    evidence_order: tuple[str, ...] = (
        "similarity_units_desc",
        "pair_support_desc",
        "source_slug_asc",
    )
    candidate_order: tuple[str, ...] = (
        "collaborative_score_units_desc",
        "slug_asc",
    )

    @property
    def identity(self) -> CollaborativeScoringIdentity:
        return CollaborativeScoringIdentity(name=self.name, version=self.version)

    def validate(self) -> None:
        if (
            self.name,
            self.version,
            self.score_scale,
            self.max_positive_sources,
            self.max_saved_game_sources,
            self.max_query_sources,
            self.max_neighbors_per_source,
            self.max_visited_edges,
            self.max_candidates,
            self.max_disliked_slugs,
            self.max_source_state_entries,
            self.source_precedence,
            self.aggregation,
            self.evidence_order,
            self.candidate_order,
        ) != (
            COLLABORATIVE_SCORING_POLICY_NAME,
            COLLABORATIVE_SCORING_POLICY_VERSION,
            SCORE_SCALE,
            5,
            5,
            10,
            MAX_NEIGHBORS_PER_ITEM,
            1_000,
            1_000,
            MAX_UNIQUE_ITEMS,
            MAX_UNIQUE_ITEMS,
            ("dislike", "liked", "rating", "saved_game"),
            "available_similarity_mean_round_half_up",
            (
                "similarity_units_desc",
                "pair_support_desc",
                "source_slug_asc",
            ),
            ("collaborative_score_units_desc", "slug_asc"),
        ):
            _contract_error(
                "scoring_config_invalid",
                "Collaborative scoring configuration does not match policy version 1.0.0",
            )


COLLABORATIVE_SCORING_CONFIG = CollaborativeScoringConfig()


@dataclass(frozen=True)
class CollaborativeSourceState:
    positive_sources: tuple[PositiveFeedbackSource, ...] = ()
    saved_game_slugs: tuple[str, ...] = ()
    disliked_slugs: tuple[str, ...] = ()

    def validate(self, config: CollaborativeScoringConfig = COLLABORATIVE_SCORING_CONFIG) -> None:
        config.validate()
        if (
            type(self.positive_sources) is not tuple
            or len(self.positive_sources) > config.max_source_state_entries
        ):
            _contract_error(
                "scoring_input_invalid",
                "Positive feedback sources must be a bounded immutable tuple",
            )
        for source in self.positive_sources:
            if (
                type(source) is not PositiveFeedbackSource
                or type(source.kind) is not str
                or source.kind not in ("liked", "rating")
            ):
                _contract_error(
                    "scoring_input_invalid",
                    "Positive feedback source kind is invalid",
                )
            _validate_slug(source.game_slug, label="Positive feedback source")
            _validate_aware_datetime(source.occurred_at, label="Positive feedback occurrence")
        _validate_slug_tuple(
            self.saved_game_slugs,
            label="Saved game sources",
            maximum=config.max_source_state_entries,
            require_distinct=False,
        )
        _validate_slug_tuple(
            self.disliked_slugs,
            label="Disliked game exclusions",
            maximum=config.max_disliked_slugs,
            require_distinct=False,
        )


@dataclass(frozen=True)
class CollaborativeQuerySource:
    game_slug: str
    kind: CollaborativeQuerySourceKind

    def validate(self, *, code: str = "scoring_input_invalid") -> None:
        _validate_slug(self.game_slug, label="Collaborative query source", code=code)
        if self.kind not in {"liked", "rating", "saved_game"}:
            _contract_error(code, "Collaborative query source kind is invalid")


@dataclass(frozen=True)
class CollaborativeQueryContext:
    sources: tuple[CollaborativeQuerySource, ...] = ()
    disliked_slugs: tuple[str, ...] = ()

    def validate(self, config: CollaborativeScoringConfig = COLLABORATIVE_SCORING_CONFIG) -> None:
        config.validate()
        if type(self.sources) is not tuple or len(self.sources) > config.max_query_sources:
            _contract_error(
                "scoring_input_invalid",
                "Collaborative query sources must be a bounded immutable tuple",
            )
        for source in self.sources:
            if type(source) is not CollaborativeQuerySource:
                _contract_error(
                    "scoring_input_invalid",
                    "Collaborative query source contains an invalid value",
                )
            source.validate()
        source_slugs = tuple(source.game_slug for source in self.sources)
        if len(source_slugs) != len(set(source_slugs)):
            _contract_error(
                "scoring_input_invalid",
                "Canonical collaborative query source slugs must be distinct",
            )
        disliked = _validate_slug_tuple(
            self.disliked_slugs,
            label="Canonical disliked game exclusions",
            maximum=config.max_disliked_slugs,
            require_sorted=True,
        )
        if set(source_slugs) & set(disliked):
            _contract_error(
                "scoring_input_invalid",
                "Canonical collaborative query sources must exclude dislikes",
            )


def canonicalize_collaborative_query_sources(
    state: CollaborativeSourceState,
    config: CollaborativeScoringConfig = COLLABORATIVE_SCORING_CONFIG,
) -> CollaborativeQueryContext:
    """Select deterministic, bounded query sources without artifact access."""

    config.validate()
    if type(state) is not CollaborativeSourceState:
        _contract_error(
            "scoring_input_invalid",
            "Collaborative source state has an invalid type",
        )
    state.validate(config)

    disliked_slugs = tuple(sorted(set(state.disliked_slugs)))
    disliked = set(disliked_slugs)
    positive_by_slug: dict[str, PositiveFeedbackSource] = {}
    positive_kind_order = {kind: position for position, kind in enumerate(config.source_precedence)}
    for source in state.positive_sources:
        if source.game_slug in disliked:
            continue
        current = positive_by_slug.get(source.game_slug)
        if current is None:
            positive_by_slug[source.game_slug] = source
            continue
        source_precedence = positive_kind_order[source.kind]
        current_precedence = positive_kind_order[current.kind]
        if source_precedence < current_precedence or (
            source_precedence == current_precedence
            and source.occurred_at.astimezone(UTC) > current.occurred_at.astimezone(UTC)
        ):
            positive_by_slug[source.game_slug] = source

    ordered_positive = sorted(positive_by_slug.values(), key=lambda source: source.game_slug)
    ordered_positive.sort(
        key=lambda source: source.occurred_at.astimezone(UTC),
        reverse=True,
    )
    selected_positive = ordered_positive[: config.max_positive_sources]
    positive_sources = tuple(
        CollaborativeQuerySource(game_slug=source.game_slug, kind=source.kind)
        for source in selected_positive
    )

    saved_slugs = sorted(set(state.saved_game_slugs) - disliked - set(positive_by_slug))[
        : config.max_saved_game_sources
    ]
    saved_sources = tuple(
        CollaborativeQuerySource(game_slug=slug, kind="saved_game") for slug in saved_slugs
    )
    context = CollaborativeQueryContext(
        sources=positive_sources + saved_sources,
        disliked_slugs=disliked_slugs,
    )
    context.validate(config)
    return context


@dataclass(frozen=True)
class CollaborativeSourceEdge:
    source_slug: str
    source_kind: CollaborativeQuerySourceKind
    candidate_slug: str
    similarity_units: int
    pair_support: int

    def validate(self, config: CollaborativeScoringConfig = COLLABORATIVE_SCORING_CONFIG) -> None:
        config.validate()
        source_slug = _validate_slug(
            self.source_slug,
            label="Collaborative edge source",
            code="scoring_result_invalid",
        )
        candidate_slug = _validate_slug(
            self.candidate_slug,
            label="Collaborative edge candidate",
            code="scoring_result_invalid",
        )
        if source_slug == candidate_slug:
            _contract_error("scoring_result_invalid", "Collaborative self-edge is invalid")
        if self.source_kind not in {"liked", "rating", "saved_game"}:
            _contract_error("scoring_result_invalid", "Collaborative edge source kind is invalid")
        _validate_bounded_int(
            self.similarity_units,
            label="Collaborative edge similarity",
            minimum=1,
            maximum=config.score_scale,
        )
        _validate_bounded_int(
            self.pair_support,
            label="Collaborative edge pair support",
            minimum=2,
            maximum=MAX_PROFILES,
        )


@dataclass(frozen=True)
class CollaborativeCandidateScore:
    slug: str
    collaborative_score_units: int
    item_support: int
    source_edges: tuple[CollaborativeSourceEdge, ...]

    def validate(self, config: CollaborativeScoringConfig = COLLABORATIVE_SCORING_CONFIG) -> None:
        config.validate()
        slug = _validate_slug(
            self.slug,
            label="Collaborative candidate",
            code="scoring_result_invalid",
        )
        _validate_bounded_int(
            self.collaborative_score_units,
            label="Collaborative candidate score",
            minimum=1,
            maximum=config.score_scale,
        )
        _validate_bounded_int(
            self.item_support,
            label="Collaborative candidate item support",
            minimum=2,
            maximum=MAX_PROFILES,
        )
        if (
            type(self.source_edges) is not tuple
            or not self.source_edges
            or len(self.source_edges) > config.max_query_sources
        ):
            _contract_error(
                "scoring_result_invalid",
                "Collaborative candidate edges must be a bounded non-empty tuple",
            )
        for edge in self.source_edges:
            if type(edge) is not CollaborativeSourceEdge:
                _contract_error(
                    "scoring_result_invalid",
                    "Collaborative candidate edge contains an invalid value",
                )
            edge.validate(config)
            if edge.candidate_slug != slug:
                _contract_error(
                    "scoring_result_invalid",
                    "Collaborative candidate edge targets are inconsistent",
                )
        source_slugs = tuple(edge.source_slug for edge in self.source_edges)
        if len(source_slugs) != len(set(source_slugs)):
            _contract_error(
                "scoring_result_invalid",
                "Collaborative candidate source edges must be distinct",
            )
        if self.source_edges != tuple(
            sorted(
                self.source_edges,
                key=lambda edge: (
                    -edge.similarity_units,
                    -edge.pair_support,
                    edge.source_slug,
                ),
            )
        ):
            _contract_error(
                "scoring_result_invalid",
                "Collaborative candidate evidence order is invalid",
            )


@dataclass(frozen=True)
class CollaborativeScoringDiagnostics:
    query_source_count: int
    supported_source_count: int
    unsupported_source_count: int
    zero_degree_source_count: int
    visited_edge_count: int
    candidate_count_before_exclusions: int
    query_source_exclusion_count: int
    dislike_exclusion_count: int
    returned_candidate_count: int

    def validate(self, config: CollaborativeScoringConfig = COLLABORATIVE_SCORING_CONFIG) -> None:
        config.validate()
        _validate_bounded_int(
            self.query_source_count,
            label="Collaborative query source count",
            minimum=0,
            maximum=config.max_query_sources,
        )
        for label, value in (
            ("Collaborative supported source count", self.supported_source_count),
            ("Collaborative unsupported source count", self.unsupported_source_count),
            ("Collaborative zero-degree source count", self.zero_degree_source_count),
        ):
            _validate_bounded_int(
                value,
                label=label,
                minimum=0,
                maximum=config.max_query_sources,
            )
        for label, value in (
            ("Collaborative visited edge count", self.visited_edge_count),
            (
                "Collaborative candidate count before exclusions",
                self.candidate_count_before_exclusions,
            ),
            ("Collaborative query source exclusion count", self.query_source_exclusion_count),
            ("Collaborative dislike exclusion count", self.dislike_exclusion_count),
            ("Collaborative returned candidate count", self.returned_candidate_count),
        ):
            _validate_bounded_int(
                value,
                label=label,
                minimum=0,
                maximum=config.max_candidates,
            )
        if self.supported_source_count + self.unsupported_source_count != self.query_source_count:
            _contract_error(
                "scoring_result_invalid",
                "Collaborative source diagnostic counts are inconsistent",
            )
        if self.zero_degree_source_count > self.supported_source_count:
            _contract_error(
                "scoring_result_invalid",
                "Collaborative zero-degree source count is inconsistent",
            )
        if self.candidate_count_before_exclusions > self.visited_edge_count:
            _contract_error(
                "scoring_result_invalid",
                "Collaborative candidate and edge counts are inconsistent",
            )
        if self.candidate_count_before_exclusions != (
            self.query_source_exclusion_count
            + self.dislike_exclusion_count
            + self.returned_candidate_count
        ):
            _contract_error(
                "scoring_result_invalid",
                "Collaborative exclusion diagnostic counts are inconsistent",
            )


@dataclass(frozen=True)
class CollaborativeScoringResult:
    reason: CollaborativeScoringReason
    identity: CollaborativeScoringIdentity
    query_sources: tuple[CollaborativeQuerySource, ...]
    supported_source_slugs: tuple[str, ...]
    unsupported_source_slugs: tuple[str, ...]
    candidates: tuple[CollaborativeCandidateScore, ...]
    diagnostics: CollaborativeScoringDiagnostics

    def validate(self, config: CollaborativeScoringConfig = COLLABORATIVE_SCORING_CONFIG) -> None:
        config.validate()
        if self.reason not in {
            "recommendations",
            "no_query_sources",
            "no_supported_sources",
            "no_candidate_edges",
            "no_eligible_candidates",
        }:
            _contract_error("scoring_result_invalid", "Collaborative scoring reason is invalid")
        if (
            type(self.identity) is not CollaborativeScoringIdentity
            or self.identity != config.identity
        ):
            _contract_error("scoring_result_invalid", "Collaborative scoring identity is invalid")
        if (
            type(self.query_sources) is not tuple
            or len(self.query_sources) > config.max_query_sources
        ):
            _contract_error(
                "scoring_result_invalid",
                "Collaborative result query sources must be a bounded immutable tuple",
            )
        for source in self.query_sources:
            if type(source) is not CollaborativeQuerySource:
                _contract_error(
                    "scoring_result_invalid",
                    "Collaborative result query source contains an invalid value",
                )
            source.validate(code="scoring_result_invalid")
        query_slugs = tuple(source.game_slug for source in self.query_sources)
        if len(query_slugs) != len(set(query_slugs)):
            _contract_error(
                "scoring_result_invalid",
                "Collaborative result query source slugs must be distinct",
            )
        supported = _validate_slug_tuple(
            self.supported_source_slugs,
            label="Supported collaborative sources",
            maximum=config.max_query_sources,
            code="scoring_result_invalid",
        )
        unsupported = _validate_slug_tuple(
            self.unsupported_source_slugs,
            label="Unsupported collaborative sources",
            maximum=config.max_query_sources,
            code="scoring_result_invalid",
        )
        if set(supported) & set(unsupported) or set(supported) | set(unsupported) != set(
            query_slugs
        ):
            _contract_error(
                "scoring_result_invalid",
                "Collaborative source support partitions are inconsistent",
            )
        query_order = {slug: index for index, slug in enumerate(query_slugs)}
        if any(
            query_order[left] >= query_order[right]
            for values in (supported, unsupported)
            for left, right in zip(values, values[1:], strict=False)
        ):
            _contract_error(
                "scoring_result_invalid",
                "Collaborative source support partitions are not canonically ordered",
            )
        if type(self.candidates) is not tuple or len(self.candidates) > config.max_candidates:
            _contract_error(
                "scoring_result_invalid",
                "Collaborative candidates must be a bounded immutable tuple",
            )
        for candidate in self.candidates:
            if type(candidate) is not CollaborativeCandidateScore:
                _contract_error(
                    "scoring_result_invalid",
                    "Collaborative candidates contain an invalid value",
                )
            candidate.validate(config)
        candidate_slugs = tuple(candidate.slug for candidate in self.candidates)
        if len(candidate_slugs) != len(set(candidate_slugs)) or set(candidate_slugs) & set(
            query_slugs
        ):
            _contract_error(
                "scoring_result_invalid",
                "Collaborative result candidate membership is invalid",
            )
        if self.candidates != tuple(
            sorted(
                self.candidates,
                key=lambda candidate: (-candidate.collaborative_score_units, candidate.slug),
            )
        ):
            _contract_error(
                "scoring_result_invalid",
                "Collaborative candidate order is invalid",
            )
        source_kinds = {source.game_slug: source.kind for source in self.query_sources}
        if any(
            edge.source_slug not in supported
            or source_kinds.get(edge.source_slug) != edge.source_kind
            for candidate in self.candidates
            for edge in candidate.source_edges
        ):
            _contract_error(
                "scoring_result_invalid",
                "Collaborative candidate evidence references an unsupported source",
            )
        if type(self.diagnostics) is not CollaborativeScoringDiagnostics:
            _contract_error(
                "scoring_result_invalid",
                "Collaborative scoring diagnostics are invalid",
            )
        self.diagnostics.validate(config)
        if (
            self.diagnostics.query_source_count != len(self.query_sources)
            or self.diagnostics.supported_source_count != len(supported)
            or self.diagnostics.unsupported_source_count != len(unsupported)
            or self.diagnostics.returned_candidate_count != len(self.candidates)
        ):
            _contract_error(
                "scoring_result_invalid",
                "Collaborative result and diagnostic counts are inconsistent",
            )
        empty_counts = (
            self.diagnostics.zero_degree_source_count == 0
            and self.diagnostics.visited_edge_count == 0
            and self.diagnostics.candidate_count_before_exclusions == 0
            and self.diagnostics.query_source_exclusion_count == 0
            and self.diagnostics.dislike_exclusion_count == 0
            and self.diagnostics.returned_candidate_count == 0
        )
        if self.reason == "recommendations":
            reason_valid = (
                bool(self.candidates)
                and bool(supported)
                and self.diagnostics.visited_edge_count > 0
            )
        elif self.reason == "no_query_sources":
            reason_valid = not self.query_sources and not self.candidates and empty_counts
        elif self.reason == "no_supported_sources":
            reason_valid = (
                bool(self.query_sources) and not supported and not self.candidates and empty_counts
            )
        elif self.reason == "no_candidate_edges":
            reason_valid = (
                bool(supported)
                and self.diagnostics.zero_degree_source_count == len(supported)
                and self.diagnostics.visited_edge_count == 0
                and self.diagnostics.candidate_count_before_exclusions == 0
                and not self.candidates
            )
        else:
            reason_valid = (
                self.diagnostics.visited_edge_count > 0
                and self.diagnostics.candidate_count_before_exclusions > 0
                and not self.candidates
            )
        if not reason_valid:
            _contract_error(
                "scoring_result_invalid",
                "Collaborative scoring reason does not match the result state",
            )
