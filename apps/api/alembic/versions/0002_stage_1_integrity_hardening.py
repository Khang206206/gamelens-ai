"""Harden Stage 1 database integrity constraints.

Revision ID: 0002_stage_1_integrity_hardening
Revises: 0001_initial_schema
Create Date: 2026-07-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_stage_1_integrity_hardening"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table_name in ("games", "genres", "tags", "platforms"):
        op.create_check_constraint(
            op.f(f"ck_{table_name}_slug_format"),
            table_name,
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'",
        )

    op.create_check_constraint(
        op.f("ck_interactions_interaction_value_matches_type"),
        "interactions",
        "(interaction_type = 'rated' AND value IS NOT NULL "
        "AND value >= 0 AND value <= 10) "
        "OR (interaction_type <> 'rated' AND value IS NULL)",
    )
    op.create_check_constraint(
        op.f("ck_recommendation_events_request_context_object"),
        "recommendation_events",
        "jsonb_typeof(request_context) = 'object'",
    )
    op.create_check_constraint(
        op.f("ck_recommendation_events_result_summary_array"),
        "recommendation_events",
        "result_summary IS NULL OR jsonb_typeof(result_summary) = 'array'",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_recommendation_events_result_summary_array"),
        "recommendation_events",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_recommendation_events_request_context_object"),
        "recommendation_events",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_interactions_interaction_value_matches_type"),
        "interactions",
        type_="check",
    )
    for table_name in ("platforms", "tags", "genres", "games"):
        op.drop_constraint(
            op.f(f"ck_{table_name}_slug_format"),
            table_name,
            type_="check",
        )
