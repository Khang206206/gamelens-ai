from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from gamelens_recommender.collaborative import (
    COLLABORATIVE_SCORING_CONFIG,
    CollaborativeScoringDiagnostics,
    CollaborativeScoringError,
    CollaborativeScoringIdentity,
    CollaborativeScoringResult,
    CollaborativeSourceEdge,
)
from gamelens_recommender.config import SCORE_SCALE
from gamelens_recommender.schemas import (
    SLUG_PATTERN,
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

    def validate_structure(self) -> None:
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
        if type(self.base_components) is not tuple or any(
            type(component) is not ScoreComponent for component in self.base_components
        ):
            _contract_error("hybrid_result_invalid", "Hybrid base components are invalid")
        if type(self.base_evidence) is not RecommendationEvidence:
            _contract_error("hybrid_result_invalid", "Hybrid base evidence is invalid")
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
        if self.collaborative_supported:
            if (
                self.candidate_origin == "content"
                or self.collaborative_score_units <= 0
                or type(self.collaborative_item_support) is not int
                or self.collaborative_item_support <= 0
                or not self.collaborative_source_edges
            ):
                _contract_error(
                    "hybrid_result_invalid",
                    "Supported collaborative evidence is incomplete",
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
        if (
            type(self.items) is not tuple
            or not self.items
            or any(type(item) is not HybridRecommendation for item in self.items)
        ):
            _contract_error("hybrid_result_invalid", "Hybrid result items are invalid")
        for item in self.items:
            item.validate_structure()
        if (
            self.collaborative_diagnostics.returned_candidate_count <= 0
            or len(self.items) > self.collaborative_diagnostics.returned_candidate_count
        ):
            _contract_error(
                "hybrid_result_invalid",
                "Hybrid items exceed collaborative candidate support",
            )
        if tuple(item.rank for item in self.items) != tuple(range(1, len(self.items) + 1)):
            _contract_error("hybrid_result_invalid", "Hybrid result ranks are not contiguous")
        if type(self.positive_sources) is not tuple or any(
            type(source) is not PositiveFeedbackSource for source in self.positive_sources
        ):
            _contract_error("hybrid_result_invalid", "Hybrid positive sources are invalid")


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
