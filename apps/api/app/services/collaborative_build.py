from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from gamelens_recommender import (
    CollaborativeBuildMetadata,
    audit_profiles,
    build_collaborative_artifact,
    fit_collaborative_neighborhoods,
    inspect_collaborative_artifact,
    prune_supported_profiles,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import begin_read_committed
from app.repositories.collaborative_registry import (
    CollaborativeArtifactRegistryRepository,
    CollaborativeRegistryMutationError,
    LiveBuildRegistration,
)
from app.repositories.collaborative_snapshot import (
    CollaborativeSnapshotRepository,
    ExtractedInteractionSnapshot,
    begin_collaborative_snapshot,
    verified_data_revision_time,
    verify_data_revision,
)

DEFAULT_LIVE_VALIDITY_DAYS = 30


class CollaborativeLiveBuildError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class CollaborativeLiveBuildService:
    """Build and transactionally register one identity-free live artifact."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def build(self, output: Path, *, settings: Settings, build_id: str) -> dict[str, object]:
        if (
            not settings.collaborative_live_data_enabled
            or not settings.collaborative_live_promotion_enabled
        ):
            raise CollaborativeLiveBuildError(
                "unapproved_live_source",
                "Live collaborative build and promotion gates must both be enabled",
            )
        contribution_version = settings.collaborative_contribution_consent_version
        if contribution_version is None:
            raise CollaborativeLiveBuildError(
                "contribution_consent_version_required",
                "Live builds require a contribution consent version",
            )
        if output.exists() or output.is_symlink():
            raise CollaborativeLiveBuildError(
                "artifact_target_exists",
                "Collaborative artifact target already exists",
            )
        self._preflight_registry(build_id)
        snapshot = self._extract_snapshot(settings, contribution_version)
        audit = audit_profiles(
            snapshot.profiles,
            source_kind="live",
            catalog_fingerprint=snapshot.catalog_fingerprint,
            exclusion_counts=snapshot.exclusion_counts,
            cutoff=snapshot.cutoff.isoformat(),
            data_revision=snapshot.data_revision,
            consent_version=contribution_version,
        )
        if audit.get("ready_for_functional_build") is not True:
            raise CollaborativeLiveBuildError(
                "insufficient_data",
                "Live interaction snapshot does not pass the functional build thresholds",
            )

        supported = prune_supported_profiles(snapshot.profiles)
        retained_user_ids = tuple(
            snapshot.profile_user_ids[index] for index in supported.source_indices
        )
        retained_authority_horizons = tuple(
            snapshot.profile_authority_valid_until[index] for index in supported.source_indices
        )
        neighborhoods = fit_collaborative_neighborhoods(
            snapshot.profiles,
            catalog_slugs=frozenset(slug for profile in snapshot.profiles for slug in profile),
        )
        if (
            not retained_user_ids
            or len(retained_user_ids) != neighborhoods.retained_contributors
            or len(retained_authority_horizons) != len(retained_user_ids)
        ):
            raise CollaborativeLiveBuildError(
                "lineage_count_mismatch",
                "Support-pruned contributor lineage does not match the fitted artifact",
            )

        built_at = self._verified_build_time(snapshot.data_revision)
        valid_until = min(
            built_at + timedelta(days=DEFAULT_LIVE_VALIDITY_DAYS),
            *retained_authority_horizons,
        )
        if valid_until <= built_at:
            raise CollaborativeLiveBuildError(
                "authority_horizon_expired",
                "A retained contributor authority horizon expired before live build promotion",
            )
        interaction_fingerprint = str(audit["interaction_fingerprint"])
        metadata = CollaborativeBuildMetadata(
            source_kind="live",
            catalog_fingerprint=snapshot.catalog_fingerprint,
            interaction_fingerprint=interaction_fingerprint,
            build_id=build_id,
            built_at=built_at,
            cutoff=snapshot.cutoff,
            consent_version=contribution_version,
            data_revision=snapshot.data_revision,
            valid_until=valid_until,
        )
        built = build_collaborative_artifact(
            neighborhoods,
            output,
            metadata=metadata,
            revision_check=self._revision_check,
        )
        result = inspect_collaborative_artifact(
            built,
            expected_catalog_fingerprint=snapshot.catalog_fingerprint,
            expected_data_revision=snapshot.data_revision,
            expected_consent_version=contribution_version,
        )
        self._register(
            LiveBuildRegistration(
                build_id=build_id,
                registered_revision=snapshot.data_revision,
                contributor_user_ids=retained_user_ids,
                consent_version=contribution_version,
                catalog_fingerprint=snapshot.catalog_fingerprint,
                interaction_fingerprint=interaction_fingerprint,
                cutoff=snapshot.cutoff,
                valid_until=valid_until,
            )
        )
        result["promotion"] = {
            "registered": True,
            "status": "active",
            "registered_revision": snapshot.data_revision,
            "contributor_count": len(retained_user_ids),
        }
        return result

    def _preflight_registry(self, build_id: str) -> None:
        session = self.session_factory()
        try:
            CollaborativeArtifactRegistryRepository(session).assert_live_build_slot(build_id)
        except SQLAlchemyError as error:
            raise CollaborativeLiveBuildError(
                "live_build_database_failed",
                "Live build registry preflight failed",
            ) from error
        finally:
            session.rollback()
            session.close()

    def _extract_snapshot(
        self,
        settings: Settings,
        contribution_version: str,
    ) -> ExtractedInteractionSnapshot:
        session = self.session_factory()
        try:
            begin_collaborative_snapshot(session)
            return CollaborativeSnapshotRepository(session).extract(
                personalization_consent_version=settings.consent_version,
                contribution_consent_version=contribution_version,
            )
        except SQLAlchemyError as error:
            raise CollaborativeLiveBuildError(
                "live_build_database_failed",
                "Live interaction snapshot extraction failed",
            ) from error
        finally:
            session.rollback()
            session.close()

    def _verified_build_time(self, expected_revision: int) -> datetime:
        session = self.session_factory()
        try:
            return verified_data_revision_time(
                session,
                expected_revision=expected_revision,
            )
        except SQLAlchemyError as error:
            raise CollaborativeLiveBuildError(
                "live_build_database_failed",
                "Live build revision verification failed",
            ) from error
        finally:
            session.rollback()
            session.close()

    def _revision_check(self, expected_revision: int) -> bool:
        session = self.session_factory()
        try:
            verify_data_revision(session, expected_revision=expected_revision)
            return True
        except SQLAlchemyError as error:
            raise CollaborativeLiveBuildError(
                "live_build_database_failed",
                "Live build revision verification failed",
            ) from error
        finally:
            session.rollback()
            session.close()

    def _register(self, registration: LiveBuildRegistration) -> None:
        session = self.session_factory()
        try:
            begin_read_committed(session)
            CollaborativeArtifactRegistryRepository(session).register_live_build(registration)
            session.commit()
        except CollaborativeRegistryMutationError:
            session.rollback()
            raise
        except SQLAlchemyError as error:
            session.rollback()
            raise CollaborativeLiveBuildError(
                "live_promotion_rejected",
                "PostgreSQL rejected live artifact registration or contributor authority",
            ) from error
        finally:
            session.close()
