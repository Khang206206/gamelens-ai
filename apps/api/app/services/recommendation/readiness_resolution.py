import logging
from datetime import UTC, datetime

from sqlalchemy import DateTime, func, select
from sqlalchemy.orm import Session

from app.core.security import utc_now
from app.repositories.collaborative_registry import CollaborativeArtifactRegistryRepository
from app.services.recommendation.collaborative import CollaborativeArtifactComponent
from app.services.recommendation.readiness import (
    CollaborativeReadiness,
    collaborative_readiness_build_id,
    evaluate_collaborative_readiness,
)

logger = logging.getLogger(__name__)


class CollaborativeReadinessResolver:
    """Resolve optional readiness inside the caller's current transaction snapshot."""

    def __init__(
        self,
        session: Session,
        component: CollaborativeArtifactComponent,
        *,
        current_consent_version: str | None,
    ) -> None:
        self.session = session
        self.component = component
        self.current_consent_version = current_consent_version

    def resolve(self, *, catalog_fingerprint: str) -> CollaborativeReadiness:
        if self.component.load_state != "loaded":
            return evaluate_collaborative_readiness(
                self.component,
                catalog_fingerprint=catalog_fingerprint,
                current_consent_version=self.current_consent_version,
                now=utc_now(),
            )

        try:
            with self.session.begin_nested():
                database_time = self.session.scalar(
                    select(func.current_timestamp(type_=DateTime(timezone=True)))
                )
                if not isinstance(database_time, datetime):
                    raise TypeError("Database time is unavailable")
                if database_time.tzinfo is None or database_time.utcoffset() is None:
                    database_time = database_time.replace(tzinfo=UTC)
                else:
                    database_time = database_time.astimezone(UTC)

                lineage = None
                if self.component.source_kind == "live":
                    build_id = collaborative_readiness_build_id(self.component)
                    if build_id is not None:
                        lineage = CollaborativeArtifactRegistryRepository(self.session).readiness(
                            build_id
                        )
                return evaluate_collaborative_readiness(
                    self.component,
                    catalog_fingerprint=catalog_fingerprint,
                    current_consent_version=self.current_consent_version,
                    now=database_time,
                    lineage=lineage,
                )
        except Exception as error:
            logger.warning(
                "Collaborative readiness evaluation failed closed",
                extra={"error_type": type(error).__name__},
            )
            return CollaborativeReadiness(
                state="stale",
                reason="artifact_incompatible",
                source_kind=self.component.source_kind,
                artifact=None,
            )
