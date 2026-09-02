from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from gamelens_recommender import (
    CollaborativeBuildMetadata,
    CollaborativeNeighborhoods,
    LoadedCollaborativeArtifact,
    audit_profiles,
    build_collaborative_artifact,
    fit_collaborative_neighborhoods,
    inspect_collaborative_artifact,
    load_collaborative_artifact,
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
from app.services.recommendation.readiness import CollaborativeReadinessRow

DEFAULT_LIVE_VALIDITY_DAYS = 30


class CollaborativeLiveBuildError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _PreparedLiveBuild:
    snapshot: ExtractedInteractionSnapshot
    neighborhoods: CollaborativeNeighborhoods
    interaction_fingerprint: str
    retained_user_ids: tuple[int, ...]
    retained_authority_horizons: tuple[datetime, ...]


@dataclass(frozen=True)
class _ArtifactLifecycle:
    built_at: datetime
    cutoff: datetime
    data_revision: int
    valid_until: datetime


class CollaborativeLiveBuildService:
    """Build and transactionally register one identity-free live artifact."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def build(self, output: Path, *, settings: Settings, build_id: str) -> dict[str, object]:
        contribution_version = self._live_contribution_version(settings)
        if output.exists() or output.is_symlink():
            raise CollaborativeLiveBuildError(
                "artifact_target_exists",
                "Collaborative artifact target already exists",
            )
        self._preflight_registry(build_id)
        prepared = self._prepare_live_build(settings, contribution_version)
        snapshot = prepared.snapshot
        built_at = self._verified_build_time(snapshot.data_revision)
        valid_until = min(
            built_at + timedelta(days=DEFAULT_LIVE_VALIDITY_DAYS),
            *prepared.retained_authority_horizons,
        )
        if valid_until <= built_at:
            raise CollaborativeLiveBuildError(
                "authority_horizon_expired",
                "A retained contributor authority horizon expired before live build promotion",
            )
        metadata = CollaborativeBuildMetadata(
            source_kind="live",
            catalog_fingerprint=snapshot.catalog_fingerprint,
            interaction_fingerprint=prepared.interaction_fingerprint,
            build_id=build_id,
            built_at=built_at,
            cutoff=snapshot.cutoff,
            consent_version=contribution_version,
            data_revision=snapshot.data_revision,
            valid_until=valid_until,
        )
        built = build_collaborative_artifact(
            prepared.neighborhoods,
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
        registration = self._registration(
            prepared,
            build_id=build_id,
            consent_version=contribution_version,
            valid_until=valid_until,
        )
        self._register(registration)
        result["promotion"] = self._promotion_result(
            registered_revision=registration.registered_revision,
            contributor_count=len(registration.contributor_user_ids),
        )
        return result

    def recover(
        self,
        artifact_path: Path,
        *,
        settings: Settings,
        build_id: str,
    ) -> dict[str, object]:
        """Register an exact orphan bundle or acknowledge an already-committed retry."""

        contribution_version = self._live_contribution_version(settings)
        CollaborativeArtifactRegistryRepository.require_valid_build_id(build_id)
        if artifact_path.is_symlink() or not artifact_path.is_dir():
            raise CollaborativeLiveBuildError(
                "recovery_target_invalid",
                "Live recovery requires an existing non-symlink artifact directory",
            )
        artifact = load_collaborative_artifact(
            artifact_path,
            expected_consent_version=contribution_version,
            now=datetime.min.replace(tzinfo=UTC),
        )
        lifecycle = self._artifact_lifecycle(
            artifact,
            build_id=build_id,
            contribution_version=contribution_version,
        )
        database_time = self._verified_build_time(lifecycle.data_revision)
        artifact = load_collaborative_artifact(
            artifact_path,
            expected_catalog_fingerprint=artifact.catalog_fingerprint,
            expected_data_revision=lifecycle.data_revision,
            expected_consent_version=contribution_version,
            now=database_time,
        )
        result = inspect_collaborative_artifact(
            artifact_path,
            expected_catalog_fingerprint=artifact.catalog_fingerprint,
            expected_data_revision=lifecycle.data_revision,
            expected_consent_version=contribution_version,
            now=database_time,
        )

        registered = self._registered_build(build_id)
        if registered is not None:
            self._assert_registered_matches(registered, artifact, lifecycle)
            result["promotion"] = self._promotion_result(
                registered_revision=registered.registered_revision,
                contributor_count=registered.contributor_count,
                recovery="already_registered",
            )
            return result

        self._preflight_registry(build_id)
        prepared = self._prepare_live_build(
            settings,
            contribution_version,
            cutoff=lifecycle.cutoff,
            expected_revision=lifecycle.data_revision,
        )
        self._assert_orphan_matches(prepared, artifact, lifecycle)
        registration = self._registration(
            prepared,
            build_id=build_id,
            consent_version=contribution_version,
            valid_until=lifecycle.valid_until,
        )
        try:
            self._register(registration)
            recovery = "orphan_registered"
        except CollaborativeRegistryMutationError as error:
            if error.code != "build_already_registered":
                raise
            registered = self._registered_build(build_id)
            if registered is None:
                raise
            self._assert_registered_matches(registered, artifact, lifecycle)
            recovery = "already_registered"
        result["promotion"] = self._promotion_result(
            registered_revision=registration.registered_revision,
            contributor_count=len(registration.contributor_user_ids),
            recovery=recovery,
        )
        return result

    @staticmethod
    def _live_contribution_version(settings: Settings) -> str:
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
        return contribution_version

    def _prepare_live_build(
        self,
        settings: Settings,
        contribution_version: str,
        *,
        cutoff: datetime | None = None,
        expected_revision: int | None = None,
    ) -> _PreparedLiveBuild:
        snapshot = self._extract_snapshot(
            settings,
            contribution_version,
            cutoff=cutoff,
        )
        if expected_revision is not None and snapshot.data_revision != expected_revision:
            raise CollaborativeLiveBuildError(
                "revision_race",
                "Collaborative source revision changed before orphan recovery",
            )
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
        return _PreparedLiveBuild(
            snapshot=snapshot,
            neighborhoods=neighborhoods,
            interaction_fingerprint=str(audit["interaction_fingerprint"]),
            retained_user_ids=retained_user_ids,
            retained_authority_horizons=retained_authority_horizons,
        )

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
        *,
        cutoff: datetime | None = None,
    ) -> ExtractedInteractionSnapshot:
        session = self.session_factory()
        try:
            begin_collaborative_snapshot(session, cutoff=cutoff)
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

    def _registered_build(self, build_id: str) -> CollaborativeReadinessRow | None:
        session = self.session_factory()
        try:
            repository = CollaborativeArtifactRegistryRepository(session)
            repository.require_valid_build_id(build_id)
            return repository.readiness(build_id)
        except SQLAlchemyError as error:
            raise CollaborativeLiveBuildError(
                "live_build_database_failed",
                "Live build registry recovery lookup failed",
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

    @staticmethod
    def _registration(
        prepared: _PreparedLiveBuild,
        *,
        build_id: str,
        consent_version: str,
        valid_until: datetime,
    ) -> LiveBuildRegistration:
        return LiveBuildRegistration(
            build_id=build_id,
            registered_revision=prepared.snapshot.data_revision,
            contributor_user_ids=prepared.retained_user_ids,
            consent_version=consent_version,
            catalog_fingerprint=prepared.snapshot.catalog_fingerprint,
            interaction_fingerprint=prepared.interaction_fingerprint,
            cutoff=prepared.snapshot.cutoff,
            valid_until=valid_until,
        )

    @staticmethod
    def _promotion_result(
        *,
        registered_revision: int,
        contributor_count: int,
        recovery: str | None = None,
    ) -> dict[str, object]:
        result: dict[str, object] = {
            "registered": True,
            "status": "active",
            "registered_revision": registered_revision,
            "contributor_count": contributor_count,
        }
        if recovery is not None:
            result["recovery"] = recovery
        return result

    @staticmethod
    def _artifact_lifecycle(
        artifact: LoadedCollaborativeArtifact,
        *,
        build_id: str,
        contribution_version: str,
    ) -> _ArtifactLifecycle:
        source = artifact.manifest["source"]
        lifecycle = artifact.manifest["lifecycle"]
        if source["kind"] != "live":
            raise CollaborativeLiveBuildError(
                "recovery_source_invalid",
                "Only live collaborative artifacts can enter registry recovery",
            )
        if artifact.build_id != build_id:
            raise CollaborativeLiveBuildError(
                "recovery_build_mismatch",
                "Recovery build ID does not match the artifact build ID",
            )
        if lifecycle["consent_version"] != contribution_version:
            raise CollaborativeLiveBuildError(
                "recovery_consent_mismatch",
                "Recovery consent version does not match the artifact",
            )
        return _ArtifactLifecycle(
            built_at=_parse_artifact_timestamp(artifact.manifest["build"]["built_at"]),
            cutoff=_parse_artifact_timestamp(lifecycle["cutoff"]),
            data_revision=int(lifecycle["data_revision"]),
            valid_until=_parse_artifact_timestamp(lifecycle["valid_until"]),
        )

    @staticmethod
    def _assert_orphan_matches(
        prepared: _PreparedLiveBuild,
        artifact: LoadedCollaborativeArtifact,
        lifecycle: _ArtifactLifecycle,
    ) -> None:
        expected_valid_until = min(
            lifecycle.built_at + timedelta(days=DEFAULT_LIVE_VALIDITY_DAYS),
            *prepared.retained_authority_horizons,
        )
        neighborhoods = prepared.neighborhoods
        exact_payload = (
            artifact.item_slugs == neighborhoods.item_slugs
            and np.array_equal(artifact.item_support, neighborhoods.item_support)
            and np.array_equal(artifact.neighbor_indices, neighborhoods.neighbor_indices)
            and np.array_equal(artifact.neighbor_indptr, neighborhoods.neighbor_indptr)
            and np.array_equal(artifact.similarity_units, neighborhoods.similarity_units)
            and np.array_equal(artifact.pair_support, neighborhoods.pair_support)
        )
        if (
            prepared.snapshot.cutoff != lifecycle.cutoff
            or prepared.snapshot.data_revision != lifecycle.data_revision
            or prepared.snapshot.catalog_fingerprint != artifact.catalog_fingerprint
            or prepared.interaction_fingerprint != artifact.interaction_fingerprint
            or lifecycle.valid_until != expected_valid_until
            or not exact_payload
        ):
            raise CollaborativeLiveBuildError(
                "orphan_artifact_mismatch",
                "Orphan artifact does not exactly match its reconstructible live snapshot",
            )

    @staticmethod
    def _assert_registered_matches(
        registered: CollaborativeReadinessRow,
        artifact: LoadedCollaborativeArtifact,
        lifecycle: _ArtifactLifecycle,
    ) -> None:
        matrix = artifact.manifest["matrix"]
        if registered.status != "active" or registered.invalidation_epoch != 0:
            raise CollaborativeLiveBuildError(
                "registered_build_not_active",
                "Recovery never reactivates an invalidated or retired build",
            )
        if (
            registered.source_kind != "live"
            or registered.build_id != artifact.build_id
            or registered.registered_revision != lifecycle.data_revision
            or registered.contributor_count != matrix["retained_contributors"]
            or registered.consent_version != artifact.manifest["lifecycle"]["consent_version"]
            or registered.catalog_fingerprint != artifact.catalog_fingerprint
            or registered.interaction_fingerprint != artifact.interaction_fingerprint
            or registered.cutoff is None
            or registered.cutoff.astimezone(UTC) != lifecycle.cutoff
            or registered.valid_until.astimezone(UTC) != lifecycle.valid_until
        ):
            raise CollaborativeLiveBuildError(
                "artifact_registry_mismatch",
                "Registered build metadata does not exactly match the recovery artifact",
            )


def _parse_artifact_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise CollaborativeLiveBuildError(
            "artifact_lifecycle_invalid",
            "Recovery artifact lifecycle timestamp is invalid",
        )
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError as error:
        raise CollaborativeLiveBuildError(
            "artifact_lifecycle_invalid",
            "Recovery artifact lifecycle timestamp is invalid",
        ) from error
    return parsed.astimezone(UTC)
