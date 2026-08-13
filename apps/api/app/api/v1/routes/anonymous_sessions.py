from fastapi import APIRouter, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.api.dependencies import DatabaseSession
from app.core.config import Settings
from app.core.exceptions import (
    VALIDATION_ERROR_RESPONSES,
    AnonymousSessionRequiredError,
    CsrfValidationError,
    OriginNotAllowedError,
)
from app.core.security import (
    SessionCredential,
    clear_session_cookie,
    csrf_matches,
    origin_is_allowed,
    parse_session_credential,
    set_session_cookie,
)
from app.schemas.anonymous_sessions import (
    AnonymousSessionConsentRequest,
    AnonymousSessionResponse,
)
from app.schemas.common import ErrorResponse
from app.services.anonymous_identity import AnonymousIdentityService

router = APIRouter(tags=["anonymous-session"])

SESSION_RESPONSES = {
    401: {
        "model": ErrorResponse,
        "description": "An active anonymous session is required.",
    },
    403: {
        "model": ErrorResponse,
        "description": "The request Origin or CSRF token is invalid.",
    },
    409: {
        "model": ErrorResponse,
        "description": "Consent or saved personalization state requires attention.",
    },
    **VALIDATION_ERROR_RESPONSES,
}


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _credential(request: Request) -> SessionCredential | None:
    settings = _settings(request)
    raw_token = request.cookies.get(settings.anonymous_session_cookie_name)
    credential = parse_session_credential(settings, raw_token)
    if raw_token is not None and credential is None:
        raise AnonymousSessionRequiredError(clear=True)
    return credential


def _require_origin(request: Request) -> None:
    if not origin_is_allowed(_settings(request), request.headers.get("origin")):
        raise OriginNotAllowedError("The request Origin is not allowed")


def _csrf_header(request: Request) -> str | None:
    return request.headers.get(_settings(request).csrf_header_name)


def _protected_credential(request: Request) -> SessionCredential:
    """Validate browser-origin and double-submit material without touching the DB."""
    _require_origin(request)
    settings = _settings(request)
    credential = _credential(request)
    if credential is None:
        raise AnonymousSessionRequiredError()
    if not csrf_matches(
        settings.anonymous_session_secret,
        credential.raw_token,
        _csrf_header(request),
    ):
        raise CsrfValidationError("The CSRF token is missing or invalid")
    return credential


def _no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post(
    "/anonymous-sessions",
    response_model=AnonymousSessionResponse,
    status_code=201,
    responses={200: {"model": AnonymousSessionResponse}, **SESSION_RESPONSES},
    summary="Create or explicitly renew a consented anonymous session",
)
def create_anonymous_session(
    payload: AnonymousSessionConsentRequest,
    request: Request,
    session: DatabaseSession,
) -> Response:
    _require_origin(request)
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
    if content_type != "application/json":
        raise CsrfValidationError("Anonymous session creation requires application/json")
    settings = _settings(request)
    result = AnonymousIdentityService(session, settings).create_or_reconsent(
        requested_consent_version=payload.consent_version,
        credential=_credential(request),
        csrf_candidate=_csrf_header(request),
    )
    response = JSONResponse(
        status_code=result.status_code,
        content=jsonable_encoder(result.response),
    )
    _no_store(response)
    if result.raw_token_to_set is not None:
        set_session_cookie(
            response,
            settings,
            result.raw_token_to_set,
            expires_at=result.response.expires_at,
            now=result.now,
        )
    return response


@router.get(
    "/me",
    response_model=AnonymousSessionResponse,
    responses=SESSION_RESPONSES,
    summary="Inspect the current anonymous session lifecycle",
)
def get_current_session(request: Request, session: DatabaseSession) -> Response:
    response_payload = AnonymousIdentityService(session, _settings(request)).bootstrap(
        _credential(request)
    )
    return _no_store(JSONResponse(content=jsonable_encoder(response_payload)))


@router.delete(
    "/me",
    status_code=204,
    responses=SESSION_RESPONSES,
    summary="Withdraw consent and delete all anonymous user data",
)
def delete_current_session(request: Request, session: DatabaseSession) -> Response:
    settings = _settings(request)
    AnonymousIdentityService(session, settings).delete(
        _protected_credential(request),
        csrf_candidate=_csrf_header(request),
    )
    response = Response(status_code=204)
    _no_store(response)
    clear_session_cookie(response, settings)
    return response
