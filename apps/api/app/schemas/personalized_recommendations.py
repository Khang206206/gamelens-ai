from math import isclose, isfinite
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from app.schemas.common import ApiSchema
from app.schemas.games import GameSummary
from app.schemas.recommendations import (
    RecommendationEvidenceResponse,
    RecommendationExplanationResponse,
    ScoreComponentResponse,
)


class PersonalizedRecommendationRequest(ApiSchema):
    model_config = ConfigDict(extra="forbid")

    top_k: int = Field(default=10, ge=1, le=20)


class PersonalizationPolicyIdentity(ApiSchema):
    name: str
    version: str


class PositiveFeedbackSourceResponse(ApiSchema):
    game_slug: str
    kind: Literal["liked", "rating"]


class PersonalizedRecommendationItem(ApiSchema):
    rank: int
    game: GameSummary
    base_ranking_score: float
    base_components: list[ScoreComponentResponse]
    base_weight: float
    base_contribution: float
    feedback_affinity_score: float
    feedback_affinity_weight: float
    feedback_affinity_contribution: float
    pre_played_score: float
    played_factor: float
    played_delta: float
    ranking_score: float
    adjustment_reasons: list[Literal["feedback_affinity", "played_adjustment"]]
    evidence: RecommendationEvidenceResponse
    explanation: RecommendationExplanationResponse


class PersonalizedRecommendationResponse(ApiSchema):
    generation_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    model_name: str
    model_version: str
    data_fingerprint: str
    policy: PersonalizationPolicyIdentity
    response_reason: Literal["recommendations", "no_content_support", "no_eligible_candidates"]
    requested_top_k: int
    positive_feedback_sources: list[PositiveFeedbackSourceResponse]
    items: list[PersonalizedRecommendationItem]


CanonicalSlug = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=220)]
BoundedIdentityPart = Annotated[
    str,
    Field(
        min_length=1,
        max_length=100,
        pattern=r"^\S(?:[^\r\n]*\S)?$",
    ),
]
Sha256Fingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
FixedPointScore = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
FixedPointDelta = Annotated[float, Field(ge=-1, le=0, allow_inf_nan=False)]
CollaborativeSupport = Annotated[int, Field(ge=2, le=500_000)]

Stage5RankingMode = Literal["hybrid", "stage_4_fallback"]
Stage5CandidateOrigin = Literal["content", "collaborative", "both"]
Stage5FallbackReason = Literal[
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
Stage5AdjustmentReason = Literal[
    "feedback_affinity",
    "collaborative_similarity",
    "played_adjustment",
]
CollaborativeSourceKind = Literal["liked", "rating", "saved_game"]

SCORE_SCALE = 1_000_000
MAX_COLLABORATIVE_SOURCE_EDGES = 10


def _fixed_point_units(value: float, *, label: str) -> int:
    scaled = value * SCORE_SCALE
    units = round(scaled)
    if not isfinite(value) or not isclose(scaled, units, rel_tol=0, abs_tol=1e-6):
        raise ValueError(f"{label} must use the six-decimal fixed-point scale")
    return units


def _contribution_units(raw_units: int, weight_units: int) -> int:
    return (raw_units * weight_units + SCORE_SCALE // 2) // SCORE_SCALE


class Stage5PolicyIdentity(ApiSchema):
    model_config = ConfigDict(extra="forbid")

    name: BoundedIdentityPart
    version: BoundedIdentityPart


class CollaborativeModelIdentityResponse(ApiSchema):
    model_config = ConfigDict(extra="forbid")

    name: BoundedIdentityPart
    version: BoundedIdentityPart
    interaction_fingerprint: Sha256Fingerprint
    scoring_policy: Stage5PolicyIdentity


class Stage5PositiveFeedbackSourceResponse(ApiSchema):
    model_config = ConfigDict(extra="forbid")

    game_slug: CanonicalSlug
    kind: Literal["liked", "rating"]


class CollaborativeSourceEdgeResponse(ApiSchema):
    model_config = ConfigDict(extra="forbid")

    source_game_slug: CanonicalSlug
    source_kind: CollaborativeSourceKind
    similarity_score: FixedPointScore
    pair_support: CollaborativeSupport

    @model_validator(mode="after")
    def validate_fixed_point_score(self) -> "CollaborativeSourceEdgeResponse":
        if _fixed_point_units(self.similarity_score, label="Collaborative similarity") <= 0:
            raise ValueError("Collaborative similarity must be positive")
        return self


class Stage5ScoreComponentResponse(ScoreComponentResponse):
    model_config = ConfigDict(extra="forbid")

    raw_score: FixedPointScore
    weight: FixedPointScore
    contribution: FixedPointScore


class Stage5PersonalizedRecommendationItem(PersonalizedRecommendationItem):
    model_config = ConfigDict(extra="forbid")

    rank: int = Field(ge=1, le=20)
    base_ranking_score: FixedPointScore
    base_components: list[Stage5ScoreComponentResponse] = Field(min_length=3, max_length=3)
    base_weight: FixedPointScore
    base_contribution: FixedPointScore
    feedback_affinity_score: FixedPointScore
    feedback_affinity_weight: FixedPointScore
    feedback_affinity_contribution: FixedPointScore
    candidate_origin: Stage5CandidateOrigin
    collaborative_supported: bool
    collaborative_score: FixedPointScore
    collaborative_weight: FixedPointScore
    collaborative_contribution: FixedPointScore
    collaborative_item_support: CollaborativeSupport | None
    collaborative_source_edges: list[CollaborativeSourceEdgeResponse] = Field(
        max_length=MAX_COLLABORATIVE_SOURCE_EDGES
    )
    pre_played_score: FixedPointScore
    played_factor: FixedPointScore
    played_delta: FixedPointDelta
    ranking_score: FixedPointScore
    adjustment_reasons: list[Stage5AdjustmentReason] = Field(max_length=3)

    @model_validator(mode="after")
    def validate_stage_5_evidence(self) -> "Stage5PersonalizedRecommendationItem":
        component_names = tuple(component.name for component in self.base_components)
        if component_names != ("content", "platform", "popularity"):
            raise ValueError("Base components must use canonical order")

        numeric_values = {
            "base ranking score": self.base_ranking_score,
            "base weight": self.base_weight,
            "base contribution": self.base_contribution,
            "feedback affinity score": self.feedback_affinity_score,
            "feedback affinity weight": self.feedback_affinity_weight,
            "feedback affinity contribution": self.feedback_affinity_contribution,
            "collaborative score": self.collaborative_score,
            "collaborative weight": self.collaborative_weight,
            "collaborative contribution": self.collaborative_contribution,
            "pre-played score": self.pre_played_score,
            "played factor": self.played_factor,
            "played delta": self.played_delta,
            "ranking score": self.ranking_score,
        }
        units = {
            label: _fixed_point_units(value, label=label.capitalize())
            for label, value in numeric_values.items()
        }
        component_units: list[tuple[int, int, int]] = []
        for component in self.base_components:
            raw_units = _fixed_point_units(
                component.raw_score,
                label=f"{component.name.title()} raw score",
            )
            weight_units = _fixed_point_units(
                component.weight,
                label=f"{component.name.title()} weight",
            )
            contribution_units = _fixed_point_units(
                component.contribution,
                label=f"{component.name.title()} contribution",
            )
            if contribution_units != _contribution_units(raw_units, weight_units):
                raise ValueError("Base component contribution is not reconstructible")
            component_units.append((raw_units, weight_units, contribution_units))

        if sum(value[2] for value in component_units) != units["base ranking score"]:
            raise ValueError("Base ranking score is not reconstructible")
        if units["base contribution"] != _contribution_units(
            units["base ranking score"], units["base weight"]
        ):
            raise ValueError("Base contribution is not reconstructible")
        if units["feedback affinity contribution"] != _contribution_units(
            units["feedback affinity score"], units["feedback affinity weight"]
        ):
            raise ValueError("Feedback contribution is not reconstructible")
        if units["collaborative contribution"] != _contribution_units(
            units["collaborative score"], units["collaborative weight"]
        ):
            raise ValueError("Collaborative contribution is not reconstructible")

        expected_pre_played = (
            units["base contribution"]
            + units["feedback affinity contribution"]
            + units["collaborative contribution"]
        )
        expected_final = _contribution_units(expected_pre_played, units["played factor"])
        if units["pre-played score"] != expected_pre_played:
            raise ValueError("Pre-played score is not reconstructible")
        if units["ranking score"] != expected_final:
            raise ValueError("Final score is not reconstructible")
        if units["played delta"] != expected_final - expected_pre_played:
            raise ValueError("Played delta is not reconstructible")

        expected_adjustments: list[Stage5AdjustmentReason] = []
        if units["feedback affinity weight"] > 0:
            expected_adjustments.append("feedback_affinity")
        if self.collaborative_supported:
            expected_adjustments.append("collaborative_similarity")
        if units["played delta"] < 0:
            expected_adjustments.append("played_adjustment")
        if self.adjustment_reasons != expected_adjustments:
            raise ValueError("Adjustment reasons are inconsistent")

        source_slugs = [edge.source_game_slug for edge in self.collaborative_source_edges]
        if len(source_slugs) != len(set(source_slugs)):
            raise ValueError("Collaborative source edges must be distinct")
        edge_units = [
            _fixed_point_units(edge.similarity_score, label="Collaborative similarity")
            for edge in self.collaborative_source_edges
        ]
        expected_edge_order = sorted(
            zip(self.collaborative_source_edges, edge_units, strict=True),
            key=lambda value: (
                -value[1],
                -value[0].pair_support,
                value[0].source_game_slug,
            ),
        )
        if self.collaborative_source_edges != [value[0] for value in expected_edge_order]:
            raise ValueError("Collaborative source edge order is invalid")
        if self.collaborative_supported:
            if (
                self.candidate_origin == "content"
                or units["collaborative score"] <= 0
                or units["collaborative weight"] <= 0
                or self.collaborative_item_support is None
                or not self.collaborative_source_edges
            ):
                raise ValueError("Supported collaborative evidence is incomplete")
            expected_collaborative_score = (sum(edge_units) + len(edge_units) // 2) // len(
                edge_units
            )
            if units["collaborative score"] != expected_collaborative_score:
                raise ValueError("Collaborative score is not reconstructible from source edges")
            if any(
                edge.pair_support > self.collaborative_item_support
                for edge in self.collaborative_source_edges
            ):
                raise ValueError("Collaborative pair support exceeds item support")
        elif (
            self.candidate_origin != "content"
            or units["collaborative score"] != 0
            or units["collaborative contribution"] != 0
            or self.collaborative_item_support is not None
            or self.collaborative_source_edges
        ):
            raise ValueError("Unsupported collaborative evidence must remain empty")
        return self


class Stage5PersonalizedRecommendationResponse(PersonalizedRecommendationResponse):
    model_config = ConfigDict(extra="forbid")

    model_name: BoundedIdentityPart
    model_version: BoundedIdentityPart
    data_fingerprint: Sha256Fingerprint
    policy: Stage5PolicyIdentity
    ranking_mode: Stage5RankingMode
    fallback_reason: Stage5FallbackReason | None
    hybrid_policy: Stage5PolicyIdentity | None
    collaborative_model: CollaborativeModelIdentityResponse | None
    requested_top_k: int = Field(ge=1, le=20)
    positive_feedback_sources: list[Stage5PositiveFeedbackSourceResponse] = Field(max_length=5)
    items: list[Stage5PersonalizedRecommendationItem] = Field(max_length=20)

    @model_validator(mode="after")
    def validate_stage_5_mode(self) -> "Stage5PersonalizedRecommendationResponse":
        item_slugs = [item.game.slug for item in self.items]
        if len(item_slugs) != len(set(item_slugs)):
            raise ValueError("Recommendation items must be distinct")
        if [item.rank for item in self.items] != list(range(1, len(self.items) + 1)):
            raise ValueError("Recommendation ranks must be contiguous and server ordered")
        if len(self.items) > self.requested_top_k:
            raise ValueError("Recommendation items exceed requested top-K")

        positive_source_slugs = [source.game_slug for source in self.positive_feedback_sources]
        if len(positive_source_slugs) != len(set(positive_source_slugs)):
            raise ValueError("Positive feedback sources must be distinct")

        if self.ranking_mode == "hybrid":
            if (
                self.response_reason != "recommendations"
                or not self.items
                or self.fallback_reason is not None
                or self.hybrid_policy is None
                or self.collaborative_model is None
            ):
                raise ValueError("Hybrid response identity is incomplete")
        elif (
            self.fallback_reason is None
            or self.hybrid_policy is not None
            or self.collaborative_model is not None
            or any(
                item.collaborative_supported
                or item.collaborative_weight != 0
                or item.collaborative_contribution != 0
                for item in self.items
            )
        ):
            raise ValueError("Fallback response must not claim collaborative application")
        return self


MAX_EVENT_FEEDBACK_COUNT = 100_000


class RecommendationEventContext(ApiSchema):
    model_config = ConfigDict(extra="forbid")

    top_k: int = Field(ge=1, le=20)
    selected_game_slugs: list[CanonicalSlug] = Field(max_length=25)
    preferred_genres: list[CanonicalSlug] = Field(max_length=20)
    preferred_tags: list[CanonicalSlug] = Field(max_length=25)
    preferred_platforms: list[CanonicalSlug] = Field(max_length=10)
    positive_source_slugs: list[CanonicalSlug] = Field(max_length=5)
    # Counts are scalar audit metadata, so their bounds follow the maximum
    # supported artifact catalog rather than the much smaller JSON list caps.
    disliked_count: int = Field(ge=0, le=MAX_EVENT_FEEDBACK_COUNT)
    played_count: int = Field(ge=0, le=MAX_EVENT_FEEDBACK_COUNT)
    positive_source_count: int = Field(ge=0, le=5)
    effective_state_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class RecommendationEventResultItem(ApiSchema):
    model_config = ConfigDict(extra="forbid")

    slug: CanonicalSlug
    rank: int = Field(ge=1, le=20)
    base_units: int = Field(ge=0, le=1_000_000)
    final_units: int = Field(ge=0, le=1_000_000)
    affinity_units: int = Field(ge=0, le=1_000_000)
    played_delta_units: int = Field(ge=-1_000_000, le=0)
