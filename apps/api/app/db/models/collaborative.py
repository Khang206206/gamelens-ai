from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class CollaborativeContributionConsent(TimestampMixin, Base):
    """Separate, optional authority for aggregate collaborative-data contribution."""

    __tablename__ = "collaborative_contribution_consents"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(consent_version)) > 0",
            name="consent_version_non_blank",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "withdrawn_at IS NULL OR withdrawn_at >= granted_at",
            name="withdrawal_not_before_grant",
        ).ddl_if(dialect="postgresql"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    consent_version: Mapped[str] = mapped_column(String(100), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CollaborativeDataRevision(Base):
    """Single monotonic source revision used to invalidate derived collaborative data."""

    __tablename__ = "collaborative_data_revision"
    __table_args__ = (
        CheckConstraint("singleton_id = 1", name="singleton_id_is_one"),
        CheckConstraint("revision >= 0", name="revision_non_negative"),
    )

    singleton_id: Mapped[int] = mapped_column(
        SmallInteger,
        primary_key=True,
        default=1,
        server_default="1",
    )
    revision: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CollaborativeArtifactBuild(TimestampMixin, Base):
    """Protected live-build registry state; artifacts contain no contributor identity."""

    __tablename__ = "collaborative_artifact_builds"
    __table_args__ = (
        CheckConstraint(
            "build_id ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'",
            name="build_id_format",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint("source_kind = 'live'", name="source_kind_live"),
        CheckConstraint(
            "status IN ('active', 'invalidated', 'retired')",
            name="status_allowed",
        ),
        CheckConstraint("registered_revision >= 0", name="registered_revision_non_negative"),
        CheckConstraint("invalidation_epoch >= 0", name="invalidation_epoch_non_negative"),
        CheckConstraint(
            "expected_contributor_count > 0 AND current_contributor_count >= 0 "
            "AND current_contributor_count <= expected_contributor_count",
            name="contributor_counts_valid",
        ),
        CheckConstraint(
            "length(btrim(consent_version)) > 0",
            name="consent_version_non_blank",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "catalog_fingerprint ~ '^[0-9a-f]{64}$'",
            name="catalog_fingerprint_format",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "interaction_fingerprint ~ '^[0-9a-f]{64}$'",
            name="interaction_fingerprint_format",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint("valid_until > created_at", name="validity_horizon_future"),
        CheckConstraint(
            "(status = 'active' AND invalidation_epoch = 0 "
            "AND invalidated_at IS NULL AND retired_at IS NULL) OR "
            "(status = 'invalidated' AND invalidation_epoch > 0 "
            "AND invalidated_at IS NOT NULL AND retired_at IS NULL) OR "
            "(status = 'retired' AND retired_at IS NOT NULL "
            "AND (invalidated_at IS NULL OR retired_at >= invalidated_at))",
            name="lifecycle_valid",
        ),
        Index(
            "ix_collaborative_artifact_builds_status_valid_until_build_id",
            "status",
            "valid_until",
            "build_id",
        ),
    )

    build_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="live")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    registered_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    invalidation_epoch: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    expected_contributor_count: Mapped[int] = mapped_column(Integer, nullable=False)
    current_contributor_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    consent_version: Mapped[str] = mapped_column(String(100), nullable=False)
    catalog_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    interaction_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CollaborativeArtifactContributor(Base):
    """Database-only membership used for targeted invalidation and count defense."""

    __tablename__ = "collaborative_artifact_contributors"
    __table_args__ = (
        Index(
            "ix_collaborative_artifact_contributors_user_id_build_id",
            "user_id",
            "build_id",
        ),
    )

    build_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("collaborative_artifact_builds.build_id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
