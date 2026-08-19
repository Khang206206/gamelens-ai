from fastapi import APIRouter, Request, Response

from app.api.dependencies import DatabaseSession
from app.api.v1.routes.anonymous_sessions import (
    SESSION_RESPONSES,
    _credential,
    _no_store,
    _protected_credential,
    _settings,
)
from app.schemas.preferences import PreferenceReplaceRequest, PreferenceResponse
from app.services.preferences import PreferenceService

router = APIRouter(prefix="/me/preferences", tags=["preferences"])


@router.get("", response_model=PreferenceResponse, responses=SESSION_RESPONSES)
def get_preferences(
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> PreferenceResponse:
    _no_store(response)
    return PreferenceService(session, _settings(request)).get(_credential(request))


@router.put("", response_model=PreferenceResponse, responses=SESSION_RESPONSES)
def replace_preferences(
    payload: PreferenceReplaceRequest,
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> PreferenceResponse:
    settings = _settings(request)
    credential = _protected_credential(request)
    _no_store(response)
    return PreferenceService(session, settings).replace(credential, payload)


@router.delete("", status_code=204, responses=SESSION_RESPONSES)
def clear_preferences(request: Request, session: DatabaseSession) -> Response:
    settings = _settings(request)
    credential = _protected_credential(request)
    PreferenceService(session, settings).clear(credential)
    return _no_store(Response(status_code=204))
