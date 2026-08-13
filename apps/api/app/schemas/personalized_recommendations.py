from typing import Annotated, Literal

from pydantic import ConfigDict, Field

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
