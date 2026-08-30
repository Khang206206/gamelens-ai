"""Invalidate collaborative builds when an included positive label is removed.

Revision ID: 0009_stage_5_label_changes
Revises: 0008_stage_5_authority_loss
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_stage_5_label_changes"
down_revision: str | None = "0008_stage_5_authority_loss"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_contributor_authority_guard(*, require_cutoff: bool) -> None:
    cutoff_guard = "AND build.cutoff IS NOT NULL" if require_cutoff else ""
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION enforce_collaborative_artifact_contributor_authority()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION USING
                    ERRCODE = '55000',
                    MESSAGE = 'Collaborative artifact contributor lineage is immutable';
            END IF;

            PERFORM 1
            FROM collaborative_artifact_builds AS build
            JOIN users AS contributor_user
              ON contributor_user.id = NEW.user_id
            JOIN collaborative_contribution_consents AS consent
              ON consent.user_id = NEW.user_id
            WHERE build.build_id = NEW.build_id
              AND build.status = 'active'
              {cutoff_guard}
              AND build.valid_until > transaction_timestamp()
              AND contributor_user.consent_version IS NOT NULL
              AND contributor_user.consented_at IS NOT NULL
              AND contributor_user.consented_at <= transaction_timestamp()
              AND contributor_user.expires_at IS NOT NULL
              AND contributor_user.expires_at >= build.valid_until
              AND (
                  contributor_user.revoked_at IS NULL
                  OR contributor_user.revoked_at >= build.valid_until
              )
              AND consent.consent_version = build.consent_version
              AND consent.granted_at <= transaction_timestamp()
              AND (
                  consent.withdrawn_at IS NULL
                  OR consent.withdrawn_at >= build.valid_until
              )
            FOR UPDATE OF contributor_user, consent;
            IF NOT FOUND THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23514',
                    CONSTRAINT = 'ck_collaborative_artifact_contributor_authority',
                    MESSAGE = 'Collaborative artifact contributor authority is invalid';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )


def upgrade() -> None:
    op.add_column(
        "collaborative_artifact_builds",
        sa.Column("cutoff", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_collaborative_artifact_builds_cutoff_valid"),
        "collaborative_artifact_builds",
        "cutoff IS NULL OR (cutoff <= created_at AND cutoff < valid_until)",
    )
    _replace_contributor_authority_guard(require_cutoff=True)

    op.execute(
        """
        CREATE FUNCTION collaborative_current_edge_is_positive(
            target_user_id integer,
            target_game_id integer
        )
        RETURNS boolean
        LANGUAGE sql
        STABLE
        AS $$
            SELECT
                NOT EXISTS (
                    SELECT 1
                    FROM interactions AS current_dislike
                    WHERE current_dislike.user_id = target_user_id
                      AND current_dislike.game_id = target_game_id
                      AND current_dislike.interaction_type = 'disliked'
                      AND current_dislike.occurred_at <= transaction_timestamp()
                      AND current_dislike.superseded_at IS NULL
                )
                AND (
                    EXISTS (
                        SELECT 1
                        FROM interactions AS current_positive
                        WHERE current_positive.user_id = target_user_id
                          AND current_positive.game_id = target_game_id
                          AND current_positive.occurred_at <= transaction_timestamp()
                          AND current_positive.superseded_at IS NULL
                          AND (
                              current_positive.interaction_type = 'liked'
                              OR (
                                  current_positive.interaction_type = 'rated'
                                  AND current_positive.value >= 7
                              )
                          )
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM user_preferences AS current_preference
                        JOIN games AS current_game
                          ON current_game.slug = current_preference.value
                        WHERE current_preference.user_id = target_user_id
                          AND current_game.id = target_game_id
                          AND current_preference.preference_type = 'game'
                          AND current_preference.weight > 0
                    )
                )
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION invalidate_collaborative_artifacts_for_preference_loss(
            target_user_id integer,
            target_game_id integer,
            old_preference_created_at timestamp with time zone,
            old_preference_updated_at timestamp with time zone
        )
        RETURNS void
        LANGUAGE plpgsql
        AS $$
        BEGIN
            UPDATE collaborative_artifact_builds AS build
            SET status = 'invalidated',
                invalidation_epoch = build.invalidation_epoch + 1,
                invalidated_at = transaction_timestamp(),
                updated_at = transaction_timestamp()
            WHERE build.status = 'active'
              AND EXISTS (
                  SELECT 1
                  FROM collaborative_artifact_contributors AS contributor
                  WHERE contributor.build_id = build.build_id
                    AND contributor.user_id = target_user_id
              )
              AND (
                  build.cutoff IS NULL
                  OR (
                      old_preference_created_at <= build.cutoff
                      AND old_preference_updated_at <= build.cutoff
                      AND NOT EXISTS (
                          SELECT 1
                          FROM interactions AS historical_dislike
                          WHERE historical_dislike.user_id = target_user_id
                            AND historical_dislike.game_id = target_game_id
                            AND historical_dislike.interaction_type = 'disliked'
                            AND historical_dislike.occurred_at <= build.cutoff
                            AND (
                                historical_dislike.superseded_at IS NULL
                                OR historical_dislike.superseded_at > build.cutoff
                            )
                      )
                  )
              )
              AND NOT collaborative_current_edge_is_positive(
                  target_user_id,
                  target_game_id
              );
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION invalidate_collaborative_artifacts_for_interaction_change(
            target_user_id integer,
            target_game_id integer,
            excluded_interaction_id integer,
            old_interaction_type character varying,
            old_interaction_value numeric,
            old_interaction_occurred_at timestamp with time zone,
            old_interaction_superseded_at timestamp with time zone
        )
        RETURNS void
        LANGUAGE plpgsql
        AS $$
        BEGIN
            UPDATE collaborative_artifact_builds AS build
            SET status = 'invalidated',
                invalidation_epoch = build.invalidation_epoch + 1,
                invalidated_at = transaction_timestamp(),
                updated_at = transaction_timestamp()
            WHERE build.status = 'active'
              AND EXISTS (
                  SELECT 1
                  FROM collaborative_artifact_contributors AS contributor
                  WHERE contributor.build_id = build.build_id
                    AND contributor.user_id = target_user_id
              )
              AND (
                  build.cutoff IS NULL
                  OR (
                      NOT (
                          EXISTS (
                              SELECT 1
                              FROM interactions AS historical_dislike
                              WHERE historical_dislike.user_id = target_user_id
                                AND historical_dislike.game_id = target_game_id
                                AND historical_dislike.id IS DISTINCT FROM excluded_interaction_id
                                AND historical_dislike.interaction_type = 'disliked'
                                AND historical_dislike.occurred_at <= build.cutoff
                                AND (
                                    historical_dislike.superseded_at IS NULL
                                    OR historical_dislike.superseded_at > build.cutoff
                                )
                          )
                          OR COALESCE(
                              old_interaction_type = 'disliked'
                              AND old_interaction_occurred_at <= build.cutoff
                              AND (
                                  old_interaction_superseded_at IS NULL
                                  OR old_interaction_superseded_at > build.cutoff
                              ),
                              FALSE
                          )
                      )
                      AND (
                          EXISTS (
                              SELECT 1
                              FROM interactions AS historical_positive
                              WHERE historical_positive.user_id = target_user_id
                                AND historical_positive.game_id = target_game_id
                                AND historical_positive.id IS DISTINCT FROM excluded_interaction_id
                                AND historical_positive.occurred_at <= build.cutoff
                                AND (
                                    historical_positive.superseded_at IS NULL
                                    OR historical_positive.superseded_at > build.cutoff
                                )
                                AND (
                                    historical_positive.interaction_type = 'liked'
                                    OR (
                                        historical_positive.interaction_type = 'rated'
                                        AND historical_positive.value >= 7
                                    )
                                )
                          )
                          OR COALESCE(
                              old_interaction_occurred_at <= build.cutoff
                              AND (
                                  old_interaction_superseded_at IS NULL
                                  OR old_interaction_superseded_at > build.cutoff
                              )
                              AND (
                                  old_interaction_type = 'liked'
                                  OR (
                                      old_interaction_type = 'rated'
                                      AND old_interaction_value >= 7
                                  )
                              ),
                              FALSE
                          )
                          OR EXISTS (
                              SELECT 1
                              FROM user_preferences AS historical_preference
                              JOIN games AS historical_game
                                ON historical_game.slug = historical_preference.value
                              WHERE historical_preference.user_id = target_user_id
                                AND historical_game.id = target_game_id
                                AND historical_preference.preference_type = 'game'
                                AND historical_preference.weight > 0
                                AND historical_preference.created_at <= build.cutoff
                                AND historical_preference.updated_at <= build.cutoff
                          )
                      )
                  )
              )
              AND NOT collaborative_current_edge_is_positive(
                  target_user_id,
                  target_game_id
              );
        END;
        $$
        """
    )

    op.execute(
        """
        CREATE FUNCTION invalidate_collaborative_artifacts_on_preference_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            target_game_id integer;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                RETURN NEW;
            END IF;
            IF OLD.preference_type <> 'game' OR OLD.weight <= 0 THEN
                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                END IF;
                RETURN NEW;
            END IF;

            SELECT game.id
            INTO target_game_id
            FROM games AS game
            WHERE game.slug = OLD.value;
            IF target_game_id IS NOT NULL THEN
                PERFORM invalidate_collaborative_artifacts_for_preference_loss(
                    OLD.user_id,
                    target_game_id,
                    OLD.created_at,
                    OLD.updated_at
                );
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_user_preferences_collaborative_label_invalidation
        AFTER INSERT OR UPDATE OR DELETE ON user_preferences
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION invalidate_collaborative_artifacts_on_preference_change()
        """
    )

    op.execute(
        """
        CREATE FUNCTION invalidate_collaborative_artifacts_on_interaction_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            old_type character varying;
            old_value numeric;
            old_occurred_at timestamp with time zone;
            old_superseded_at timestamp with time zone;
        BEGIN
            IF TG_OP IN ('UPDATE', 'DELETE') THEN
                IF OLD.interaction_type = 'liked'
                   OR (OLD.interaction_type = 'rated' AND OLD.value >= 7) THEN
                    PERFORM invalidate_collaborative_artifacts_for_interaction_change(
                        OLD.user_id,
                        OLD.game_id,
                        CASE WHEN TG_OP = 'UPDATE' THEN NEW.id ELSE NULL END,
                        OLD.interaction_type,
                        OLD.value,
                        OLD.occurred_at,
                        OLD.superseded_at
                    );
                END IF;
            END IF;

            IF TG_OP IN ('INSERT', 'UPDATE') THEN
                IF NEW.interaction_type = 'disliked' THEN
                    old_type := NULL;
                    old_value := NULL;
                    old_occurred_at := NULL;
                    old_superseded_at := NULL;
                    IF TG_OP = 'UPDATE'
                       AND OLD.user_id = NEW.user_id
                       AND OLD.game_id = NEW.game_id THEN
                        old_type := OLD.interaction_type;
                        old_value := OLD.value;
                        old_occurred_at := OLD.occurred_at;
                        old_superseded_at := OLD.superseded_at;
                    END IF;
                    PERFORM invalidate_collaborative_artifacts_for_interaction_change(
                        NEW.user_id,
                        NEW.game_id,
                        NEW.id,
                        old_type,
                        old_value,
                        old_occurred_at,
                        old_superseded_at
                    );
                END IF;
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_interactions_collaborative_label_invalidation
        AFTER INSERT OR UPDATE OR DELETE ON interactions
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION invalidate_collaborative_artifacts_on_interaction_change()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_interactions_collaborative_label_invalidation ON interactions"
    )
    op.execute("DROP FUNCTION IF EXISTS invalidate_collaborative_artifacts_on_interaction_change()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_user_preferences_collaborative_label_invalidation "
        "ON user_preferences"
    )
    op.execute("DROP FUNCTION IF EXISTS invalidate_collaborative_artifacts_on_preference_change()")
    op.execute(
        "DROP FUNCTION IF EXISTS invalidate_collaborative_artifacts_for_interaction_change("
        "integer, integer, integer, character varying, numeric, "
        "timestamp with time zone, timestamp with time zone)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS invalidate_collaborative_artifacts_for_preference_loss("
        "integer, integer, timestamp with time zone, timestamp with time zone)"
    )
    op.execute("DROP FUNCTION IF EXISTS collaborative_current_edge_is_positive(integer, integer)")

    _replace_contributor_authority_guard(require_cutoff=False)
    op.drop_constraint(
        op.f("ck_collaborative_artifact_builds_cutoff_valid"),
        "collaborative_artifact_builds",
        type_="check",
    )
    op.drop_column("collaborative_artifact_builds", "cutoff")
