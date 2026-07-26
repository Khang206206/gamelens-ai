from enum import StrEnum

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Game, Genre, Platform, Tag


class CatalogSort(StrEnum):
    POPULARITY = "popularity"
    RATING = "rating"
    RELEASE_DATE = "release_date"
    TITLE = "title"


class GameRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _apply_filters(
        statement: Select,
        *,
        q: str | None,
        genre: str | None,
        tag: str | None,
        platform: str | None,
    ) -> Select:
        if q is not None:
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            statement = statement.where(Game.title.ilike(f"%{escaped}%", escape="\\"))
        if genre is not None:
            statement = statement.where(Game.genres.any(Genre.slug == genre))
        if tag is not None:
            statement = statement.where(Game.tags.any(Tag.slug == tag))
        if platform is not None:
            statement = statement.where(Game.platforms.any(Platform.slug == platform))
        return statement

    @staticmethod
    def _apply_sort(statement: Select, sort: CatalogSort) -> Select:
        if sort is CatalogSort.RATING:
            return statement.order_by(
                Game.average_rating.desc().nulls_last(),
                Game.rating_count.desc(),
                Game.id.asc(),
            )
        if sort is CatalogSort.RELEASE_DATE:
            return statement.order_by(
                Game.release_date.desc().nulls_last(),
                Game.id.asc(),
            )
        if sort is CatalogSort.TITLE:
            return statement.order_by(func.lower(Game.title).asc(), Game.id.asc())
        return statement.order_by(Game.popularity_score.desc(), Game.id.asc())

    def count(
        self,
        *,
        q: str | None = None,
        genre: str | None = None,
        tag: str | None = None,
        platform: str | None = None,
    ) -> int:
        statement = self._apply_filters(
            select(func.count(Game.id)),
            q=q,
            genre=genre,
            tag=tag,
            platform=platform,
        )
        return self.session.scalar(statement) or 0

    def list(
        self,
        *,
        page: int,
        page_size: int,
        q: str | None = None,
        genre: str | None = None,
        tag: str | None = None,
        platform: str | None = None,
        sort: CatalogSort = CatalogSort.POPULARITY,
    ) -> list[Game]:
        statement = select(Game).options(
            selectinload(Game.genres),
            selectinload(Game.tags),
            selectinload(Game.platforms),
        )
        statement = self._apply_filters(
            statement,
            q=q,
            genre=genre,
            tag=tag,
            platform=platform,
        )
        statement = self._apply_sort(statement, sort)
        statement = statement.offset((page - 1) * page_size).limit(page_size)
        return list(self.session.scalars(statement).all())

    def get(self, game_id: int) -> Game | None:
        statement = (
            select(Game)
            .where(Game.id == game_id)
            .options(
                selectinload(Game.genres),
                selectinload(Game.tags),
                selectinload(Game.platforms),
            )
        )
        return self.session.scalar(statement)
