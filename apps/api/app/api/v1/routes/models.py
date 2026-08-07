from fastapi import APIRouter, Request

from app.api.dependencies import DatabaseSession
from app.core.exceptions import DATABASE_ERROR_RESPONSES
from app.repositories.recommendation_catalog import RecommendationCatalogRepository
from app.schemas.model_status import ModelStatusResponse

router = APIRouter(prefix="/models", tags=["models"])


@router.get(
    "/status",
    response_model=ModelStatusResponse,
    responses={**DATABASE_ERROR_RESPONSES},
    summary="Report recommendation model readiness",
    response_model_exclude_unset=True,
)
def model_status(request: Request, session: DatabaseSession) -> ModelStatusResponse:
    service = request.app.state.recommendation_service
    if not service.needs_catalog:
        return service.status()
    catalog = RecommendationCatalogRepository(session).load()
    return service.status(
        catalog.model_snapshot,
        catalog_error=catalog.model_unavailable_reason,
    )
