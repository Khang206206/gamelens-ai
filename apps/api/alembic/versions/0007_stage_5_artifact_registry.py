"""Add protected collaborative artifact registry and contributor lineage.

Revision ID: 0007_stage_5_artifact_registry
Revises: 0006_stage_5_collab_contract
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_stage_5_artifact_registry"
down_revision: str | None = "0006_stage_5_collab_contract"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collaborative_artifact_builds",
        sa.Column("build_id", sa.String(128), nullable=False),
        sa.Column("source_kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("registered_revision", sa.BigInteger(), nullable=False),
        sa.Column("invalidation_epoch", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("expected_contributor_count", sa.Integer(), nullable=False),
        sa.Column("current_contributor_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("consent_version", sa.String(100), nullable=False),
        sa.Column("catalog_fingerprint", sa.String(64), nullable=False),
        sa.Column("interaction_fingerprint", sa.String(64), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "build_id ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'",
            name=op.f("ck_collaborative_artifact_builds_build_id_format"),
        ),
        sa.CheckConstraint(
            "source_kind = 'live'",
            name=op.f("ck_collaborative_artifact_builds_source_kind_live"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'invalidated', 'retired')",
            name=op.f("ck_collaborative_artifact_builds_status_allowed"),
        ),
        sa.CheckConstraint(
            "registered_revision >= 0",
            name=op.f("ck_collaborative_artifact_builds_registered_revision_non_negative"),
        ),
        sa.CheckConstraint(
            "invalidation_epoch >= 0",
            name=op.f("ck_collaborative_artifact_builds_invalidation_epoch_non_negative"),
        ),
        sa.CheckConstraint(
            "expected_contributor_count > 0 AND current_contributor_count >= 0 "
            "AND current_contributor_count <= expected_contributor_count",
            name=op.f("ck_collaborative_artifact_builds_contributor_counts_valid"),
        ),
        sa.CheckConstraint(
            "length(btrim(consent_version)) > 0",
            name=op.f("ck_collaborative_artifact_builds_consent_version_non_blank"),
        ),
        sa.CheckConstraint(
            "catalog_fingerprint ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_collaborative_artifact_builds_catalog_fingerprint_format"),
        ),
        sa.CheckConstraint(
            "interaction_fingerprint ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_collaborative_artifact_builds_interaction_fingerprint_format"),
        ),
        sa.CheckConstraint(
            "valid_until > created_at",
            name=op.f("ck_collaborative_artifact_builds_validity_horizon_future"),
        ),
        sa.CheckConstraint(
            "(status = 'active' AND invalidation_epoch = 0 "
            "AND invalidated_at IS NULL AND retired_at IS NULL) OR "
            "(status = 'invalidated' AND invalidation_epoch > 0 "
            "AND invalidated_at IS NOT NULL AND retired_at IS NULL) OR "
            "(status = 'retired' AND retired_at IS NOT NULL "
            "AND (invalidated_at IS NULL OR retired_at >= invalidated_at))",
            name=op.f("ck_collaborative_artifact_builds_lifecycle_valid"),
        ),
        sa.PrimaryKeyConstraint(
            "build_id",
            name=op.f("pk_collaborative_artifact_builds"),
        ),
    )
    op.create_index(
        "ix_collaborative_artifact_builds_status_valid_until_build_id",
        "collaborative_artifact_builds",
        ["status", "valid_until", "build_id"],
        unique=False,
    )
    op.create_table(
        "collaborative_artifact_contributors",
        sa.Column("build_id", sa.String(128), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["build_id"],
            ["collaborative_artifact_builds.build_id"],
            name=op.f(
                "fk_collaborative_artifact_contributors_build_id_collaborative_artifact_builds"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_collaborative_artifact_contributors_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "build_id",
            "user_id",
            name=op.f("pk_collaborative_artifact_contributors"),
        ),
    )
    op.create_index(
        "ix_collaborative_artifact_contributors_user_id_build_id",
        "collaborative_artifact_contributors",
        ["user_id", "build_id"],
        unique=False,
    )
    op.execute(
        """
        CREATE FUNCTION maintain_collaborative_artifact_contributor_count()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                UPDATE collaborative_artifact_builds
                SET current_contributor_count = current_contributor_count + 1,
                    updated_at = transaction_timestamp()
                WHERE build_id = NEW.build_id;
                RETURN NEW;
            END IF;

            UPDATE collaborative_artifact_builds
            SET current_contributor_count = GREATEST(current_contributor_count - 1, 0),
                status = CASE WHEN status = 'active' THEN 'invalidated' ELSE status END,
                invalidation_epoch = CASE
                    WHEN status = 'active' THEN invalidation_epoch + 1
                    ELSE invalidation_epoch
                END,
                invalidated_at = CASE
                    WHEN status = 'active' THEN transaction_timestamp()
                    ELSE invalidated_at
                END,
                updated_at = transaction_timestamp()
            WHERE build_id = OLD.build_id;
            RETURN OLD;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_collaborative_artifact_contributor_count
        AFTER INSERT OR DELETE ON collaborative_artifact_contributors
        FOR EACH ROW
        EXECUTE FUNCTION maintain_collaborative_artifact_contributor_count()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_collaborative_artifact_contributor_count "
        "ON collaborative_artifact_contributors"
    )
    op.execute("DROP FUNCTION IF EXISTS maintain_collaborative_artifact_contributor_count()")
    op.drop_index(
        "ix_collaborative_artifact_contributors_user_id_build_id",
        table_name="collaborative_artifact_contributors",
    )
    op.drop_table("collaborative_artifact_contributors")
    op.drop_index(
        "ix_collaborative_artifact_builds_status_valid_until_build_id",
        table_name="collaborative_artifact_builds",
    )
    op.drop_table("collaborative_artifact_builds")
