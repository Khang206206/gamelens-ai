from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from app.api.dependencies import CatalogServiceDependency
from app.core.exceptions import VALIDATION_ERROR_RESPONSES
from app.repositories.games import CatalogSort
from app.schemas.common import ErrorResponse
from app.schemas.games import GameDetail, GamePage

router = APIRouter(prefix="/games", tags=["games"])
MAX_CATALOG_PAGE = 1_000_000
MAX_DATABASE_INTEGER = 2_147_483_647
SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


@router.get(
    "",
    response_model=GamePage,
    responses={**VALIDATION_ERROR_RESPONSES},
    summary="List and filter catalog games",
)
def list_games(
    service: CatalogServiceDependency,
    page: Annotated[int, Query(ge=1, le=MAX_CATALOG_PAGE)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    genre: Annotated[str | None, Query(pattern=SLUG_PATTERN)] = None,
    tag: Annotated[str | None, Query(pattern=SLUG_PATTERN)] = None,
    platform: Annotated[str | None, Query(pattern=SLUG_PATTERN)] = None,
    sort: CatalogSort = CatalogSort.POPULARITY,
) -> GamePage:
    return service.list_games(
        page=page,
        page_size=page_size,
        q=q,
        genre=genre,
        tag=tag,
        platform=platform,
        sort=sort,
    )


@router.get(
    "/{game_id}",
    response_model=GameDetail,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        **VALIDATION_ERROR_RESPONSES,
    },
    summary="Get one catalog game",
)
def get_game(
    game_id: Annotated[int, Path(ge=1, le=MAX_DATABASE_INTEGER)],
    service: CatalogServiceDependency,
) -> GameDetail:
    return service.get_game(game_id)
