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


async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(
            error_payload(code=exc.code, message=exc.message, details=exc.details)
        ),
    )


async def validation_error_handler(
    _request: Request,
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
    )


async def http_error_handler(
    _request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    code = "not_found" if exc.status_code == 404 else "http_error"
    message = str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(error_payload(code=code, message=message)),
        headers=exc.headers,
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
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(DBAPIError, database_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, internal_error_handler)
