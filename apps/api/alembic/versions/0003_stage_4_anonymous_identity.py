"""Add the Stage 4 consent-aware anonymous identity contract.

Revision ID: 0003_stage_4_anonymous_identity
Revises: 0002_stage_1_integrity_hardening
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_stage_4_anonymous_identity"
down_revision: str | None = "0002_stage_1_integrity_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("anonymous_token_digest", sa.String(64), nullable=True))
    op.add_column("users", sa.Column("consent_version", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE users
            SET anonymous_token_digest =
                    md5('legacy-revoked-v1:' || anonymous_key) ||
                    lpad(to_hex(id), 32, '0'),
                revoked_at = now()
            """
        )
    )
    op.alter_column("users", "anonymous_token_digest", nullable=False)
    op.create_unique_constraint(
        op.f("uq_users_anonymous_token_digest"),
        "users",
        ["anonymous_token_digest"],
    )
    op.create_check_constraint(
        op.f("ck_users_anonymous_token_digest_format"),
        "users",
        "anonymous_token_digest ~ '^[0-9a-f]{64}$'",
    )
    op.create_check_constraint(
        op.f("ck_users_consent_lifecycle_valid"),
        "users",
        "(consent_version IS NULL AND consented_at IS NULL AND expires_at IS NULL "
        "AND revoked_at IS NOT NULL) OR "
        "(consent_version IS NOT NULL AND length(btrim(consent_version)) > 0 "
        "AND consented_at IS NOT NULL AND expires_at IS NOT NULL "
        "AND expires_at > consented_at)",
    )
    op.create_index("ix_users_expires_at_id", "users", ["expires_at", "id"])
    op.create_index("ix_users_revoked_at_id", "users", ["revoked_at", "id"])
    op.drop_constraint(op.f("uq_users_anonymous_key"), "users", type_="unique")
    op.drop_column("users", "anonymous_key")


def downgrade() -> None:
    op.add_column("users", sa.Column("anonymous_key", sa.String(100), nullable=True))
    op.execute(sa.text("UPDATE users SET anonymous_key = 'stage4-downgrade-' || id::text"))
    op.alter_column("users", "anonymous_key", nullable=False)
    op.create_unique_constraint(
        op.f("uq_users_anonymous_key"),
        "users",
        ["anonymous_key"],
    )
    op.drop_index("ix_users_revoked_at_id", table_name="users")
    op.drop_index("ix_users_expires_at_id", table_name="users")
    op.drop_constraint(
        op.f("ck_users_consent_lifecycle_valid"),
        "users",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_users_anonymous_token_digest_format"),
        "users",
        type_="check",
    )
    op.drop_constraint(
        op.f("uq_users_anonymous_token_digest"),
        "users",
        type_="unique",
    )
    op.drop_column("users", "revoked_at")
    op.drop_column("users", "expires_at")
    op.drop_column("users", "consented_at")
    op.drop_column("users", "consent_version")
    op.drop_column("users", "anonymous_token_digest")
