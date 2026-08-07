from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from app.schemas.common import ApiSchema
from app.schemas.games import GameSummary

Slug = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
GameId = Annotated[int, Field(ge=1, le=2_147_483_647)]


class RecommendationRequest(ApiSchema):
    model_config = ConfigDict(extra="forbid")

    selected_game_ids: list[GameId] = Field(default_factory=list, max_length=5)
    preferred_genres: list[Slug] = Field(default_factory=list, max_length=5)
    preferred_tags: list[Slug] = Field(default_factory=list, max_length=10)
    preferred_platforms: list[Slug] = Field(default_factory=list, max_length=6)
    top_k: int = Field(default=10, ge=1, le=20)

    @model_validator(mode="after")
    def validate_context(self) -> "RecommendationRequest":
        collections = (
            self.selected_game_ids,
            self.preferred_genres,
            self.preferred_tags,
            self.preferred_platforms,
        )
        if any(len(values) != len(set(values)) for values in collections):
            raise ValueError("Selection values must be distinct")
        if not (self.selected_game_ids or self.preferred_genres or self.preferred_tags):
            raise ValueError("Select at least one game, genre, or tag")
        return self


class RecommendationModelIdentity(ApiSchema):
    name: str
    version: str
    data_fingerprint: str


class ScoreComponentResponse(ApiSchema):
    name: Literal["content", "platform", "popularity"]
    raw_score: float
    weight: float
    contribution: float


class EvidenceValue(ApiSchema):
    slug: str
    name: str


class SimilarSelectedGameResponse(ApiSchema):
    slug: str
    title: str
    similarity_score: float


class RecommendationEvidenceResponse(ApiSchema):
    matching_genres: list[EvidenceValue]
    matching_tags: list[EvidenceValue]
    preferred_platforms: list[EvidenceValue]
    similar_selected_games: list[SimilarSelectedGameResponse]
    popularity_score: float


class RecommendationExplanationResponse(ApiSchema):
    summary: str
    reasons: list[str]


class RecommendationItemResponse(ApiSchema):
    rank: int
    ranking_score: float
    game: GameSummary
    components: list[ScoreComponentResponse]
    evidence: RecommendationEvidenceResponse
    explanation: RecommendationExplanationResponse


class RecommendationResponse(ApiSchema):
    model: RecommendationModelIdentity
    response_reason: Literal["recommendations", "no_content_support"]
    requested_top_k: int
    items: list[RecommendationItemResponse]
