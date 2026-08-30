import re
from datetime import datetime
from typing import cast

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models import CollaborativeArtifactBuild
from app.services.recommendation.collaborative import CollaborativeArtifactSourceKind
from app.services.recommendation.readiness import (
    CollaborativeReadinessRow,
    CollaborativeRegistryStatus,
)

_SAFE_BUILD_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


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
