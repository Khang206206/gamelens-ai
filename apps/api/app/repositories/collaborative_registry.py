import re
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

from sqlalchemy import Select, func, insert, select
from sqlalchemy.orm import Session

from app.db.models import (
    CollaborativeArtifactBuild,
    CollaborativeArtifactContributor,
    CollaborativeDataRevision,
)
from app.services.recommendation.collaborative import CollaborativeArtifactSourceKind
from app.services.recommendation.readiness import (
    CollaborativeReadinessRow,
    CollaborativeRegistryStatus,
)

_SAFE_BUILD_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
CONTRIBUTOR_INSERT_BATCH_SIZE = 1_000


class CollaborativeRegistryMutationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class LiveBuildRegistration:
    build_id: str
    registered_revision: int
    contributor_user_ids: tuple[int, ...]
    consent_version: str
    catalog_fingerprint: str
    interaction_fingerprint: str
    cutoff: datetime
    valid_until: datetime


@dataclass(frozen=True)
class CollaborativeLifecycleTransition:
    operation: Literal["invalidate", "retire"]
    build_id: str
    previous_status: CollaborativeRegistryStatus
    status: CollaborativeRegistryStatus
    changed: bool
    invalidation_epoch: int
    effective_at: datetime


@dataclass(frozen=True)
class CollaborativeRegistryLifecycleState:
    build_id: str
    status: CollaborativeRegistryStatus
    invalidation_epoch: int


def collaborative_readiness_query(build_id: str) -> Select[tuple[object, ...]]:
    """Select one registry row without joining or counting contributor membership."""

    return (
        select(
            CollaborativeArtifactBuild.build_id,
            CollaborativeArtifactBuild.source_kind,
            CollaborativeArtifactBuild.status,
            CollaborativeArtifactBuild.registered_revision,
            CollaborativeArtifactBuild.invalidation_epoch,
            CollaborativeArtifactBuild.current_contributor_count.label("contributor_count"),
            CollaborativeArtifactBuild.consent_version,
            CollaborativeArtifactBuild.catalog_fingerprint,
            CollaborativeArtifactBuild.interaction_fingerprint,
            CollaborativeArtifactBuild.cutoff,
            CollaborativeArtifactBuild.valid_until,
        )
        .where(CollaborativeArtifactBuild.build_id == build_id)
        .limit(1)
    )


class CollaborativeArtifactRegistryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def readiness(self, build_id: str) -> CollaborativeReadinessRow | None:
        if type(build_id) is not str or _SAFE_BUILD_ID.fullmatch(build_id) is None:
            return None
        record = (
            self.session.execute(collaborative_readiness_query(build_id)).mappings().one_or_none()
        )
        if record is None:
            return None
        return CollaborativeReadinessRow(
            build_id=cast(str, record["build_id"]),
            source_kind=cast(CollaborativeArtifactSourceKind, record["source_kind"]),
            status=cast(CollaborativeRegistryStatus, record["status"]),
            registered_revision=cast(int, record["registered_revision"]),
            invalidation_epoch=cast(int, record["invalidation_epoch"]),
            contributor_count=cast(int, record["contributor_count"]),
            consent_version=cast(str, record["consent_version"]),
            catalog_fingerprint=cast(str, record["catalog_fingerprint"]),
            interaction_fingerprint=cast(str, record["interaction_fingerprint"]),
            cutoff=cast(datetime | None, record["cutoff"]),
            valid_until=cast(datetime, record["valid_until"]),
        )

    @staticmethod
    def require_valid_build_id(build_id: str) -> None:
        if type(build_id) is not str or _SAFE_BUILD_ID.fullmatch(build_id) is None:
            raise CollaborativeRegistryMutationError(
                "build_id_invalid",
                "Live build ID must be a safe identifier of at most 128 characters",
            )

    def assert_live_build_slot(self, build_id: str) -> None:
        self.require_valid_build_id(build_id)
        existing = self.session.scalar(
            select(CollaborativeArtifactBuild.build_id)
            .where(CollaborativeArtifactBuild.build_id == build_id)
            .limit(1)
        )
        if existing is not None:
            raise CollaborativeRegistryMutationError(
                "build_already_registered",
                "Collaborative build ID is already registered",
            )
        active = self.session.scalar(
            select(CollaborativeArtifactBuild.build_id)
            .where(CollaborativeArtifactBuild.status == "active")
            .order_by(CollaborativeArtifactBuild.build_id)
            .limit(1)
        )
        if active is not None:
            raise CollaborativeRegistryMutationError(
                "active_build_exists",
                "An active collaborative build must be retired before another promotion",
            )

    def invalidate_live_build(self, build_id: str) -> CollaborativeLifecycleTransition:
        build = self._locked_build(build_id)
        previous_status = cast(CollaborativeRegistryStatus, build.status)
        if previous_status == "retired":
            raise CollaborativeRegistryMutationError(
                "retired_build_terminal",
                "A retired collaborative build cannot be invalidated or reactivated",
            )
        if previous_status == "invalidated":
            if build.invalidated_at is None:
                raise CollaborativeRegistryMutationError(
                    "registry_state_invalid",
                    "Invalidated collaborative build is missing its lifecycle timestamp",
                )
            return CollaborativeLifecycleTransition(
                operation="invalidate",
                build_id=build.build_id,
                previous_status=previous_status,
                status=previous_status,
                changed=False,
                invalidation_epoch=build.invalidation_epoch,
                effective_at=build.invalidated_at,
            )

        effective_at = self._database_time()
        build.status = "invalidated"
        build.invalidation_epoch += 1
        build.invalidated_at = effective_at
        self.session.flush()
        return CollaborativeLifecycleTransition(
            operation="invalidate",
            build_id=build.build_id,
            previous_status=previous_status,
            status="invalidated",
            changed=True,
            invalidation_epoch=build.invalidation_epoch,
            effective_at=effective_at,
        )

    def retire_live_build(self, build_id: str) -> CollaborativeLifecycleTransition:
        build = self._locked_build(build_id)
        previous_status = cast(CollaborativeRegistryStatus, build.status)
        if previous_status == "active":
            raise CollaborativeRegistryMutationError(
                "active_build_retirement_forbidden",
                "Invalidate an active collaborative build before retiring it",
            )
        if previous_status == "retired":
            if build.retired_at is None:
                raise CollaborativeRegistryMutationError(
                    "registry_state_invalid",
                    "Retired collaborative build is missing its lifecycle timestamp",
                )
            return CollaborativeLifecycleTransition(
                operation="retire",
                build_id=build.build_id,
                previous_status=previous_status,
                status=previous_status,
                changed=False,
                invalidation_epoch=build.invalidation_epoch,
                effective_at=build.retired_at,
            )

        effective_at = self._database_time()
        build.status = "retired"
        build.retired_at = effective_at
        self.session.flush()
        return CollaborativeLifecycleTransition(
            operation="retire",
            build_id=build.build_id,
            previous_status=previous_status,
            status="retired",
            changed=True,
            invalidation_epoch=build.invalidation_epoch,
            effective_at=effective_at,
        )

    def lifecycle_states(
        self,
        build_ids: Collection[str],
    ) -> dict[str, CollaborativeRegistryLifecycleState]:
        normalized = tuple(sorted(set(build_ids)))
        for build_id in normalized:
            self.require_valid_build_id(build_id)
        if not normalized:
            return {}
        rows = self.session.execute(
            select(
                CollaborativeArtifactBuild.build_id,
                CollaborativeArtifactBuild.status,
                CollaborativeArtifactBuild.invalidation_epoch,
            ).where(CollaborativeArtifactBuild.build_id.in_(normalized))
        ).all()
        return {
            row.build_id: CollaborativeRegistryLifecycleState(
                build_id=row.build_id,
                status=cast(CollaborativeRegistryStatus, row.status),
                invalidation_epoch=row.invalidation_epoch,
            )
            for row in rows
        }

    def register_live_build(self, registration: LiveBuildRegistration) -> None:
        self._validate_registration(registration)
        self.assert_live_build_slot(registration.build_id)
        build = CollaborativeArtifactBuild(
            build_id=registration.build_id,
            source_kind="live",
            status="active",
            registered_revision=registration.registered_revision,
            invalidation_epoch=0,
            expected_contributor_count=len(registration.contributor_user_ids),
            current_contributor_count=0,
            consent_version=registration.consent_version,
            catalog_fingerprint=registration.catalog_fingerprint,
            interaction_fingerprint=registration.interaction_fingerprint,
            cutoff=registration.cutoff,
            valid_until=registration.valid_until,
            invalidated_at=None,
            retired_at=None,
        )
        self.session.add(build)
        self.session.flush()
        contributor_rows = (
            {"build_id": registration.build_id, "user_id": user_id}
            for user_id in registration.contributor_user_ids
        )
        batch: list[dict[str, object]] = []
        for row in contributor_rows:
            batch.append(row)
            if len(batch) == CONTRIBUTOR_INSERT_BATCH_SIZE:
                self.session.execute(insert(CollaborativeArtifactContributor), batch)
                batch.clear()
        if batch:
            self.session.execute(insert(CollaborativeArtifactContributor), batch)
        self.session.flush()
        self.session.refresh(build)
        if build.current_contributor_count != len(registration.contributor_user_ids):
            raise CollaborativeRegistryMutationError(
                "lineage_count_mismatch",
                "Registered contributor lineage count does not match the live artifact",
            )

        current_revision = self.session.scalar(
            select(CollaborativeDataRevision.revision)
            .where(CollaborativeDataRevision.singleton_id == 1)
            .with_for_update()
        )
        if current_revision is None:
            raise CollaborativeRegistryMutationError(
                "revision_unavailable",
                "Collaborative source revision singleton is unavailable",
            )
        if current_revision != registration.registered_revision:
            raise CollaborativeRegistryMutationError(
                "revision_race",
                "Collaborative source revision changed before registry promotion",
            )
        competing_active = self.session.scalar(
            select(CollaborativeArtifactBuild.build_id)
            .where(
                CollaborativeArtifactBuild.status == "active",
                CollaborativeArtifactBuild.build_id != registration.build_id,
            )
            .order_by(CollaborativeArtifactBuild.build_id)
            .limit(1)
        )
        if competing_active is not None:
            raise CollaborativeRegistryMutationError(
                "active_build_exists",
                "An active collaborative build must be retired before another promotion",
            )

    @staticmethod
    def _validate_registration(registration: LiveBuildRegistration) -> None:
        contributor_ids = registration.contributor_user_ids
        if not contributor_ids or len(set(contributor_ids)) != len(contributor_ids):
            raise CollaborativeRegistryMutationError(
                "lineage_invalid",
                "Live build contributor lineage must be non-empty and unique",
            )
        if any(type(user_id) is not int or user_id <= 0 for user_id in contributor_ids):
            raise CollaborativeRegistryMutationError(
                "lineage_invalid",
                "Live build contributor lineage contains an invalid user reference",
            )

    def _locked_build(self, build_id: str) -> CollaborativeArtifactBuild:
        self.require_valid_build_id(build_id)
        build = self.session.scalar(
            select(CollaborativeArtifactBuild)
            .where(CollaborativeArtifactBuild.build_id == build_id)
            .with_for_update()
        )
        if build is None:
            raise CollaborativeRegistryMutationError(
                "build_not_registered",
                "Collaborative build is not registered",
            )
        return build

    def _database_time(self) -> datetime:
        database_time = self.session.scalar(select(func.clock_timestamp()))
        if database_time is None:
            raise CollaborativeRegistryMutationError(
                "database_time_unavailable",
                "PostgreSQL lifecycle timestamp is unavailable",
            )
        return database_time
