"""Persist versioned Stage 5 recommendation-generation events.

Revision ID: 0010_stage_5_event_contract
Revises: 0009_stage_5_label_changes
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_stage_5_event_contract"
down_revision: str | None = "0009_stage_5_label_changes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_CONSTRAINT_NAME = "ck_recommendation_events_stage_4_identity_complete"
_NEW_CONSTRAINT_NAME = "ck_recommendation_events_event_identity_complete"
_STAGE_4_IDENTITY_CONSTRAINT = (
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
    "AND result_summary IS NOT NULL)"
)
_STAGE_5_IDENTITY_CONSTRAINT = (
    "(event_schema_version = 'legacy-v1' "
    "AND data_fingerprint IS NULL "
    "AND ranking_policy_name IS NULL "
    "AND ranking_policy_version IS NULL "
    "AND ranking_mode IS NULL "
    "AND fallback_reason IS NULL "
    "AND hybrid_policy_name IS NULL "
    "AND hybrid_policy_version IS NULL "
    "AND collaborative_model_name IS NULL "
    "AND collaborative_model_version IS NULL "
    "AND collaborative_interaction_fingerprint IS NULL "
    "AND collaborative_policy_name IS NULL "
    "AND collaborative_policy_version IS NULL) OR "
    "(event_schema_version = 'stage-4-v1' "
    "AND data_fingerprint ~ '^[0-9a-f]{64}$' "
    "AND ranking_policy_name IS NOT NULL "
    "AND length(btrim(ranking_policy_name)) > 0 "
    "AND ranking_policy_version IS NOT NULL "
    "AND length(btrim(ranking_policy_version)) > 0 "
    "AND result_summary IS NOT NULL "
    "AND ranking_mode IS NULL "
    "AND fallback_reason IS NULL "
    "AND hybrid_policy_name IS NULL "
    "AND hybrid_policy_version IS NULL "
    "AND collaborative_model_name IS NULL "
    "AND collaborative_model_version IS NULL "
    "AND collaborative_interaction_fingerprint IS NULL "
    "AND collaborative_policy_name IS NULL "
    "AND collaborative_policy_version IS NULL) OR "
    "(event_schema_version = 'stage-5-v1' "
    "AND length(btrim(model_name)) > 0 "
    "AND length(btrim(model_version)) > 0 "
    "AND data_fingerprint IS NOT NULL "
    "AND data_fingerprint ~ '^[0-9a-f]{64}$' "
    "AND ranking_policy_name IS NOT NULL "
    "AND length(btrim(ranking_policy_name)) > 0 "
    "AND ranking_policy_version IS NOT NULL "
    "AND length(btrim(ranking_policy_version)) > 0 "
    "AND result_summary IS NOT NULL "
    "AND jsonb_array_length(result_summary) <= 20 "
    "AND ranking_mode IS NOT NULL "
    "AND request_context ? 'ranking_mode' "
    "AND request_context ->> 'ranking_mode' IS NOT NULL "
    "AND request_context ->> 'ranking_mode' = ranking_mode "
    "AND request_context ? 'fallback_reason' "
    "AND ((ranking_mode = 'hybrid' "
    "AND fallback_reason IS NULL "
    "AND request_context ->> 'fallback_reason' IS NULL "
    "AND hybrid_policy_name IS NOT NULL "
    "AND length(btrim(hybrid_policy_name)) > 0 "
    "AND hybrid_policy_version IS NOT NULL "
    "AND length(btrim(hybrid_policy_version)) > 0 "
    "AND collaborative_model_name IS NOT NULL "
    "AND length(btrim(collaborative_model_name)) > 0 "
    "AND collaborative_model_version IS NOT NULL "
    "AND length(btrim(collaborative_model_version)) > 0 "
    "AND collaborative_interaction_fingerprint IS NOT NULL "
    "AND collaborative_interaction_fingerprint ~ '^[0-9a-f]{64}$' "
    "AND collaborative_policy_name IS NOT NULL "
    "AND length(btrim(collaborative_policy_name)) > 0 "
    "AND collaborative_policy_version IS NOT NULL "
    "AND length(btrim(collaborative_policy_version)) > 0) OR "
    "(ranking_mode = 'stage_4_fallback' "
    "AND fallback_reason IS NOT NULL "
    "AND fallback_reason IN ('not_configured', 'fixture_not_allowed', "
    "'insufficient_data', 'artifact_missing', 'artifact_corrupt', "
    "'artifact_incompatible', 'artifact_stale', 'privacy_invalid', "
    "'artifact_expired', 'catalog_stale', 'artifact_retired', "
    "'no_query_sources', 'no_supported_sources', 'no_candidate_edges', "
    "'no_eligible_candidates') "
    "AND request_context ->> 'fallback_reason' IS NOT NULL "
    "AND request_context ->> 'fallback_reason' = fallback_reason "
    "AND hybrid_policy_name IS NULL "
    "AND hybrid_policy_version IS NULL "
    "AND collaborative_model_name IS NULL "
    "AND collaborative_model_version IS NULL "
    "AND collaborative_interaction_fingerprint IS NULL "
    "AND collaborative_policy_name IS NULL "
    "AND collaborative_policy_version IS NULL)))"
)

_STAGE_5_COLUMN_SPECS = (
    ("ranking_mode", 30),
    ("fallback_reason", 50),
    ("hybrid_policy_name", 100),
    ("hybrid_policy_version", 100),
    ("collaborative_model_name", 100),
    ("collaborative_model_version", 100),
    ("collaborative_interaction_fingerprint", 64),
    ("collaborative_policy_name", 100),
    ("collaborative_policy_version", 100),
)


def upgrade() -> None:
    for name, length in _STAGE_5_COLUMN_SPECS:
        op.add_column(
            "recommendation_events",
            sa.Column(name, sa.String(length), nullable=True),
        )
    op.drop_constraint(
        op.f(_OLD_CONSTRAINT_NAME),
        "recommendation_events",
        type_="check",
    )
    op.create_check_constraint(
        op.f(_NEW_CONSTRAINT_NAME),
        "recommendation_events",
        _STAGE_5_IDENTITY_CONSTRAINT,
    )
    op.create_index(
        "ix_recommendation_events_mode_generated_at",
        "recommendation_events",
        ["ranking_mode", "generated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recommendation_events_mode_generated_at",
        table_name="recommendation_events",
    )
    op.drop_constraint(
        op.f(_NEW_CONSTRAINT_NAME),
        "recommendation_events",
        type_="check",
    )
    op.create_check_constraint(
        op.f(_OLD_CONSTRAINT_NAME),
        "recommendation_events",
        _STAGE_4_IDENTITY_CONSTRAINT,
    )
    for name, _length in reversed(_STAGE_5_COLUMN_SPECS):
        op.drop_column("recommendation_events", name)
