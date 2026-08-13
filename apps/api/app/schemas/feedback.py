from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from app.schemas.common import ApiSchema

HalfStepRating = Annotated[Decimal, Field(ge=0, le=10, decimal_places=1)]


class FeedbackReplaceRequest(ApiSchema):
    model_config = ConfigDict(extra="forbid")

    reaction: Literal["liked", "disliked"] | None
    played: bool
    wishlisted: bool
    rating: HalfStepRating | None

    @model_validator(mode="after")
    def rating_uses_half_steps(self) -> "FeedbackReplaceRequest":
        if self.rating is not None and self.rating * 2 != (self.rating * 2).to_integral_value():
            raise ValueError("rating must use half-point increments")
        return self

    @property
    def is_empty(self) -> bool:
        return (
            self.reaction is None
            and not self.played
            and not self.wishlisted
            and self.rating is None
        )


class FeedbackResource(ApiSchema):
    game_id: int
    game_slug: str
    game_title: str
    reaction: Literal["liked", "disliked"] | None
    played: bool
    wishlisted: bool
    rating: float | None
    latest_occurred_at: datetime


class FeedbackPage(ApiSchema):
    items: list[FeedbackResource]
    page: int
    page_size: int
    total: int
