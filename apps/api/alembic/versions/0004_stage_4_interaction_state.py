"""Add temporal current-state semantics to interactions.

Revision ID: 0004_stage_4_interaction_state
Revises: 0003_stage_4_anonymous_identity
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_stage_4_interaction_state"
down_revision: str | None = "0003_stage_4_anonymous_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interactions",
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       occurred_at,
                       lag(occurred_at) OVER (
                           PARTITION BY user_id, game_id,
                           CASE
                               WHEN interaction_type IN ('liked', 'disliked')
                                   THEN 'reaction'
                               ELSE interaction_type
                           END
                           ORDER BY occurred_at DESC, id DESC
                       ) AS newer_at,
                       row_number() OVER (
                           PARTITION BY user_id, game_id,
                           CASE
                               WHEN interaction_type IN ('liked', 'disliked')
                                   THEN 'reaction'
                               ELSE interaction_type
                           END
                           ORDER BY occurred_at DESC, id DESC
                       ) AS position
                FROM interactions
                WHERE interaction_type IN (
                    'liked', 'disliked', 'played', 'wishlisted', 'rated'
                )
            )
            UPDATE interactions AS interaction
            SET superseded_at = GREATEST(ranked.occurred_at, ranked.newer_at)
            FROM ranked
            WHERE interaction.id = ranked.id
              AND ranked.position > 1
            """
        )
    )
    op.create_check_constraint(
        op.f("ck_interactions_superseded_not_before_occurrence"),
        "interactions",
        "superseded_at IS NULL OR superseded_at >= occurred_at",
    )
    op.create_index(
        "uq_interactions_active_reaction",
        "interactions",
        ["user_id", "game_id"],
        unique=True,
        postgresql_where=sa.text(
            "superseded_at IS NULL AND interaction_type IN ('liked', 'disliked')"
        ),
    )
    op.create_index(
        "uq_interactions_active_state_type",
        "interactions",
        ["user_id", "game_id", "interaction_type"],
        unique=True,
        postgresql_where=sa.text(
            "superseded_at IS NULL AND interaction_type IN ('played', 'wishlisted', 'rated')"
        ),
    )
    op.create_index(
        "ix_interactions_user_id_active_occurred_at",
        "interactions",
        ["user_id", "superseded_at", "occurred_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_interactions_user_id_active_occurred_at",
        table_name="interactions",
    )
    op.drop_index("uq_interactions_active_state_type", table_name="interactions")
    op.drop_index("uq_interactions_active_reaction", table_name="interactions")
    op.drop_constraint(
        op.f("ck_interactions_superseded_not_before_occurrence"),
        "interactions",
        type_="check",
    )
    op.drop_column("interactions", "superseded_at")
