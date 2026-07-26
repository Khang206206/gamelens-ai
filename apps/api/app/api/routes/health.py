from fastapi import APIRouter, Request, Response, status

from app.core.exceptions import INTERNAL_SERVER_ERROR_RESPONSES
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthResponse,
            "description": "The database or required schema is not ready.",
        },
        **INTERNAL_SERVER_ERROR_RESPONSES,
    },
    summary="Report application health",
)
def health(request: Request, response: Response) -> HealthResponse:
    settings = request.app.state.settings
    database_ready = request.app.state.database_health_check(request.app.state.database_engine)
    if not database_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if database_ready else "degraded",
        service=settings.app_name,
        environment=settings.environment,
        database="ready" if database_ready else "unavailable",
    )
