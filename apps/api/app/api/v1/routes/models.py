from fastapi import APIRouter, Request

from app.core.exceptions import INTERNAL_SERVER_ERROR_RESPONSES
from app.schemas.model_status import ModelStatusResponse

router = APIRouter(prefix="/models", tags=["models"])


@router.get(
    "/status",
    response_model=ModelStatusResponse,
    responses={**INTERNAL_SERVER_ERROR_RESPONSES},
    summary="Report recommendation model readiness",
)
def model_status(request: Request) -> ModelStatusResponse:
    return request.app.state.recommendation_service.status()
