from datetime import date, datetime
from math import ceil

from app.schemas.common import ApiSchema
from app.schemas.metadata import TaxonomyItem


class GameSummary(ApiSchema):
    id: int
    title: str
    slug: str
    release_date: date | None
    developer: str | None
    publisher: str | None
    average_rating: float | None
    rating_count: int
    popularity_score: float
    genres: list[TaxonomyItem]
    tags: list[TaxonomyItem]
    platforms: list[TaxonomyItem]
    cover_image_url: str | None


class GameDetail(GameSummary):
    description: str
    created_at: datetime
    updated_at: datetime


class GamePage(ApiSchema):
    items: list[GameSummary]
    page: int
    page_size: int
    total: int
    total_pages: int

    @classmethod
    def build(
        cls,
        *,
        items: list[GameSummary],
        page: int,
        page_size: int,
        total: int,
    ) -> "GamePage":
        return cls(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if total else 0,
        )
