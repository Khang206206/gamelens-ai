from datetime import timedelta

import pytest
from app.db.models import CollaborativeArtifactBuild
from app.repositories.collaborative_registry import CollaborativeArtifactRegistryRepository
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.integration.test_stage_5_operator_lifecycle import BUILD_ID, _register_active_build

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("initial", "change"),
    [
        ("active", "skip_invalidation"),
        ("invalidated", "reactivate"),
        ("retired", "reactivate"),
        ("retired", "unretire"),
        ("invalidated", "rewind_epoch"),
        ("retired", "rewind_epoch"),
        ("invalidated", "rewrite_invalidation"),
        ("retired", "rewrite_retirement"),
    ],
)
def test_postgresql_blocks_lifecycle_reversal_even_with_consistent_row_fields(
    postgres_session: Session, initial: str, change: str
) -> None:
    _register_active_build(postgres_session)
    repository = CollaborativeArtifactRegistryRepository(postgres_session)
    if initial != "active":
        repository.invalidate_live_build(BUILD_ID)
        postgres_session.execute(update(CollaborativeArtifactBuild).values(invalidation_epoch=2))
    if initial == "retired":
        repository.retire_live_build(BUILD_ID)
    postgres_session.commit()
    row = postgres_session.get(CollaborativeArtifactBuild, BUILD_ID)
    assert row is not None
    before = (row.status, row.invalidation_epoch, row.invalidated_at, row.retired_at)
    now = postgres_session.scalar(select(func.clock_timestamp()))
    changes = {
        "skip_invalidation": {"status": "retired", "retired_at": now},
        "reactivate": {
            "status": "active",
            "invalidation_epoch": 0,
            "invalidated_at": None,
            "retired_at": None,
        },
        "unretire": {"status": "invalidated", "retired_at": None},
        "rewind_epoch": {"invalidation_epoch": 1},
        "rewrite_invalidation": {"invalidated_at": now + timedelta(seconds=1)},
        "rewrite_retirement": {"retired_at": now + timedelta(seconds=1)},
    }[change]
    with pytest.raises(IntegrityError) as caught, postgres_session.begin_nested():
        postgres_session.execute(
            update(CollaborativeArtifactBuild)
            .where(CollaborativeArtifactBuild.build_id == BUILD_ID)
            .values(**changes)
        )
    assert caught.value.orig.diag.constraint_name == "collaborative_lifecycle_monotonic"
    postgres_session.refresh(row)
    assert (row.status, row.invalidation_epoch, row.invalidated_at, row.retired_at) == before
    # Idempotent status writes and ordinary bookkeeping remain legal.
    postgres_session.execute(
        update(CollaborativeArtifactBuild)
        .where(CollaborativeArtifactBuild.build_id == BUILD_ID)
        .values(status=initial, current_contributor_count=1, updated_at=now)
    )
    postgres_session.commit()
