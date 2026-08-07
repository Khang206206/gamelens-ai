from fastapi import APIRouter, Request

from app.api.dependencies import DatabaseSession
from app.core.exceptions import RECOMMENDATION_ERROR_RESPONSES
from app.repositories.recommendation_catalog import RecommendationCatalogRepository
from app.schemas.recommendations import RecommendationRequest, RecommendationResponse
from app.services.recommendation.application import RecommendationApplicationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post(
    "",
    response_model=RecommendationResponse,
    responses={**RECOMMENDATION_ERROR_RESPONSES},
    summary="Recommend games from anonymous request-scoped preferences",
)
def create_recommendations(
    payload: RecommendationRequest,
    request: Request,
    session: DatabaseSession,
) -> RecommendationResponse:
    service = request.app.state.recommendation_service
    service.ensure_intrinsic_ready()
    catalog = RecommendationCatalogRepository(session).load()
    return RecommendationApplicationService(
        catalog,
        service,
    ).recommend(payload)
