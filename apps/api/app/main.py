from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from sqlalchemy import Engine

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import UnhandledExceptionMiddleware, register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import (
    create_database_engine,
    create_session_factory,
    database_is_ready,
)
from app.services.recommendation import (
    CollaborativeArtifactComponent,
    HybridContentComponent,
    HybridRankingOrchestrator,
    LifecycleAwareHybridOrchestrator,
    RecommendationService,
    create_collaborative_component,
    create_recommendation_service,
)

ANONYMOUS_SESSION_SECURITY_SCHEME = "AnonymousSessionCookie"
PROTECTED_API_PREFIX = "/api/v1/me"
SESSION_API_PATH = "/api/v1/anonymous-sessions"
UNSAFE_METHODS = frozenset({"post", "put", "delete", "patch"})


def _append_header_parameter(
    operation: dict[str, Any],
    *,
    name: str,
    required: bool,
    description: str,
    schema: dict[str, Any] | None = None,
) -> None:
    parameters = operation.setdefault("parameters", [])
    if any(
        parameter.get("in") == "header"
        and str(parameter.get("name", "")).casefold() == name.casefold()
        for parameter in parameters
        if isinstance(parameter, dict)
    ):
        return
    parameters.append(
        {
            "name": name,
            "in": "header",
            "required": required,
            "description": description,
            "schema": schema or {"type": "string"},
        }
    )


def _configure_openapi_contract(app: FastAPI, settings: Settings) -> None:
    """Describe cookie/CSRF and no-store contracts that are resolved at runtime."""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            summary=app.summary,
            description=app.description,
            routes=app.routes,
        )
        components = schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes[ANONYMOUS_SESSION_SECURITY_SCHEME] = {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.anonymous_session_cookie_name,
            "description": "Host-only HttpOnly anonymous-session cookie.",
        }
        for path, path_item in schema.get("paths", {}).items():
            if not isinstance(path_item, dict):
                continue
            protected = path == SESSION_API_PATH or path.startswith(PROTECTED_API_PREFIX)
            if not protected:
                continue
            for method, operation in path_item.items():
                if method not in {"get", "post", "put", "delete", "patch"} or not isinstance(
                    operation, dict
                ):
                    continue
                cookie_requirement = {ANONYMOUS_SESSION_SECURITY_SCHEME: []}
                operation["security"] = (
                    [{}, cookie_requirement]
                    if path == SESSION_API_PATH and method == "post"
                    else [cookie_requirement]
                )
                for response in operation.get("responses", {}).values():
                    if not isinstance(response, dict):
                        continue
                    response.setdefault("headers", {})["Cache-Control"] = {
                        "description": "Protected responses are never stored by caches.",
                        "schema": {"type": "string", "enum": ["no-store"]},
                    }
                if method in UNSAFE_METHODS:
                    _append_header_parameter(
                        operation,
                        name="Origin",
                        required=True,
                        description="Exact browser origin from the configured allowlist.",
                    )
                    _append_header_parameter(
                        operation,
                        name=settings.csrf_header_name,
                        required=not (path == SESSION_API_PATH and method == "post"),
                        description=(
                            "Domain-separated CSRF value returned by the session bootstrap. "
                            "Optional only for first-time consent without a session cookie."
                        ),
                        schema={
                            "type": "string",
                            "pattern": "^[0-9a-f]{64}$",
                            "minLength": 64,
                            "maxLength": 64,
                        },
                    )
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]


def create_app(
    settings: Settings | None = None,
    *,
    database_engine: Engine | None = None,
    database_health_check: Callable[[Engine], bool] = database_is_ready,
    recommendation_service: RecommendationService | None = None,
    collaborative_component: CollaborativeArtifactComponent | None = None,
    hybrid_orchestrator: HybridRankingOrchestrator | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()
    configure_logging(runtime_settings.log_level)
    engine = database_engine or create_database_engine(runtime_settings.database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title=runtime_settings.app_name,
        version="0.3.0",
        description="Consented feedback and artifact-backed recommendation API for GameLens AI.",
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings
    app.state.database_engine = engine
    app.state.session_factory = session_factory
    app.state.database_health_check = database_health_check
    resolved_recommendation_service = recommendation_service or create_recommendation_service(
        runtime_settings.model_artifact_path
    )
    app.state.recommendation_service = resolved_recommendation_service
    app.state.collaborative_component = (
        collaborative_component
        if collaborative_component is not None
        else create_collaborative_component(
            runtime_settings.collaborative_artifact_path,
            environment=runtime_settings.environment,
            allow_test_fixture=runtime_settings.collaborative_allow_test_fixture,
        )
    )
    app.state.hybrid_orchestrator = hybrid_orchestrator
    if app.state.hybrid_orchestrator is None and isinstance(
        resolved_recommendation_service, HybridContentComponent
    ):
        app.state.hybrid_orchestrator = LifecycleAwareHybridOrchestrator(
            resolved_recommendation_service
        )
    app.add_middleware(UnhandledExceptionMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", runtime_settings.csrf_header_name],
    )
    register_exception_handlers(app)
    app.include_router(api_router)
    _configure_openapi_contract(app, runtime_settings)
    return app


app = create_app()
