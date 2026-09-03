"""Enforce one-way collaborative lifecycle transitions without changing data.

Revision ID: 0011_stage_5_lifecycle_guard
Revises: 0010_stage_5_event_contract
"""

from alembic import op

revision: str = "0011_stage_5_lifecycle_guard"
down_revision: str | None = "0010_stage_5_event_contract"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION gamelens_guard_collaborative_lifecycle()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF (OLD.status = 'active' AND NEW.status = 'retired')
                OR (OLD.status = 'invalidated' AND NEW.status = 'active')
                OR (OLD.status = 'retired' AND NEW.status <> 'retired')
                OR NEW.invalidation_epoch < OLD.invalidation_epoch
                OR (OLD.invalidated_at IS NOT NULL
                    AND NEW.invalidated_at IS DISTINCT FROM OLD.invalidated_at)
                OR (OLD.retired_at IS NOT NULL
                    AND NEW.retired_at IS DISTINCT FROM OLD.retired_at)
            THEN
                RAISE EXCEPTION 'Collaborative lifecycle transition is not reversible'
                    USING ERRCODE = '23514',
                        CONSTRAINT = 'collaborative_lifecycle_monotonic';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER trg_collaborative_lifecycle_guard
        BEFORE UPDATE ON collaborative_artifact_builds
        FOR EACH ROW EXECUTE FUNCTION gamelens_guard_collaborative_lifecycle();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_collaborative_lifecycle_guard ON collaborative_artifact_builds")
    op.execute("DROP FUNCTION gamelens_guard_collaborative_lifecycle()")
