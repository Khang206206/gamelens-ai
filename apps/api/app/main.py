from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
from app.services.recommendation import NotConfiguredRecommendationService


def create_app(
    settings: Settings | None = None,
    *,
    database_engine: Engine | None = None,
    database_health_check: Callable[[Engine], bool] = database_is_ready,
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
        version="0.1.0",
        description="Catalog and model-readiness API for GameLens AI.",
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings
    app.state.database_engine = engine
    app.state.session_factory = session_factory
    app.state.database_health_check = database_health_check
    app.state.recommendation_service = NotConfiguredRecommendationService()
    app.add_middleware(UnhandledExceptionMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
