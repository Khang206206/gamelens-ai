from fastapi import APIRouter

from app.api.dependencies import CatalogServiceDependency
from app.core.exceptions import DATABASE_ERROR_RESPONSES
from app.schemas.metadata import TaxonomyItem

router = APIRouter(prefix="/metadata", tags=["metadata"])


@router.get(
    "/genres",
    response_model=list[TaxonomyItem],
    responses={**DATABASE_ERROR_RESPONSES},
)
def list_genres(service: CatalogServiceDependency) -> list[TaxonomyItem]:
    return service.list_genres()


@router.get(
    "/tags",
    response_model=list[TaxonomyItem],
    responses={**DATABASE_ERROR_RESPONSES},
)
def list_tags(service: CatalogServiceDependency) -> list[TaxonomyItem]:
    return service.list_tags()


@router.get(
    "/platforms",
    response_model=list[TaxonomyItem],
    responses={**DATABASE_ERROR_RESPONSES},
)
def list_platforms(service: CatalogServiceDependency) -> list[TaxonomyItem]:
    return service.list_platforms()
