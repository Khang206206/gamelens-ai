from pydantic import ConfigDict, Field, model_validator

from app.schemas.common import ApiSchema
from app.schemas.recommendations import GameId, Slug


class PreferenceReplaceRequest(ApiSchema):
    model_config = ConfigDict(extra="forbid")

    selected_game_ids: list[GameId] = Field(default_factory=list, max_length=5)
    preferred_genres: list[Slug] = Field(default_factory=list, max_length=5)
    preferred_tags: list[Slug] = Field(default_factory=list, max_length=10)
    preferred_platforms: list[Slug] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def validate_context(self) -> "PreferenceReplaceRequest":
        collections = (
            self.selected_game_ids,
            self.preferred_genres,
            self.preferred_tags,
            self.preferred_platforms,
        )
        if any(len(values) != len(set(values)) for values in collections):
            raise ValueError("Preference values must be distinct")
        if not (self.selected_game_ids or self.preferred_genres or self.preferred_tags):
            raise ValueError("Save at least one game, genre, or tag")
        return self


class SavedGamePreference(ApiSchema):
    id: int
    slug: str
    title: str


class PreferenceResponse(ApiSchema):
    selected_games: list[SavedGamePreference]
    preferred_genres: list[str]
    preferred_tags: list[str]
    preferred_platforms: list[str]
    stale_references: list[str] = Field(max_length=26)
