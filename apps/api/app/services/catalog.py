from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundError
from app.repositories.games import CatalogSort, GameRepository
from app.repositories.taxonomies import TaxonomyRepository
from app.schemas.games import GameDetail, GamePage, GameSummary
from app.schemas.metadata import TaxonomyItem


class CatalogService:
    def __init__(self, session: Session) -> None:
        self.games = GameRepository(session)
        self.taxonomies = TaxonomyRepository(session)

    def list_games(
        self,
        *,
        page: int,
        page_size: int,
        q: str | None = None,
        genre: str | None = None,
        tag: str | None = None,
        platform: str | None = None,
        sort: CatalogSort = CatalogSort.POPULARITY,
    ) -> GamePage:
        filters = {
            "q": q,
            "genre": genre,
            "tag": tag,
            "platform": platform,
        }
        total = self.games.count(**filters)
        games = self.games.list(
            page=page,
            page_size=page_size,
            sort=sort,
            **filters,
        )
        return GamePage.build(
            items=[GameSummary.model_validate(game) for game in games],
            page=page,
            page_size=page_size,
            total=total,
        )

    def get_game(self, game_id: int) -> GameDetail:
        game = self.games.get(game_id)
        if game is None:
            raise ResourceNotFoundError(
                f"Game {game_id} was not found",
                code="game_not_found",
            )
        return GameDetail.model_validate(game)

    def list_genres(self) -> list[TaxonomyItem]:
        return [TaxonomyItem.model_validate(item) for item in self.taxonomies.list_genres()]

    def list_tags(self) -> list[TaxonomyItem]:
        return [TaxonomyItem.model_validate(item) for item in self.taxonomies.list_tags()]

    def list_platforms(self) -> list[TaxonomyItem]:
        return [TaxonomyItem.model_validate(item) for item in self.taxonomies.list_platforms()]
