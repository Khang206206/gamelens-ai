from pydantic import ConfigDict, Field, model_validator

from app.schemas.common import ApiSchema
from app.schemas.personalized_recommendations import (
    MAX_COLLABORATIVE_SOURCE_EDGES,
    MAX_EVENT_FEEDBACK_COUNT,
    SCORE_SCALE,
    BoundedIdentityPart,
    CanonicalSlug,
    CollaborativeSupport,
    Sha256Fingerprint,
    Stage5CandidateOrigin,
    Stage5FallbackReason,
    Stage5PolicyIdentity,
    Stage5RankingMode,
)


def _contribution_units(raw_units: int, weight_units: int) -> int:
    return (raw_units * weight_units + SCORE_SCALE // 2) // SCORE_SCALE


class Stage5RecommendationEventCollaborativeIdentity(ApiSchema):
    model_config = ConfigDict(extra="forbid")

    name: BoundedIdentityPart
    version: BoundedIdentityPart
    interaction_fingerprint: Sha256Fingerprint
    scoring_policy: Stage5PolicyIdentity


class Stage5RecommendationEventIdentity(ApiSchema):
    model_config = ConfigDict(extra="forbid")

    content_model_name: BoundedIdentityPart
    content_model_version: BoundedIdentityPart
    content_data_fingerprint: Sha256Fingerprint
    feedback_policy: Stage5PolicyIdentity
    ranking_mode: Stage5RankingMode
    fallback_reason: Stage5FallbackReason | None
    hybrid_policy: Stage5PolicyIdentity | None
    collaborative_model: Stage5RecommendationEventCollaborativeIdentity | None

    @model_validator(mode="after")
    def validate_mode_identity(self) -> "Stage5RecommendationEventIdentity":
        if self.ranking_mode == "hybrid":
            if (
                self.fallback_reason is not None
                or self.hybrid_policy is None
                or self.collaborative_model is None
            ):
                raise ValueError("Hybrid event identity is incomplete")
        elif (
            self.fallback_reason is None
            or self.hybrid_policy is not None
            or self.collaborative_model is not None
        ):
            raise ValueError("Fallback event must not claim collaborative application")
        return self


class Stage5RecommendationEventContext(ApiSchema):
    model_config = ConfigDict(extra="forbid")

    top_k: int = Field(ge=1, le=20)
    ranking_mode: Stage5RankingMode
    fallback_reason: Stage5FallbackReason | None
    selected_game_slugs: list[CanonicalSlug] = Field(max_length=25)
    preferred_genres: list[CanonicalSlug] = Field(max_length=20)
    preferred_tags: list[CanonicalSlug] = Field(max_length=25)
    preferred_platforms: list[CanonicalSlug] = Field(max_length=10)
    positive_source_slugs: list[CanonicalSlug] = Field(max_length=5)
    disliked_count: int = Field(ge=0, le=MAX_EVENT_FEEDBACK_COUNT)
    played_count: int = Field(ge=0, le=MAX_EVENT_FEEDBACK_COUNT)
    positive_source_count: int = Field(ge=0, le=5)
    effective_state_fingerprint: Sha256Fingerprint

    @model_validator(mode="after")
    def validate_context(self) -> "Stage5RecommendationEventContext":
        for values in (
            self.selected_game_slugs,
            self.preferred_genres,
            self.preferred_tags,
            self.preferred_platforms,
            self.positive_source_slugs,
        ):
            if len(values) != len(set(values)):
                raise ValueError("Recommendation event context values must be distinct")
        if self.positive_source_count != len(self.positive_source_slugs):
            raise ValueError("Positive source count does not match the bounded source list")
        if (self.ranking_mode == "hybrid") != (self.fallback_reason is None):
            raise ValueError("Recommendation event mode and fallback reason are inconsistent")
        return self


class Stage5RecommendationEventResultItem(ApiSchema):
    model_config = ConfigDict(extra="forbid")

    slug: CanonicalSlug
    rank: int = Field(ge=1, le=20)
    candidate_origin: Stage5CandidateOrigin
    base_units: int = Field(ge=0, le=SCORE_SCALE)
    base_weight_units: int = Field(ge=0, le=SCORE_SCALE)
    base_contribution_units: int = Field(ge=0, le=SCORE_SCALE)
    affinity_units: int = Field(ge=0, le=SCORE_SCALE)
    affinity_weight_units: int = Field(ge=0, le=SCORE_SCALE)
    affinity_contribution_units: int = Field(ge=0, le=SCORE_SCALE)
    collaborative_supported: bool
    collaborative_units: int = Field(ge=0, le=SCORE_SCALE)
    collaborative_weight_units: int = Field(ge=0, le=SCORE_SCALE)
    collaborative_contribution_units: int = Field(ge=0, le=SCORE_SCALE)
    collaborative_item_support: CollaborativeSupport | None
    collaborative_source_edge_count: int = Field(ge=0, le=MAX_COLLABORATIVE_SOURCE_EDGES)
    pre_played_units: int = Field(ge=0, le=SCORE_SCALE)
    played_factor_units: int = Field(ge=0, le=SCORE_SCALE)
    played_delta_units: int = Field(ge=-SCORE_SCALE, le=0)
    final_units: int = Field(ge=0, le=SCORE_SCALE)

    @model_validator(mode="after")
    def validate_fixed_point_reconstruction(self) -> "Stage5RecommendationEventResultItem":
        if self.base_contribution_units != _contribution_units(
            self.base_units, self.base_weight_units
        ):
            raise ValueError("Base contribution units are not reconstructible")
        if self.affinity_contribution_units != _contribution_units(
            self.affinity_units, self.affinity_weight_units
        ):
            raise ValueError("Feedback contribution units are not reconstructible")
        if self.collaborative_contribution_units != _contribution_units(
            self.collaborative_units, self.collaborative_weight_units
        ):
            raise ValueError("Collaborative contribution units are not reconstructible")

        expected_pre_played = (
            self.base_contribution_units
            + self.affinity_contribution_units
            + self.collaborative_contribution_units
        )
        expected_final = _contribution_units(expected_pre_played, self.played_factor_units)
        if self.pre_played_units != expected_pre_played:
            raise ValueError("Pre-played units are not reconstructible")
        if self.final_units != expected_final:
            raise ValueError("Final units are not reconstructible")
        if self.played_delta_units != expected_final - expected_pre_played:
            raise ValueError("Played delta units are not reconstructible")

        if self.collaborative_supported:
            if (
                self.candidate_origin == "content"
                or self.collaborative_units <= 0
                or self.collaborative_weight_units <= 0
                or self.collaborative_item_support is None
                or self.collaborative_source_edge_count <= 0
            ):
                raise ValueError("Supported collaborative event evidence is incomplete")
        elif (
            self.candidate_origin != "content"
            or self.collaborative_units != 0
            or self.collaborative_contribution_units != 0
            or self.collaborative_item_support is not None
            or self.collaborative_source_edge_count != 0
        ):
            raise ValueError("Unsupported collaborative event evidence must remain empty")
        return self
