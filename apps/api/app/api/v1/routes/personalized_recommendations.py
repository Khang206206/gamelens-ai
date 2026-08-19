from fastapi import APIRouter, Request, Response

from app.api.dependencies import DatabaseSession
from app.api.v1.routes.anonymous_sessions import (
    SESSION_RESPONSES,
    _no_store,
    _protected_credential,
    _settings,
)
from app.core.exceptions import RECOMMENDATION_ERROR_RESPONSES
from app.schemas.personalized_recommendations import (
    PersonalizedRecommendationRequest,
    PersonalizedRecommendationResponse,
)
from app.services.personalized_recommendation import PersonalizedRecommendationService

router = APIRouter(prefix="/me/recommendations", tags=["personalized-recommendations"])


@router.post(
    "",
    response_model=PersonalizedRecommendationResponse,
    responses={**SESSION_RESPONSES, **RECOMMENDATION_ERROR_RESPONSES},
    summary="Generate and durably log a feedback-aware recommendation",
)
def create_personalized_recommendations(
    payload: PersonalizedRecommendationRequest,
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> PersonalizedRecommendationResponse:
    credential = _protected_credential(request)
    _no_store(response)
    return PersonalizedRecommendationService(
        session,
        _settings(request),
        request.app.state.recommendation_service,
    ).recommend(credential, top_k=payload.top_k)
