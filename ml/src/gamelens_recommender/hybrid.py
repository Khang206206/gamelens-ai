from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from gamelens_recommender.collaborative import (
    COLLABORATIVE_SCORING_CONFIG,
    CollaborativeCandidateScore,
    CollaborativeScoringDiagnostics,
    CollaborativeScoringError,
    CollaborativeScoringIdentity,
    CollaborativeScoringResult,
    CollaborativeSourceEdge,
)
from gamelens_recommender.config import ARTIFACT_LIMITS, RANKING_CONFIG, SCORE_SCALE
from gamelens_recommender.feedback import (
    AffinityMaterializationError,
    FeedbackRanker,
    PreparedFeedbackRankingContext,
)
from gamelens_recommender.ranking import (
    MAX_EXACT_BASE_CANDIDATES,
    BaseCandidateMaterializationError,
    contribution,
)
from gamelens_recommender.schemas import (
    SLUG_PATTERN,
    BaseCandidateScore,
    FeedbackPolicyIdentity,
    PersonalizedRankingReason,
    PersonalizedRankingResult,
    PositiveFeedbackSource,
    RecommendationEvidence,
    ScoreComponent,
)

HYBRID_POLICY_NAME = "gamelens-hybrid-ranking"
HYBRID_POLICY_VERSION = "1.0.0"

HybridRankingMode = Literal["hybrid", "stage_4_fallback"]
HybridCandidateOrigin = Literal["content", "collaborative", "both"]
HybridAdjustmentReason = Literal[
    "feedback_affinity",
    "collaborative_similarity",
    "played_adjustment",
]
CollaborativeUnavailableReason = Literal[
    "not_configured",
    "fixture_not_allowed",
    "insufficient_data",
    "artifact_missing",
    "artifact_corrupt",
    "artifact_incompatible",
    "artifact_stale",
    "privacy_invalid",
    "artifact_expired",
    "catalog_stale",
    "artifact_retired",
]
HybridFallbackReason = Literal[
    "not_configured",
    "fixture_not_allowed",
    "insufficient_data",
    "artifact_missing",
    "artifact_corrupt",
    "artifact_incompatible",
    "artifact_stale",
    "privacy_invalid",
    "artifact_expired",
    "catalog_stale",
    "artifact_retired",
    "no_query_sources",
    "no_supported_sources",
    "no_candidate_edges",
    "no_eligible_candidates",
]
HybridContractErrorCode = Literal[
    "hybrid_config_invalid",
    "hybrid_input_invalid",
    "hybrid_result_invalid",
]

HYBRID_RANKING_MODES: tuple[HybridRankingMode, ...] = (
    "hybrid",
    "stage_4_fallback",
)
HYBRID_CANDIDATE_ORIGINS: tuple[HybridCandidateOrigin, ...] = (
    "content",
    "collaborative",
    "both",
)
COLLABORATIVE_UNAVAILABLE_REASONS: tuple[CollaborativeUnavailableReason, ...] = (
    "not_configured",
    "fixture_not_allowed",
    "insufficient_data",
    "artifact_missing",
    "artifact_corrupt",
    "artifact_incompatible",
    "artifact_stale",
    "privacy_invalid",
    "artifact_expired",
    "catalog_stale",
    "artifact_retired",
)
COLLABORATIVE_NO_SUPPORT_REASONS: tuple[HybridFallbackReason, ...] = (
    "no_query_sources",
    "no_supported_sources",
    "no_candidate_edges",
    "no_eligible_candidates",
)
HYBRID_FALLBACK_REASONS: tuple[HybridFallbackReason, ...] = (
    *COLLABORATIVE_UNAVAILABLE_REASONS,
    *COLLABORATIVE_NO_SUPPORT_REASONS,
)


class HybridContractError(ValueError):
    def __init__(self, code: HybridContractErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def _contract_error(code: HybridContractErrorCode, message: str) -> None:
    raise HybridContractError(code, message)


@dataclass(frozen=True)
class HybridPolicyIdentity:
    name: str
    version: str

    def validate(self) -> None:
        if (self.name, self.version) != (HYBRID_POLICY_NAME, HYBRID_POLICY_VERSION):
            _contract_error("hybrid_config_invalid", "Hybrid policy identity is unsupported")


@dataclass(frozen=True)
class HybridPolicyConfig:
    name: str = HYBRID_POLICY_NAME
    version: str = HYBRID_POLICY_VERSION
    score_scale: int = SCORE_SCALE
    affinity_weight_units: int = 100_000
    collaborative_weight_units: int = 100_000
    base_weight_units_with_affinity: int = 800_000
    base_weight_units_without_affinity: int = 900_000
    played_factor_units: int = 500_000
    ranking_modes: tuple[HybridRankingMode, ...] = HYBRID_RANKING_MODES
    candidate_origins: tuple[HybridCandidateOrigin, ...] = HYBRID_CANDIDATE_ORIGINS
    fallback_reasons: tuple[HybridFallbackReason, ...] = HYBRID_FALLBACK_REASONS
    tie_break: tuple[str, ...] = (
        "final_score_desc",
        "pre_played_score_desc",
        "base_contribution_desc",
        "collaborative_contribution_desc",
        "affinity_contribution_desc",
        "content_score_desc",
        "popularity_score_desc",
        "slug_asc",
    )

    @property
    def identity(self) -> HybridPolicyIdentity:
        return HybridPolicyIdentity(name=self.name, version=self.version)

    def validate(self) -> None:
        integer_values = (
            self.score_scale,
            self.affinity_weight_units,
            self.collaborative_weight_units,
            self.base_weight_units_with_affinity,
            self.base_weight_units_without_affinity,
            self.played_factor_units,
        )
        if any(type(value) is not int for value in integer_values):
            _contract_error(
                "hybrid_config_invalid",
                "Hybrid policy numeric values must be integers",
            )
        if any(
            type(value) is not tuple
            for value in (
                self.ranking_modes,
                self.candidate_origins,
                self.fallback_reasons,
                self.tie_break,
            )
        ):
            _contract_error(
                "hybrid_config_invalid",
                "Hybrid policy enumerations must be immutable tuples",
            )
        expected = HybridPolicyConfig()
        if self != expected:
            _contract_error(
                "hybrid_config_invalid",
                "Hybrid configuration does not match policy version 1.0.0",
            )
        if (
            self.base_weight_units_with_affinity
            + self.affinity_weight_units
            + self.collaborative_weight_units
            != self.score_scale
            or self.base_weight_units_without_affinity + self.collaborative_weight_units
            != self.score_scale
        ):
            _contract_error(
                "hybrid_config_invalid",
                "Hybrid active-component weights must sum to the score scale",
            )
        self.identity.validate()


HYBRID_POLICY_CONFIG = HybridPolicyConfig()


@dataclass(frozen=True)
class CollaborativeComponentUnavailable:
    reason: CollaborativeUnavailableReason

    def validate(self) -> None:
        if type(self.reason) is not str or self.reason not in COLLABORATIVE_UNAVAILABLE_REASONS:
            _contract_error(
                "hybrid_input_invalid",
                "Collaborative unavailability reason is invalid",
            )


@dataclass(frozen=True)
class CollaborativeComponentReady:
    scoring_result: CollaborativeScoringResult

    def validate(self) -> None:
        if type(self.scoring_result) is not CollaborativeScoringResult:
            _contract_error(
                "hybrid_input_invalid",
                "Ready collaborative component must contain a scoring result",
            )
        try:
            self.scoring_result.validate()
        except CollaborativeScoringError as error:
            raise HybridContractError(
                "hybrid_input_invalid",
                "Ready collaborative component contains an invalid scoring result",
            ) from error


CollaborativeComponentOutcome = CollaborativeComponentReady | CollaborativeComponentUnavailable


def _validate_base_candidate(
    candidate: BaseCandidateScore,
    *,
    code: HybridContractErrorCode,
) -> None:
    if type(candidate) is not BaseCandidateScore:
        _contract_error(code, "Hybrid base candidate is invalid")
    if type(candidate.slug) is not str or SLUG_PATTERN.fullmatch(candidate.slug) is None:
        _contract_error(code, "Hybrid base candidate slug is invalid")
    units = (
        candidate.base_score_units,
        candidate.content_score_units,
        candidate.platform_score_units,
        candidate.popularity_score_units,
    )
    if any(type(value) is not int or not 0 <= value <= SCORE_SCALE for value in units):
        _contract_error(code, "Hybrid base candidate units are invalid")
    expected_base_units = sum(
        contribution(raw_units, weight_units)
        for raw_units, weight_units in (
            (candidate.content_score_units, RANKING_CONFIG.content_weight_units),
            (candidate.platform_score_units, RANKING_CONFIG.platform_weight_units),
            (candidate.popularity_score_units, RANKING_CONFIG.popularity_weight_units),
        )
    )
    if candidate.base_score_units != expected_base_units:
        _contract_error(code, "Hybrid base candidate is not reconstructible")


def _hybrid_tie_break_key(
    *,
    final_score_units: int,
    pre_played_score_units: int,
    base_contribution_units: int,
    collaborative_contribution_units: int,
    affinity_contribution_units: int,
    content_score_units: int,
    popularity_score_units: int,
    slug: str,
) -> tuple[int, int, int, int, int, int, int, str]:
    return (
        -final_score_units,
        -pre_played_score_units,
        -base_contribution_units,
        -collaborative_contribution_units,
        -affinity_contribution_units,
        -content_score_units,
        -popularity_score_units,
        slug,
    )


@dataclass(frozen=True)
class HybridCandidateComponents:
    """Exact raw component state for one eligible union candidate."""

    slug: str
    candidate_origin: HybridCandidateOrigin
    base: BaseCandidateScore
    affinity_score_units: int
    collaborative_candidate: CollaborativeCandidateScore | None

    def validate(self) -> None:
        if type(self.slug) is not str or SLUG_PATTERN.fullmatch(self.slug) is None:
            _contract_error("hybrid_result_invalid", "Hybrid candidate slug is invalid")
        if self.candidate_origin not in HYBRID_CANDIDATE_ORIGINS:
            _contract_error("hybrid_result_invalid", "Hybrid candidate origin is invalid")
        _validate_base_candidate(self.base, code="hybrid_result_invalid")
        if self.base.slug != self.slug:
            _contract_error("hybrid_result_invalid", "Hybrid base candidate slug is inconsistent")
        if (
            type(self.affinity_score_units) is not int
            or not 0 <= self.affinity_score_units <= SCORE_SCALE
        ):
            _contract_error("hybrid_result_invalid", "Hybrid candidate affinity units are invalid")

        content_supported = self.base.content_score_units > 0
        if self.collaborative_candidate is None:
            if self.candidate_origin != "content" or not content_supported:
                _contract_error(
                    "hybrid_result_invalid",
                    "Content-only hybrid candidate state is inconsistent",
                )
            return
        if type(self.collaborative_candidate) is not CollaborativeCandidateScore:
            _contract_error("hybrid_result_invalid", "Hybrid collaborative candidate is invalid")
        try:
            self.collaborative_candidate.validate()
        except CollaborativeScoringError as error:
            raise HybridContractError(
                "hybrid_result_invalid",
                "Hybrid collaborative candidate is invalid",
            ) from error
        if self.collaborative_candidate.slug != self.slug:
            _contract_error(
                "hybrid_result_invalid",
                "Hybrid collaborative candidate slug is inconsistent",
            )
        expected_origin: HybridCandidateOrigin = "both" if content_supported else "collaborative"
        if self.candidate_origin != expected_origin:
            _contract_error(
                "hybrid_result_invalid",
                "Hybrid collaborative candidate origin is inconsistent",
            )


@dataclass(frozen=True)
class HybridCandidateUnion:
    """Canonical pre-weight, pre-played, pre-rank candidate union."""

    affinity_profile_active: bool
    candidates: tuple[HybridCandidateComponents, ...]

    @property
    def collaborative_candidate_count(self) -> int:
        return sum(candidate.collaborative_candidate is not None for candidate in self.candidates)

    def validate(self) -> None:
        if type(self.affinity_profile_active) is not bool:
            _contract_error("hybrid_result_invalid", "Hybrid affinity profile state is invalid")
        if (
            type(self.candidates) is not tuple
            or len(self.candidates) > ARTIFACT_LIMITS.max_items
            or any(
                type(candidate) is not HybridCandidateComponents for candidate in self.candidates
            )
        ):
            _contract_error("hybrid_result_invalid", "Hybrid candidate union is invalid")
        for candidate in self.candidates:
            candidate.validate()
        slugs = tuple(candidate.slug for candidate in self.candidates)
        if slugs != tuple(sorted(set(slugs))):
            _contract_error(
                "hybrid_result_invalid",
                "Hybrid candidate union order or membership is invalid",
            )
        if not self.affinity_profile_active and any(
            candidate.affinity_score_units != 0 for candidate in self.candidates
        ):
            _contract_error(
                "hybrid_result_invalid",
                "Inactive hybrid affinity profile has a non-zero candidate score",
            )


def _validate_candidate_union_inputs(
    feedback_ranker: FeedbackRanker,
    prepared_context: PreparedFeedbackRankingContext,
    collaborative_result: CollaborativeScoringResult,
) -> None:
    if type(feedback_ranker) is not FeedbackRanker:
        _contract_error("hybrid_input_invalid", "Hybrid feedback ranker is invalid")
    if type(prepared_context) is not PreparedFeedbackRankingContext:
        _contract_error("hybrid_input_invalid", "Prepared hybrid ranking context is invalid")
    try:
        prepared_context.validate()
    except ValueError as error:
        raise HybridContractError(
            "hybrid_input_invalid",
            "Prepared hybrid ranking context is invalid",
        ) from error
    if type(collaborative_result) is not CollaborativeScoringResult:
        _contract_error("hybrid_input_invalid", "Collaborative scoring result is invalid")
    try:
        collaborative_result.validate()
    except CollaborativeScoringError as error:
        raise HybridContractError(
            "hybrid_input_invalid",
            "Collaborative scoring result is invalid",
        ) from error
    if collaborative_result.reason != "recommendations":
        _contract_error(
            "hybrid_input_invalid",
            "Candidate union requires collaborative recommendation support",
        )
    if collaborative_result.query_sources != prepared_context.collaborative_query_context.sources:
        _contract_error(
            "hybrid_input_invalid",
            "Collaborative query sources do not match the prepared ranking context",
        )

    artifact_slugs = set(feedback_ranker.artifact.slug_to_row)
    prepared_slugs = (
        set(prepared_context.candidate_exclusion_slugs)
        | set(prepared_context.played_slugs)
        | {source.game_slug for source in prepared_context.collaborative_query_context.sources}
        | set(prepared_context.collaborative_query_context.disliked_slugs)
    )
    if not prepared_slugs <= artifact_slugs or any(
        candidate.slug not in artifact_slugs for candidate in collaborative_result.candidates
    ):
        _contract_error(
            "hybrid_input_invalid",
            "Hybrid candidate state is incompatible with the content artifact",
        )


def materialize_hybrid_candidate_union(
    feedback_ranker: FeedbackRanker,
    prepared_context: PreparedFeedbackRankingContext,
    collaborative_result: CollaborativeScoringResult,
) -> HybridCandidateUnion:
    """Join exact Stage 4 and collaborative components without final policy math.

    The raw union is formed before hard exclusions. Exact base and affinity
    materialization is chunked at the Phase 3 row bound. This seam applies no
    hybrid weights, played factor, top-K truncation, final rank, fallback, or
    explanation prose.
    """

    _validate_candidate_union_inputs(feedback_ranker, prepared_context, collaborative_result)
    content_candidates = feedback_ranker.content_ranker.score_candidates(
        prepared_context.effective_context
    )
    if type(content_candidates) is not tuple or any(
        type(candidate) is not BaseCandidateScore for candidate in content_candidates
    ):
        _contract_error("hybrid_input_invalid", "Stage 4 content candidates are invalid")
    for candidate in content_candidates:
        _validate_base_candidate(candidate, code="hybrid_input_invalid")
        if (
            candidate.slug not in feedback_ranker.artifact.slug_to_row
            or candidate.content_score_units <= 0
        ):
            _contract_error(
                "hybrid_input_invalid",
                "Stage 4 content candidate eligibility is invalid",
            )
    content_by_slug = {candidate.slug: candidate for candidate in content_candidates}
    if len(content_by_slug) != len(content_candidates):
        _contract_error("hybrid_input_invalid", "Stage 4 content candidates are not distinct")
    collaborative_by_slug = {
        candidate.slug: candidate for candidate in collaborative_result.candidates
    }

    raw_union_slugs = set(content_by_slug) | set(collaborative_by_slug)
    candidate_slugs = tuple(
        sorted(raw_union_slugs - set(prepared_context.candidate_exclusion_slugs))
    )
    base_by_slug: dict[str, BaseCandidateScore] = {}
    affinity_by_slug: dict[str, int] = {}
    expected_affinity_profile_active = bool(prepared_context.positive_sources)
    for start in range(0, len(candidate_slugs), MAX_EXACT_BASE_CANDIDATES):
        chunk = candidate_slugs[start : start + MAX_EXACT_BASE_CANDIDATES]
        try:
            base_chunk = feedback_ranker.content_ranker.materialize_base_candidates(
                prepared_context.effective_context,
                chunk,
            )
            affinity_chunk = feedback_ranker.materialize_affinity_candidates(
                prepared_context.positive_sources,
                chunk,
            )
        except (BaseCandidateMaterializationError, AffinityMaterializationError) as error:
            raise HybridContractError(
                "hybrid_input_invalid",
                "Hybrid candidate component materialization failed",
            ) from error
        if (
            tuple(candidate.slug for candidate in base_chunk) != chunk
            or tuple(candidate.slug for candidate in affinity_chunk.candidates) != chunk
            or affinity_chunk.profile_active != expected_affinity_profile_active
        ):
            _contract_error(
                "hybrid_input_invalid",
                "Hybrid candidate component materialization is inconsistent",
            )
        for candidate in base_chunk:
            _validate_base_candidate(candidate, code="hybrid_input_invalid")
            base_by_slug[candidate.slug] = candidate
        affinity_by_slug.update(
            (candidate.slug, candidate.affinity_score_units)
            for candidate in affinity_chunk.candidates
        )

    if any(
        slug in content_by_slug and base_by_slug.get(slug) != content_by_slug[slug]
        for slug in candidate_slugs
    ):
        _contract_error(
            "hybrid_input_invalid",
            "Exact base materialization drifted from Stage 4 content scoring",
        )

    candidates = tuple(
        HybridCandidateComponents(
            slug=slug,
            candidate_origin=(
                "both"
                if slug in content_by_slug and slug in collaborative_by_slug
                else "content"
                if slug in content_by_slug
                else "collaborative"
            ),
            base=base_by_slug[slug],
            affinity_score_units=affinity_by_slug[slug],
            collaborative_candidate=collaborative_by_slug.get(slug),
        )
        for slug in candidate_slugs
    )
    result = HybridCandidateUnion(
        affinity_profile_active=expected_affinity_profile_active,
        candidates=candidates,
    )
    result.validate()
    return result


@dataclass(frozen=True)
class RankedHybridCandidate:
    """One selected candidate after versioned math, before evidence prose."""

    rank: int
    candidate: HybridCandidateComponents
    base_weight_units: int
    base_contribution_units: int
    affinity_weight_units: int
    affinity_contribution_units: int
    collaborative_weight_units: int
    collaborative_contribution_units: int
    pre_played_score_units: int
    played_factor_units: int
    played_delta_units: int
    final_score_units: int
    adjustment_reasons: tuple[HybridAdjustmentReason, ...]

    def validate(self, config: HybridPolicyConfig = HYBRID_POLICY_CONFIG) -> None:
        config.validate()
        if type(self.rank) is not int or self.rank <= 0:
            _contract_error("hybrid_result_invalid", "Ranked hybrid candidate rank is invalid")
        if type(self.candidate) is not HybridCandidateComponents:
            _contract_error("hybrid_result_invalid", "Ranked hybrid candidate is invalid")
        self.candidate.validate()
        if self.affinity_weight_units == config.affinity_weight_units:
            affinity_profile_active = True
            expected_base_weight = config.base_weight_units_with_affinity
        elif self.affinity_weight_units == 0 and self.candidate.affinity_score_units == 0:
            affinity_profile_active = False
            expected_base_weight = config.base_weight_units_without_affinity
        else:
            _contract_error(
                "hybrid_result_invalid",
                "Ranked hybrid candidate affinity weight is invalid",
            )
        if (
            self.base_weight_units != expected_base_weight
            or self.collaborative_weight_units != config.collaborative_weight_units
        ):
            _contract_error(
                "hybrid_result_invalid",
                "Ranked hybrid candidate request weights are invalid",
            )
        unit_values = (
            self.base_contribution_units,
            self.affinity_contribution_units,
            self.collaborative_contribution_units,
            self.pre_played_score_units,
            self.played_factor_units,
            self.final_score_units,
        )
        if any(type(value) is not int or not 0 <= value <= SCORE_SCALE for value in unit_values):
            _contract_error("hybrid_result_invalid", "Ranked hybrid candidate units are invalid")
        if (
            type(self.played_delta_units) is not int
            or not -SCORE_SCALE <= self.played_delta_units <= 0
        ):
            _contract_error(
                "hybrid_result_invalid",
                "Ranked hybrid candidate played delta is invalid",
            )
        if type(self.adjustment_reasons) is not tuple or any(
            type(reason) is not str
            or reason
            not in {
                "feedback_affinity",
                "collaborative_similarity",
                "played_adjustment",
            }
            for reason in self.adjustment_reasons
        ):
            _contract_error(
                "hybrid_result_invalid",
                "Ranked hybrid candidate adjustment reasons are invalid",
            )

        collaborative_score_units = (
            self.candidate.collaborative_candidate.collaborative_score_units
            if self.candidate.collaborative_candidate is not None
            else 0
        )
        expected_base_contribution = contribution(
            self.candidate.base.base_score_units,
            self.base_weight_units,
        )
        expected_affinity_contribution = contribution(
            self.candidate.affinity_score_units,
            self.affinity_weight_units,
        )
        expected_collaborative_contribution = contribution(
            collaborative_score_units,
            self.collaborative_weight_units,
        )
        expected_pre_played = (
            expected_base_contribution
            + expected_affinity_contribution
            + expected_collaborative_contribution
        )
        played_adjusted = "played_adjustment" in self.adjustment_reasons
        expected_played_factor = config.played_factor_units if played_adjusted else SCORE_SCALE
        expected_final = contribution(expected_pre_played, expected_played_factor)
        if (
            self.base_contribution_units != expected_base_contribution
            or self.affinity_contribution_units != expected_affinity_contribution
            or self.collaborative_contribution_units != expected_collaborative_contribution
            or self.pre_played_score_units != expected_pre_played
            or self.played_factor_units != expected_played_factor
            or self.final_score_units != expected_final
            or self.played_delta_units != expected_final - expected_pre_played
        ):
            _contract_error(
                "hybrid_result_invalid",
                "Ranked hybrid candidate score is not reconstructible",
            )
        expected_reasons: tuple[HybridAdjustmentReason, ...] = ()
        if affinity_profile_active:
            expected_reasons += ("feedback_affinity",)
        if self.candidate.collaborative_candidate is not None:
            expected_reasons += ("collaborative_similarity",)
        if played_adjusted:
            expected_reasons += ("played_adjustment",)
        if self.adjustment_reasons != expected_reasons:
            _contract_error(
                "hybrid_result_invalid",
                "Ranked hybrid candidate adjustment reasons are invalid",
            )


def _ranked_hybrid_candidate_key(
    candidate: RankedHybridCandidate,
) -> tuple[int, int, int, int, int, int, int, str]:
    return _hybrid_tie_break_key(
        final_score_units=candidate.final_score_units,
        pre_played_score_units=candidate.pre_played_score_units,
        base_contribution_units=candidate.base_contribution_units,
        collaborative_contribution_units=candidate.collaborative_contribution_units,
        affinity_contribution_units=candidate.affinity_contribution_units,
        content_score_units=candidate.candidate.base.content_score_units,
        popularity_score_units=candidate.candidate.base.popularity_score_units,
        slug=candidate.candidate.slug,
    )


@dataclass(frozen=True)
class HybridCandidateRanking:
    """Deterministic top-K hybrid scores without fallback or prose."""

    policy: HybridPolicyIdentity
    affinity_profile_active: bool
    items: tuple[RankedHybridCandidate, ...]

    def validate(self, config: HybridPolicyConfig = HYBRID_POLICY_CONFIG) -> None:
        config.validate()
        if type(self.policy) is not HybridPolicyIdentity or self.policy != config.identity:
            _contract_error("hybrid_result_invalid", "Hybrid candidate ranking policy is invalid")
        if type(self.affinity_profile_active) is not bool:
            _contract_error(
                "hybrid_result_invalid",
                "Hybrid candidate ranking affinity state is invalid",
            )
        if (
            type(self.items) is not tuple
            or not self.items
            or len(self.items) > 20
            or any(type(item) is not RankedHybridCandidate for item in self.items)
        ):
            _contract_error("hybrid_result_invalid", "Hybrid candidate ranking items are invalid")
        for item in self.items:
            item.validate(config)
            expected_affinity_weight = (
                config.affinity_weight_units if self.affinity_profile_active else 0
            )
            if item.affinity_weight_units != expected_affinity_weight:
                _contract_error(
                    "hybrid_result_invalid",
                    "Hybrid candidate ranking affinity weights are inconsistent",
                )
        if tuple(item.rank for item in self.items) != tuple(range(1, len(self.items) + 1)):
            _contract_error("hybrid_result_invalid", "Hybrid candidate ranks are not contiguous")
        slugs = tuple(item.candidate.slug for item in self.items)
        if len(slugs) != len(set(slugs)):
            _contract_error(
                "hybrid_result_invalid",
                "Hybrid candidate ranking slugs are not distinct",
            )
        if self.items != tuple(sorted(self.items, key=_ranked_hybrid_candidate_key)):
            _contract_error("hybrid_result_invalid", "Hybrid candidate ranking order is invalid")


def rank_hybrid_candidate_union(
    candidate_union: HybridCandidateUnion,
    prepared_context: PreparedFeedbackRankingContext,
    config: HybridPolicyConfig = HYBRID_POLICY_CONFIG,
) -> HybridCandidateRanking:
    """Apply request-wide hybrid weights, played adjustment, order, and top-K.

    Collaborative weight remains active for every candidate in a supported
    request. Missing candidate edges contribute zero and are never reassigned
    to base. This function performs no fallback, evidence materialization,
    explanation prose, I/O, or mutation.
    """

    if type(config) is not HybridPolicyConfig:
        _contract_error("hybrid_config_invalid", "Hybrid policy configuration is invalid")
    config.validate()
    if type(candidate_union) is not HybridCandidateUnion:
        _contract_error("hybrid_input_invalid", "Hybrid candidate union is invalid")
    try:
        candidate_union.validate()
    except HybridContractError as error:
        raise HybridContractError(
            "hybrid_input_invalid",
            "Hybrid candidate union is invalid",
        ) from error
    if type(prepared_context) is not PreparedFeedbackRankingContext:
        _contract_error("hybrid_input_invalid", "Prepared hybrid ranking context is invalid")
    try:
        prepared_context.validate()
    except ValueError as error:
        raise HybridContractError(
            "hybrid_input_invalid",
            "Prepared hybrid ranking context is invalid",
        ) from error
    if candidate_union.affinity_profile_active != bool(prepared_context.positive_sources):
        _contract_error(
            "hybrid_input_invalid",
            "Hybrid affinity state does not match the prepared ranking context",
        )
    if candidate_union.collaborative_candidate_count <= 0:
        _contract_error(
            "hybrid_input_invalid",
            "Hybrid ranking requires an eligible collaborative candidate",
        )
    if {candidate.slug for candidate in candidate_union.candidates} & set(
        prepared_context.candidate_exclusion_slugs
    ):
        _contract_error(
            "hybrid_input_invalid",
            "Hybrid candidate union bypasses a prepared hard exclusion",
        )

    affinity_profile_active = candidate_union.affinity_profile_active
    base_weight_units = (
        config.base_weight_units_with_affinity
        if affinity_profile_active
        else config.base_weight_units_without_affinity
    )
    affinity_weight_units = config.affinity_weight_units if affinity_profile_active else 0
    played_slugs = set(prepared_context.played_slugs)
    scored: list[RankedHybridCandidate] = []
    for candidate in candidate_union.candidates:
        collaborative_score_units = (
            candidate.collaborative_candidate.collaborative_score_units
            if candidate.collaborative_candidate is not None
            else 0
        )
        base_contribution_units = contribution(candidate.base.base_score_units, base_weight_units)
        affinity_contribution_units = contribution(
            candidate.affinity_score_units,
            affinity_weight_units,
        )
        collaborative_contribution_units = contribution(
            collaborative_score_units,
            config.collaborative_weight_units,
        )
        pre_played_score_units = (
            base_contribution_units + affinity_contribution_units + collaborative_contribution_units
        )
        is_played = candidate.slug in played_slugs
        played_factor_units = config.played_factor_units if is_played else SCORE_SCALE
        final_score_units = contribution(pre_played_score_units, played_factor_units)
        adjustment_reasons: tuple[HybridAdjustmentReason, ...] = ()
        if affinity_profile_active:
            adjustment_reasons += ("feedback_affinity",)
        if candidate.collaborative_candidate is not None:
            adjustment_reasons += ("collaborative_similarity",)
        if is_played:
            adjustment_reasons += ("played_adjustment",)
        scored.append(
            RankedHybridCandidate(
                rank=1,
                candidate=candidate,
                base_weight_units=base_weight_units,
                base_contribution_units=base_contribution_units,
                affinity_weight_units=affinity_weight_units,
                affinity_contribution_units=affinity_contribution_units,
                collaborative_weight_units=config.collaborative_weight_units,
                collaborative_contribution_units=collaborative_contribution_units,
                pre_played_score_units=pre_played_score_units,
                played_factor_units=played_factor_units,
                played_delta_units=final_score_units - pre_played_score_units,
                final_score_units=final_score_units,
                adjustment_reasons=adjustment_reasons,
            )
        )

    scored.sort(key=_ranked_hybrid_candidate_key)
    selected = scored[: prepared_context.effective_context.top_k]
    result = HybridCandidateRanking(
        policy=config.identity,
        affinity_profile_active=affinity_profile_active,
        items=tuple(replace(candidate, rank=rank) for rank, candidate in enumerate(selected, 1)),
    )
    result.validate(config)
    return result


@dataclass(frozen=True)
class HybridRecommendation:
    slug: str
    rank: int
    candidate_origin: HybridCandidateOrigin
    base_score_units: int
    base_components: tuple[ScoreComponent, ...]
    base_evidence: RecommendationEvidence
    base_weight_units: int
    base_contribution_units: int
    affinity_score_units: int
    affinity_weight_units: int
    affinity_contribution_units: int
    collaborative_supported: bool
    collaborative_score_units: int
    collaborative_weight_units: int
    collaborative_contribution_units: int
    collaborative_item_support: int | None
    collaborative_source_edges: tuple[CollaborativeSourceEdge, ...]
    pre_played_score_units: int
    played_factor_units: int
    played_delta_units: int
    final_score_units: int
    explanation_summary: str
    explanation_reasons: tuple[str, ...]
    adjustment_reasons: tuple[HybridAdjustmentReason, ...]

    def validate_structure(self, config: HybridPolicyConfig = HYBRID_POLICY_CONFIG) -> None:
        config.validate()
        if type(self.slug) is not str or SLUG_PATTERN.fullmatch(self.slug) is None:
            _contract_error("hybrid_result_invalid", "Hybrid recommendation slug is invalid")
        if type(self.rank) is not int or self.rank <= 0:
            _contract_error("hybrid_result_invalid", "Hybrid recommendation rank is invalid")
        if self.candidate_origin not in HYBRID_CANDIDATE_ORIGINS:
            _contract_error("hybrid_result_invalid", "Hybrid candidate origin is invalid")
        unit_values = (
            self.base_score_units,
            self.base_weight_units,
            self.base_contribution_units,
            self.affinity_score_units,
            self.affinity_weight_units,
            self.affinity_contribution_units,
            self.collaborative_score_units,
            self.collaborative_weight_units,
            self.collaborative_contribution_units,
            self.pre_played_score_units,
            self.played_factor_units,
            self.final_score_units,
        )
        if any(type(value) is not int or not 0 <= value <= SCORE_SCALE for value in unit_values):
            _contract_error("hybrid_result_invalid", "Hybrid recommendation units are invalid")
        if (
            type(self.played_delta_units) is not int
            or not -SCORE_SCALE <= self.played_delta_units <= 0
        ):
            _contract_error("hybrid_result_invalid", "Hybrid played delta is invalid")
        if (
            type(self.base_components) is not tuple
            or any(type(component) is not ScoreComponent for component in self.base_components)
            or tuple(component.name for component in self.base_components)
            != ("content", "platform", "popularity")
        ):
            _contract_error("hybrid_result_invalid", "Hybrid base components are invalid")
        expected_base_component_weights = (
            RANKING_CONFIG.content_weight_units,
            RANKING_CONFIG.platform_weight_units,
            RANKING_CONFIG.popularity_weight_units,
        )
        for component, expected_weight in zip(
            self.base_components,
            expected_base_component_weights,
            strict=True,
        ):
            if (
                type(component.raw_units) is not int
                or not 0 <= component.raw_units <= SCORE_SCALE
                or type(component.weight_units) is not int
                or type(component.contribution_units) is not int
                or component.weight_units != expected_weight
                or component.contribution_units
                != contribution(component.raw_units, component.weight_units)
            ):
                _contract_error(
                    "hybrid_result_invalid",
                    "Hybrid base component is not reconstructible",
                )
        if self.base_score_units != sum(
            component.contribution_units for component in self.base_components
        ):
            _contract_error(
                "hybrid_result_invalid",
                "Hybrid base score is not reconstructible",
            )
        if type(self.base_evidence) is not RecommendationEvidence:
            _contract_error("hybrid_result_invalid", "Hybrid base evidence is invalid")
        if self.base_evidence.popularity_percentile_units != self.base_components[2].raw_units:
            _contract_error(
                "hybrid_result_invalid",
                "Hybrid base evidence is inconsistent",
            )
        if type(self.collaborative_supported) is not bool:
            _contract_error("hybrid_result_invalid", "Hybrid collaborative support is invalid")
        if type(self.collaborative_source_edges) is not tuple or any(
            type(edge) is not CollaborativeSourceEdge for edge in self.collaborative_source_edges
        ):
            _contract_error("hybrid_result_invalid", "Hybrid collaborative edges are invalid")
        if any(edge.candidate_slug != self.slug for edge in self.collaborative_source_edges):
            _contract_error(
                "hybrid_result_invalid",
                "Hybrid collaborative edges reference another candidate",
            )
        try:
            for edge in self.collaborative_source_edges:
                edge.validate()
        except CollaborativeScoringError as error:
            raise HybridContractError(
                "hybrid_result_invalid",
                "Hybrid collaborative edge is invalid",
            ) from error
        content_supported = self.base_components[0].raw_units > 0
        if self.collaborative_supported:
            if self.candidate_origin == "content" or not self.collaborative_source_edges:
                _contract_error(
                    "hybrid_result_invalid",
                    "Supported collaborative evidence is incomplete",
                )
            try:
                CollaborativeCandidateScore(
                    slug=self.slug,
                    collaborative_score_units=self.collaborative_score_units,
                    item_support=self.collaborative_item_support,  # type: ignore[arg-type]
                    source_edges=self.collaborative_source_edges,
                ).validate()
            except CollaborativeScoringError as error:
                raise HybridContractError(
                    "hybrid_result_invalid",
                    "Supported collaborative evidence is invalid",
                ) from error
            expected_origin: HybridCandidateOrigin = (
                "both" if content_supported else "collaborative"
            )
            if self.candidate_origin != expected_origin:
                _contract_error(
                    "hybrid_result_invalid",
                    "Supported collaborative candidate origin is inconsistent",
                )
        elif (
            self.candidate_origin != "content"
            or self.collaborative_score_units != 0
            or self.collaborative_contribution_units != 0
            or self.collaborative_item_support is not None
            or self.collaborative_source_edges
        ):
            _contract_error(
                "hybrid_result_invalid",
                "Unsupported collaborative evidence must remain empty",
            )
        elif not content_supported:
            _contract_error(
                "hybrid_result_invalid",
                "Content-only hybrid candidate has no content support",
            )
        if type(self.explanation_summary) is not str or not self.explanation_summary:
            _contract_error("hybrid_result_invalid", "Hybrid explanation summary is invalid")
        if (
            type(self.explanation_reasons) is not tuple
            or not self.explanation_reasons
            or any(type(reason) is not str or not reason for reason in self.explanation_reasons)
        ):
            _contract_error("hybrid_result_invalid", "Hybrid explanation reasons are invalid")
        if type(self.adjustment_reasons) is not tuple or any(
            type(reason) is not str
            or reason not in {"feedback_affinity", "collaborative_similarity", "played_adjustment"}
            for reason in self.adjustment_reasons
        ):
            _contract_error("hybrid_result_invalid", "Hybrid adjustment reasons are invalid")

        if self.affinity_weight_units == config.affinity_weight_units:
            affinity_profile_active = True
            expected_base_weight = config.base_weight_units_with_affinity
        elif self.affinity_weight_units == 0 and self.affinity_score_units == 0:
            affinity_profile_active = False
            expected_base_weight = config.base_weight_units_without_affinity
        else:
            _contract_error("hybrid_result_invalid", "Hybrid affinity state is invalid")
        expected_base_contribution = contribution(self.base_score_units, self.base_weight_units)
        expected_affinity_contribution = contribution(
            self.affinity_score_units,
            self.affinity_weight_units,
        )
        expected_collaborative_contribution = contribution(
            self.collaborative_score_units,
            self.collaborative_weight_units,
        )
        expected_pre_played = (
            expected_base_contribution
            + expected_affinity_contribution
            + expected_collaborative_contribution
        )
        played_adjusted = "played_adjustment" in self.adjustment_reasons
        expected_played_factor = config.played_factor_units if played_adjusted else SCORE_SCALE
        expected_final = contribution(expected_pre_played, expected_played_factor)
        if (
            self.base_weight_units != expected_base_weight
            or self.collaborative_weight_units != config.collaborative_weight_units
            or self.base_contribution_units != expected_base_contribution
            or self.affinity_contribution_units != expected_affinity_contribution
            or self.collaborative_contribution_units != expected_collaborative_contribution
            or self.pre_played_score_units != expected_pre_played
            or self.played_factor_units != expected_played_factor
            or self.played_delta_units != expected_final - expected_pre_played
            or self.final_score_units != expected_final
        ):
            _contract_error(
                "hybrid_result_invalid",
                "Hybrid recommendation score is not reconstructible",
            )
        expected_reasons: tuple[HybridAdjustmentReason, ...] = ()
        if affinity_profile_active:
            expected_reasons += ("feedback_affinity",)
        if self.collaborative_supported:
            expected_reasons += ("collaborative_similarity",)
        if played_adjusted:
            expected_reasons += ("played_adjustment",)
        if self.adjustment_reasons != expected_reasons:
            _contract_error("hybrid_result_invalid", "Hybrid adjustment reasons are inconsistent")


def _hybrid_recommendation_key(
    recommendation: HybridRecommendation,
) -> tuple[int, int, int, int, int, int, int, str]:
    components = {component.name: component for component in recommendation.base_components}
    return _hybrid_tie_break_key(
        final_score_units=recommendation.final_score_units,
        pre_played_score_units=recommendation.pre_played_score_units,
        base_contribution_units=recommendation.base_contribution_units,
        collaborative_contribution_units=recommendation.collaborative_contribution_units,
        affinity_contribution_units=recommendation.affinity_contribution_units,
        content_score_units=components["content"].raw_units,
        popularity_score_units=components["popularity"].raw_units,
        slug=recommendation.slug,
    )


@dataclass(frozen=True)
class HybridRecommendationsResult:
    mode: Literal["hybrid"]
    items: tuple[HybridRecommendation, ...]
    reason: PersonalizedRankingReason
    policy: HybridPolicyIdentity
    feedback_policy: FeedbackPolicyIdentity
    collaborative_policy: CollaborativeScoringIdentity
    collaborative_diagnostics: CollaborativeScoringDiagnostics
    positive_sources: tuple[PositiveFeedbackSource, ...]

    def validate(self, config: HybridPolicyConfig = HYBRID_POLICY_CONFIG) -> None:
        config.validate()
        if self.mode != "hybrid" or self.reason != "recommendations":
            _contract_error("hybrid_result_invalid", "Hybrid result mode or reason is invalid")
        if type(self.policy) is not HybridPolicyIdentity or self.policy != config.identity:
            _contract_error("hybrid_result_invalid", "Hybrid result policy identity is invalid")
        if type(self.feedback_policy) is not FeedbackPolicyIdentity or (
            self.feedback_policy.name,
            self.feedback_policy.version,
        ) != ("gamelens-feedback-adjustment", "1.0.0"):
            _contract_error("hybrid_result_invalid", "Hybrid feedback policy identity is invalid")
        if (
            type(self.collaborative_policy) is not CollaborativeScoringIdentity
            or self.collaborative_policy != COLLABORATIVE_SCORING_CONFIG.identity
        ):
            _contract_error(
                "hybrid_result_invalid",
                "Hybrid collaborative policy identity is invalid",
            )
        if type(self.collaborative_diagnostics) is not CollaborativeScoringDiagnostics:
            _contract_error(
                "hybrid_result_invalid",
                "Hybrid collaborative diagnostics are invalid",
            )
        try:
            self.collaborative_diagnostics.validate()
        except CollaborativeScoringError as error:
            raise HybridContractError(
                "hybrid_result_invalid",
                "Hybrid collaborative diagnostics are invalid",
            ) from error
        if type(self.positive_sources) is not tuple or any(
            type(source) is not PositiveFeedbackSource for source in self.positive_sources
        ):
            _contract_error("hybrid_result_invalid", "Hybrid positive sources are invalid")
        if (
            type(self.items) is not tuple
            or not self.items
            or len(self.items) > 20
            or any(type(item) is not HybridRecommendation for item in self.items)
        ):
            _contract_error("hybrid_result_invalid", "Hybrid result items are invalid")
        affinity_profile_active = bool(self.positive_sources)
        for item in self.items:
            item.validate_structure(config)
            expected_affinity_weight = (
                config.affinity_weight_units if affinity_profile_active else 0
            )
            if item.affinity_weight_units != expected_affinity_weight:
                _contract_error(
                    "hybrid_result_invalid",
                    "Hybrid result affinity state is inconsistent",
                )
        if self.collaborative_diagnostics.returned_candidate_count <= 0:
            _contract_error(
                "hybrid_result_invalid",
                "Hybrid result has no collaborative candidate support",
            )
        if tuple(item.rank for item in self.items) != tuple(range(1, len(self.items) + 1)):
            _contract_error("hybrid_result_invalid", "Hybrid result ranks are not contiguous")
        slugs = tuple(item.slug for item in self.items)
        if len(slugs) != len(set(slugs)):
            _contract_error("hybrid_result_invalid", "Hybrid result item slugs are not distinct")
        if self.items != tuple(sorted(self.items, key=_hybrid_recommendation_key)):
            _contract_error("hybrid_result_invalid", "Hybrid result order is invalid")


@dataclass(frozen=True)
class Stage4FallbackResult:
    mode: Literal["stage_4_fallback"]
    fallback_reason: HybridFallbackReason
    stage_4_result: PersonalizedRankingResult

    def validate(self) -> None:
        if self.mode != "stage_4_fallback":
            _contract_error("hybrid_result_invalid", "Stage 4 fallback mode is invalid")
        if (
            type(self.fallback_reason) is not str
            or self.fallback_reason not in HYBRID_FALLBACK_REASONS
        ):
            _contract_error("hybrid_result_invalid", "Stage 4 fallback reason is invalid")
        if type(self.stage_4_result) is not PersonalizedRankingResult:
            _contract_error("hybrid_result_invalid", "Stage 4 fallback payload is invalid")


HybridRankingResult = HybridRecommendationsResult | Stage4FallbackResult


def validate_collaborative_component_outcome(outcome: CollaborativeComponentOutcome) -> None:
    if type(outcome) is CollaborativeComponentReady:
        outcome.validate()
        return
    if type(outcome) is CollaborativeComponentUnavailable:
        outcome.validate()
        return
    _contract_error("hybrid_input_invalid", "Collaborative component outcome is invalid")


def validate_hybrid_ranking_result(
    result: HybridRankingResult,
    config: HybridPolicyConfig = HYBRID_POLICY_CONFIG,
) -> None:
    if type(result) is HybridRecommendationsResult:
        result.validate(config)
        return
    if type(result) is Stage4FallbackResult:
        result.validate()
        return
    _contract_error("hybrid_result_invalid", "Hybrid ranking result is invalid")
