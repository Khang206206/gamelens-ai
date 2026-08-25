"""Add Stage 5 contribution consent and monotonic source revision.

Revision ID: 0006_stage_5_collab_contract
Revises: 0005_stage_4_event_contract
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_stage_5_collab_contract"
down_revision: str | None = "0005_stage_4_event_contract"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVISION_SOURCE_TABLES = (
    "users",
    "user_preferences",
    "interactions",
    "collaborative_contribution_consents",
    "games",
    "genres",
    "tags",
    "platforms",
    "game_genres",
    "game_tags",
    "game_platforms",
)


def upgrade() -> None:
    op.create_table(
        "collaborative_contribution_consents",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("consent_version", sa.String(100), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
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
            "length(btrim(consent_version)) > 0",
            name=op.f("ck_collaborative_contribution_consents_consent_version_non_blank"),
        ),
        sa.CheckConstraint(
            "withdrawn_at IS NULL OR withdrawn_at >= granted_at",
            name=op.f("ck_collaborative_contribution_consents_withdrawal_not_before_grant"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_collaborative_contribution_consents_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id",
            name=op.f("pk_collaborative_contribution_consents"),
        ),
    )
    op.create_table(
        "collaborative_data_revision",
        sa.Column("singleton_id", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("revision", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "singleton_id = 1",
            name=op.f("ck_collaborative_data_revision_singleton_id_is_one"),
        ),
        sa.CheckConstraint(
            "revision >= 0",
            name=op.f("ck_collaborative_data_revision_revision_non_negative"),
        ),
        sa.PrimaryKeyConstraint(
            "singleton_id",
            name=op.f("pk_collaborative_data_revision"),
        ),
    )
    op.execute("INSERT INTO collaborative_data_revision (singleton_id, revision) VALUES (1, 0)")
    op.execute(
        """
        CREATE FUNCTION bump_collaborative_data_revision()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            INSERT INTO collaborative_data_revision (singleton_id, revision, updated_at)
            VALUES (1, 1, transaction_timestamp())
            ON CONFLICT (singleton_id) DO UPDATE
            SET revision = collaborative_data_revision.revision + 1,
                updated_at = transaction_timestamp();
            RETURN NULL;
        END;
        $$
        """
    )
    for table_name in REVISION_SOURCE_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_collaborative_revision
            AFTER INSERT OR UPDATE OR DELETE ON {table_name}
            FOR EACH STATEMENT
            EXECUTE FUNCTION bump_collaborative_data_revision()
            """
        )


def downgrade() -> None:
    for table_name in reversed(REVISION_SOURCE_TABLES):
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_{table_name}_collaborative_revision ON {table_name}"
        )
    op.execute("DROP FUNCTION IF EXISTS bump_collaborative_data_revision()")
    op.drop_table("collaborative_data_revision")
    op.drop_table("collaborative_contribution_consents")
