from dataclasses import dataclass

from gamelens_recommender import (
    CatalogItem,
    CatalogSnapshot,
    TaxonomyValue,
    canonical_snapshot,
)
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.db.models import Game, Genre, Platform, Tag
from app.schemas.games import GameSummary


@dataclass(frozen=True)
class RecommendationCatalogSnapshot:
    model_snapshot: CatalogSnapshot | None
    model_unavailable_reason: str | None
    games_by_id: dict[int, GameSummary]
    games_by_slug: dict[str, GameSummary]
    genre_slugs: frozenset[str]
    tag_slugs: frozenset[str]
    platform_slugs: frozenset[str]


class RecommendationCatalogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def load(self) -> RecommendationCatalogSnapshot:
        bind = self.session.get_bind()
        if bind.dialect.name == "postgresql":
            self.session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        games = list(
            self.session.scalars(
                select(Game)
                .options(
                    selectinload(Game.genres),
                    selectinload(Game.tags),
                    selectinload(Game.platforms),
                )
                .order_by(Game.slug)
            ).all()
        )
        model_items = tuple(
            CatalogItem(
                slug=game.slug,
                title=game.title,
                description=game.description,
                developer=game.developer,
                publisher=game.publisher,
                average_rating=(
                    None if game.average_rating is None else float(game.average_rating)
                ),
                rating_count=game.rating_count,
                popularity_score=float(game.popularity_score),
                genres=tuple(
                    TaxonomyValue(slug=value.slug, name=value.name) for value in game.genres
                ),
                tags=tuple(TaxonomyValue(slug=value.slug, name=value.name) for value in game.tags),
                platforms=tuple(
                    TaxonomyValue(slug=value.slug, name=value.name) for value in game.platforms
                ),
            )
            for game in games
        )
        model_snapshot: CatalogSnapshot | None = None
        model_unavailable_reason: str | None = "catalog_stale"
        if model_items:
            try:
                model_snapshot = canonical_snapshot(model_items)
                model_unavailable_reason = None
            except ValueError:
                model_unavailable_reason = "catalog_invalid"
        summaries = [GameSummary.model_validate(game) for game in games]
        return RecommendationCatalogSnapshot(
            model_snapshot=model_snapshot,
            model_unavailable_reason=model_unavailable_reason,
            games_by_id={summary.id: summary for summary in summaries},
            games_by_slug={summary.slug: summary for summary in summaries},
            genre_slugs=frozenset(
                self.session.scalars(select(Genre.slug).order_by(func.lower(Genre.slug))).all()
            ),
            tag_slugs=frozenset(
                self.session.scalars(select(Tag.slug).order_by(func.lower(Tag.slug))).all()
            ),
            platform_slugs=frozenset(
                self.session.scalars(
                    select(Platform.slug).order_by(func.lower(Platform.slug))
                ).all()
            ),
        )
