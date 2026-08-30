from sqlalchemy.orm import Session

from app.db.session import begin_repeatable_read
from app.repositories.recommendation_catalog import RecommendationCatalogRepository
from app.schemas.model_status import (
    CollaborativeComponentStatus,
    ContentComponentStatus,
    ModelComponentsStatus,
    ModelStatusResponse,
)
from app.services.recommendation.base import RecommendationService
from app.services.recommendation.collaborative import CollaborativeArtifactComponent
from app.services.recommendation.readiness import CollaborativeReadiness
from app.services.recommendation.readiness_resolution import CollaborativeReadinessResolver

_MISSING_CATALOG_FINGERPRINT = ""


class RecommendationStatusService:
    """Resolve required and optional model status at one request boundary."""

    def __init__(
        self,
        session: Session,
        recommendation_service: RecommendationService,
        collaborative_component: CollaborativeArtifactComponent,
        *,
        current_consent_version: str | None,
    ) -> None:
        self.session = session
        self.recommendation_service = recommendation_service
        self.collaborative_component = collaborative_component
        self.current_consent_version = current_consent_version

    def resolve(self) -> ModelStatusResponse:
        if (
            not self.recommendation_service.needs_catalog
            and self.collaborative_component.load_state != "loaded"
        ):
            content_status = self.recommendation_service.status()
            collaborative_status = self._readiness_resolver().resolve(
                catalog_fingerprint=_MISSING_CATALOG_FINGERPRINT
            )
            return _with_components(content_status, collaborative_status)

        begin_repeatable_read(self.session, read_only=True)
        try:
            catalog = RecommendationCatalogRepository(self.session).load()
            content_status = (
                self.recommendation_service.status(
                    catalog.model_snapshot,
                    catalog_error=catalog.model_unavailable_reason,
                )
                if self.recommendation_service.needs_catalog
                else self.recommendation_service.status()
            )
            collaborative_status = self._collaborative_status(
                catalog_fingerprint=(
                    catalog.model_snapshot.fingerprint
                    if catalog.model_snapshot is not None
                    else _MISSING_CATALOG_FINGERPRINT
                )
            )
            return _with_components(content_status, collaborative_status)
        finally:
            self.session.rollback()

    def _collaborative_status(self, *, catalog_fingerprint: str) -> CollaborativeReadiness:
        return self._readiness_resolver().resolve(catalog_fingerprint=catalog_fingerprint)

    def _readiness_resolver(self) -> CollaborativeReadinessResolver:
        return CollaborativeReadinessResolver(
            self.session,
            self.collaborative_component,
            current_consent_version=self.current_consent_version,
        )


def _with_components(
    content_status: ModelStatusResponse,
    collaborative_status: CollaborativeReadiness,
) -> ModelStatusResponse:
    components = ModelComponentsStatus(
        content=ContentComponentStatus(
            status=content_status.status,
            reason=content_status.unavailable_reason,
        ),
        collaborative=CollaborativeComponentStatus(
            status=collaborative_status.state,
            reason=collaborative_status.reason,
            source_kind=collaborative_status.source_kind,
        ),
    )
    return content_status.model_copy(update={"components": components})
