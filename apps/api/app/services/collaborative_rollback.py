from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from gamelens_recommender import load_collaborative_artifact
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import begin_repeatable_read
from app.repositories.recommendation_catalog import RecommendationCatalogRepository
from app.services.recommendation.collaborative import CollaborativeArtifactComponent
from app.services.recommendation.readiness_resolution import CollaborativeReadinessResolver


class CollaborativeRollbackError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class CollaborativeRollbackService:
    """Check a manual rollback candidate against the same snapshot rules as serving."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def check(self, artifact_path: Path, *, settings: Settings) -> dict[str, object]:
        artifact_path = artifact_path.expanduser().absolute()
        if any(
            path.is_symlink() or path.is_junction()
            for path in (artifact_path, *artifact_path.parents)
        ):
            raise CollaborativeRollbackError(
                "rollback_path_invalid", "Rollback requires a non-linked artifact directory"
            )
        artifact_path = artifact_path.resolve(strict=True)
        # Intrinsic validation first; expiry is evaluated using PostgreSQL time
        # together with current catalog and protected registry state below.
        artifact = load_collaborative_artifact(
            artifact_path, allow_fixture=False, now=datetime.min.replace(tzinfo=UTC)
        )
        component = CollaborativeArtifactComponent.loaded(artifact, source_kind="live")
        with self.session_factory() as session:
            try:
                begin_repeatable_read(session, read_only=True)
                catalog = RecommendationCatalogRepository(session).load()
                readiness = CollaborativeReadinessResolver(
                    session,
                    component,
                    current_consent_version=settings.collaborative_contribution_consent_version,
                ).resolve(
                    catalog_fingerprint=(
                        catalog.model_snapshot.fingerprint if catalog.model_snapshot else ""
                    )
                )
                if readiness.state != "ready":
                    raise CollaborativeRollbackError(
                        "rollback_candidate_not_ready",
                        f"Rollback candidate is not ready: {readiness.reason}",
                    )
                return {
                    "status": "ok",
                    "operation": "rollback_check",
                    "candidate_artifact_path": str(artifact_path),
                    "build_id": artifact.manifest["build"]["id"],
                    "readiness": "ready",
                    "configuration_changed": False,
                    "requires_manual_configuration_and_restart": True,
                }
            finally:
                session.rollback()
