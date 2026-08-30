"""Invalidate collaborative builds when contributor authority is lost.

Revision ID: 0008_stage_5_authority_loss
Revises: 0007_stage_5_artifact_registry
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_stage_5_authority_loss"
down_revision: str | None = "0007_stage_5_artifact_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION invalidate_collaborative_artifacts_for_user(target_user_id integer)
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
              );
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION enforce_collaborative_artifact_contributor_authority()
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
    op.execute(
        """
        CREATE TRIGGER trg_collaborative_artifact_contributor_authority
        BEFORE INSERT OR UPDATE ON collaborative_artifact_contributors
        FOR EACH ROW
        EXECUTE FUNCTION enforce_collaborative_artifact_contributor_authority()
        """
    )

    op.execute(
        """
        CREATE FUNCTION invalidate_collaborative_artifacts_on_consent_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                PERFORM invalidate_collaborative_artifacts_for_user(OLD.user_id);
                RETURN OLD;
            END IF;
            IF OLD.consent_version IS DISTINCT FROM NEW.consent_version
               OR OLD.granted_at IS DISTINCT FROM NEW.granted_at
               OR OLD.withdrawn_at IS DISTINCT FROM NEW.withdrawn_at THEN
                PERFORM invalidate_collaborative_artifacts_for_user(NEW.user_id);
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_collaborative_consent_artifact_invalidation
        AFTER DELETE OR UPDATE OF consent_version, granted_at, withdrawn_at
        ON collaborative_contribution_consents
        FOR EACH ROW
        EXECUTE FUNCTION invalidate_collaborative_artifacts_on_consent_change()
        """
    )

    op.execute(
        """
        CREATE FUNCTION invalidate_collaborative_artifacts_on_user_authority_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                PERFORM invalidate_collaborative_artifacts_for_user(OLD.id);
                RETURN OLD;
            END IF;
            IF OLD.consent_version IS DISTINCT FROM NEW.consent_version
               OR OLD.consented_at IS DISTINCT FROM NEW.consented_at
               OR OLD.expires_at IS DISTINCT FROM NEW.expires_at
               OR OLD.revoked_at IS DISTINCT FROM NEW.revoked_at THEN
                PERFORM invalidate_collaborative_artifacts_for_user(NEW.id);
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_user_collaborative_authority_invalidation
        AFTER DELETE OR UPDATE OF consent_version, consented_at, expires_at, revoked_at
        ON users
        FOR EACH ROW
        EXECUTE FUNCTION invalidate_collaborative_artifacts_on_user_authority_change()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_user_collaborative_authority_invalidation ON users")
    op.execute(
        "DROP FUNCTION IF EXISTS invalidate_collaborative_artifacts_on_user_authority_change()"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_collaborative_consent_artifact_invalidation "
        "ON collaborative_contribution_consents"
    )
    op.execute("DROP FUNCTION IF EXISTS invalidate_collaborative_artifacts_on_consent_change()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_collaborative_artifact_contributor_authority "
        "ON collaborative_artifact_contributors"
    )
    op.execute("DROP FUNCTION IF EXISTS enforce_collaborative_artifact_contributor_authority()")
    op.execute("DROP FUNCTION IF EXISTS invalidate_collaborative_artifacts_for_user(integer)")
