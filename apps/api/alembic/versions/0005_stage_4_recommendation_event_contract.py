"""Version and bound Stage 4 recommendation-generation events.

Revision ID: 0005_stage_4_event_contract
Revises: 0004_stage_4_interaction_state
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_stage_4_event_contract"
down_revision: str | None = "0004_stage_4_interaction_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "recommendation_events",
        sa.Column("generation_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "recommendation_events",
        sa.Column("event_schema_version", sa.String(50), nullable=True),
    )
    op.add_column(
        "recommendation_events",
        sa.Column("data_fingerprint", sa.String(64), nullable=True),
    )
    op.add_column(
        "recommendation_events",
        sa.Column("ranking_policy_name", sa.String(100), nullable=True),
    )
    op.add_column(
        "recommendation_events",
        sa.Column("ranking_policy_version", sa.String(100), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE recommendation_events
            SET generation_id = 'legacy-' || id::text,
                event_schema_version = 'legacy-v1'
            """
        )
    )
    op.alter_column("recommendation_events", "generation_id", nullable=False)
    op.alter_column("recommendation_events", "event_schema_version", nullable=False)
    op.create_unique_constraint(
        op.f("uq_recommendation_events_generation_id"),
        "recommendation_events",
        ["generation_id"],
    )
    op.create_check_constraint(
        op.f("ck_recommendation_events_stage_4_identity_complete"),
        "recommendation_events",
        "(event_schema_version = 'legacy-v1' "
        "AND data_fingerprint IS NULL "
        "AND ranking_policy_name IS NULL "
        "AND ranking_policy_version IS NULL) OR "
        "(event_schema_version = 'stage-4-v1' "
        "AND data_fingerprint ~ '^[0-9a-f]{64}$' "
        "AND ranking_policy_name IS NOT NULL "
        "AND length(btrim(ranking_policy_name)) > 0 "
        "AND ranking_policy_version IS NOT NULL "
        "AND length(btrim(ranking_policy_version)) > 0 "
        "AND result_summary IS NOT NULL)",
    )
    op.create_index(
        "ix_recommendation_events_generated_at_id",
        "recommendation_events",
        ["generated_at", "id"],
    )
    op.create_index(
        "ix_recommendation_events_policy_generated_at",
        "recommendation_events",
        ["ranking_policy_name", "ranking_policy_version", "generated_at"],
    )
    op.create_index(
        "ix_recommendation_events_model_generated_at",
        "recommendation_events",
        ["model_name", "model_version", "generated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recommendation_events_generated_at_id",
        table_name="recommendation_events",
    )
    op.drop_index(
        "ix_recommendation_events_model_generated_at",
        table_name="recommendation_events",
    )
    op.drop_index(
        "ix_recommendation_events_policy_generated_at",
        table_name="recommendation_events",
    )
    op.drop_constraint(
        op.f("ck_recommendation_events_stage_4_identity_complete"),
        "recommendation_events",
        type_="check",
    )
    op.drop_constraint(
        op.f("uq_recommendation_events_generation_id"),
        "recommendation_events",
        type_="unique",
    )
    op.drop_column("recommendation_events", "ranking_policy_version")
    op.drop_column("recommendation_events", "ranking_policy_name")
    op.drop_column("recommendation_events", "data_fingerprint")
    op.drop_column("recommendation_events", "event_schema_version")
    op.drop_column("recommendation_events", "generation_id")
