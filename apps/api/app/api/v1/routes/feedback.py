from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from app.api.dependencies import DatabaseSession
from app.api.v1.routes.anonymous_sessions import (
    SESSION_RESPONSES,
    _credential,
    _no_store,
    _protected_credential,
    _settings,
)
from app.schemas.common import ErrorResponse
from app.schemas.feedback import FeedbackPage, FeedbackReplaceRequest, FeedbackResource
from app.schemas.recommendations import GameId
from app.services.feedback import FeedbackService

router = APIRouter(prefix="/me", tags=["feedback"])

FEEDBACK_RESPONSES = {
    **SESSION_RESPONSES,
    404: {
        "model": ErrorResponse,
        "description": "The referenced game does not exist.",
    },
}


@router.get("/feedback", response_model=FeedbackPage, responses=SESSION_RESPONSES)
def list_feedback(
    request: Request,
    response: Response,
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1, le=1_000_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> FeedbackPage:
    _no_store(response)
    return FeedbackService(session, _settings(request)).list(
        _credential(request), page=page, page_size=page_size
    )


@router.put(
    "/games/{game_id}/feedback",
    response_model=FeedbackResource | None,
    responses=FEEDBACK_RESPONSES,
)
def replace_game_feedback(
    game_id: GameId,
    payload: FeedbackReplaceRequest,
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> FeedbackResource | None:
    credential = _protected_credential(request)
    _no_store(response)
    return FeedbackService(session, _settings(request)).replace(
        credential, game_id=game_id, payload=payload
    )


@router.delete("/games/{game_id}/feedback", status_code=204, responses=FEEDBACK_RESPONSES)
def clear_game_feedback(
    game_id: GameId,
    request: Request,
    session: DatabaseSession,
) -> Response:
    credential = _protected_credential(request)
    FeedbackService(session, _settings(request)).clear(credential, game_id=game_id)
    return _no_store(Response(status_code=204))
