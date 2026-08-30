from fastapi import APIRouter, Request

from app.api.dependencies import DatabaseSession
from app.core.exceptions import DATABASE_ERROR_RESPONSES
from app.schemas.model_status import ModelStatusResponse
from app.services.recommendation.status import RecommendationStatusService

router = APIRouter(prefix="/models", tags=["models"])


@router.get(
    "/status",
    response_model=ModelStatusResponse,
    responses={**DATABASE_ERROR_RESPONSES},
    summary="Report recommendation model readiness",
    response_model_exclude_unset=True,
)
def model_status(request: Request, session: DatabaseSession) -> ModelStatusResponse:
    return RecommendationStatusService(
        session,
        request.app.state.recommendation_service,
        request.app.state.collaborative_component,
        current_consent_version=(
            request.app.state.settings.collaborative_contribution_consent_version
        ),
    ).resolve()
