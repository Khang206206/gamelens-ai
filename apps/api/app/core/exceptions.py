import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)

INTERNAL_SERVER_ERROR_RESPONSES = {
    500: {
        "model": ErrorResponse,
        "description": "An unexpected internal error occurred.",
    }
}
DATABASE_ERROR_RESPONSES = {
    503: {
        "model": ErrorResponse,
        "description": "The database is temporarily unavailable.",
    },
    **INTERNAL_SERVER_ERROR_RESPONSES,
}
VALIDATION_ERROR_RESPONSES = {
    422: {
        "model": ErrorResponse,
        "description": "Request validation failed.",
    },
    **DATABASE_ERROR_RESPONSES,
}
RECOMMENDATION_ERROR_RESPONSES = {
    422: {
        "model": ErrorResponse,
        "description": "Recommendation request validation failed.",
    },
    503: {
        "model": ErrorResponse,
        "description": "The recommendation model or database is temporarily unavailable.",
    },
    **INTERNAL_SERVER_ERROR_RESPONSES,
}


class UnhandledExceptionMiddleware:
    """Convert unexpected HTTP failures before the outer CORS middleware exits."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_with_state(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_with_state)
        except Exception as exc:
            if response_started:
                raise
            response = await internal_error_handler(Request(scope), exc)
            await response(scope, receive, send)


class DomainError(Exception):
    status_code = 400
    code = "domain_error"
    clear_session_cookie = False

    def __init__(
        self,
        message: str,
        *,
        details: Any | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if code is not None:
            self.code = code


class ResourceNotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class RecommendationValidationError(DomainError):
    status_code = 422
    code = "recommendation_validation_error"


class RecommendationUnavailableError(DomainError):
    status_code = 503
    code = "recommendation_unavailable"


class AnonymousSessionRequiredError(DomainError):
    status_code = 401
    code = "anonymous_session_required"

    def __init__(
        self, message: str = "An active anonymous session is required", *, clear: bool = False
    ):
        super().__init__(message)
        self.clear_session_cookie = clear


class OriginNotAllowedError(DomainError):
    status_code = 403
    code = "origin_not_allowed"


class CsrfValidationError(DomainError):
    status_code = 403
    code = "csrf_validation_failed"


class ConsentVersionOutdatedError(DomainError):
    status_code = 409
    code = "consent_version_outdated"


class SavedPreferencesStaleError(DomainError):
    status_code = 409
    code = "saved_preferences_stale"


class RecommendationGenerationOutcomeUnknownError(DomainError):
    status_code = 503
    code = "generation_outcome_unknown"


def error_payload(
    *,
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, dict[str, Any]]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def _protected_response_headers(
    request: Request,
    headers: dict[str, str] | None = None,
) -> dict[str, str]:
    result = dict(headers or {})
    if request.url.path == "/api/v1/anonymous-sessions" or request.url.path.startswith(
        "/api/v1/me"
    ):
        result["Cache-Control"] = "no-store"
    return result


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    response = JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(
            error_payload(code=exc.code, message=exc.message, details=exc.details)
        ),
    )
    if exc.clear_session_cookie:
        from app.core.security import clear_session_cookie

        clear_session_cookie(response, request.app.state.settings)
    response.headers.update(_protected_response_headers(request))
    return response


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            error_payload(
                code="validation_error",
                message="Request validation failed",
                details=exc.errors(),
            )
        ),
        headers=_protected_response_headers(request),
    )


async def http_error_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    code = "not_found" if exc.status_code == 404 else "http_error"
    message = str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(error_payload(code=code, message=message)),
        headers=_protected_response_headers(request, exc.headers),
    )


async def database_error_handler(request: Request, exc: DBAPIError) -> JSONResponse:
    logger.error(
        "Database operation failed",
        extra={
            "error_type": type(exc).__name__,
            "method": request.method,
            "path": request.url.path,
            "status_code": 503,
        },
    )
    return JSONResponse(
        status_code=503,
        content=error_payload(
            code="database_unavailable",
            message="The database is temporarily unavailable",
        ),
        headers=_protected_response_headers(request),
    )


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled application error",
        extra={
            "error_type": type(exc).__name__,
            "method": request.method,
            "path": request.url.path,
            "status_code": 500,
        },
    )
    return JSONResponse(
        status_code=500,
        content=error_payload(
            code="internal_error",
            message="An unexpected internal error occurred",
        ),
        headers=_protected_response_headers(request),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(DBAPIError, database_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, internal_error_handler)
