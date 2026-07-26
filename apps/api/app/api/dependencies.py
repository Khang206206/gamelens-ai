from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.session import session_scope
from app.services.catalog import CatalogService


def get_app_db_session(request: Request) -> Generator[Session]:
    yield from session_scope(request.app.state.session_factory)


DatabaseSession = Annotated[Session, Depends(get_app_db_session)]


def get_catalog_service(session: DatabaseSession) -> CatalogService:
    return CatalogService(session)


CatalogServiceDependency = Annotated[CatalogService, Depends(get_catalog_service)]
