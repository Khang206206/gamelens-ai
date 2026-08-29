from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast

import pytest
from app.db.models import (
    CollaborativeArtifactBuild,
    CollaborativeArtifactContributor,
    User,
)
from app.repositories.collaborative_registry import CollaborativeArtifactRegistryRepository
from app.services.recommendation import (
    CollaborativeArtifactComponent,
    evaluate_collaborative_readiness,
)
from gamelens_recommender import LoadedCollaborativeArtifact
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.conftest import make_consented_user

pytestmark = pytest.mark.integration

CATALOG_FINGERPRINT = "a" * 64
INTERACTION_FINGERPRINT = "b" * 64
CONSENT_VERSION = "stage-5-contribution-v1"
BUILD_ID = "stage5-live-registry-v1"


def _build(
    *,
    now: datetime,
    expected_contributor_count: int = 12,
    **changes: object,
) -> CollaborativeArtifactBuild:
    values: dict[str, object] = {
        "build_id": BUILD_ID,
        "source_kind": "live",
        "status": "active",
        "registered_revision": 7,
        "invalidation_epoch": 0,
        "expected_contributor_count": expected_contributor_count,
        "current_contributor_count": 0,
        "consent_version": CONSENT_VERSION,
        "catalog_fingerprint": CATALOG_FINGERPRINT,
        "interaction_fingerprint": INTERACTION_FINGERPRINT,
        "valid_until": now + timedelta(days=30),
        "invalidated_at": None,
        "retired_at": None,
    }
    values.update(changes)
    return CollaborativeArtifactBuild(**values)  # type: ignore[arg-type]


def _artifact(*, valid_until: datetime) -> LoadedCollaborativeArtifact:
    manifest = {
        "source": {"kind": "live"},
        "build": {"id": BUILD_ID},
        "lifecycle": {
            "data_revision": 7,
            "consent_version": CONSENT_VERSION,
            "valid_until": valid_until.isoformat(timespec="microseconds").replace("+00:00", "Z"),
        },
        "catalog_fingerprint": CATALOG_FINGERPRINT,
        "interaction_fingerprint": INTERACTION_FINGERPRINT,
        "matrix": {
            "retained_contributors": 12,
            "retained_positive_edges": 36,
            "retained_items": 6,
        },
        "thresholds": {
            "activation_minimum_users": 10,
            "activation_minimum_edges": 20,
            "activation_minimum_items": 5,
        },
    }
    return cast(LoadedCollaborativeArtifact, SimpleNamespace(manifest=manifest))


def test_registry_count_is_constant_time_and_user_delete_invalidates_before_serving(
    postgres_session: Session,
) -> None:
    now = datetime.now(UTC)
    users = [make_consented_user(f"registry-contributor-{index}") for index in range(12)]
    postgres_session.add_all(users)
    postgres_session.flush()
    build = _build(now=now)
    postgres_session.add(build)
    postgres_session.flush()
    postgres_session.add_all(
        CollaborativeArtifactContributor(build_id=build.build_id, user_id=user.id) for user in users
    )
    postgres_session.flush()
    postgres_session.refresh(build)

    assert build.current_contributor_count == 12
    assert build.status == "active"
    repository = CollaborativeArtifactRegistryRepository(postgres_session)
    active_row = repository.readiness(BUILD_ID)
    assert active_row is not None
    component = CollaborativeArtifactComponent.loaded(
        _artifact(valid_until=build.valid_until),
        source_kind="live",
    )
    ready = evaluate_collaborative_readiness(
        component,
        catalog_fingerprint=CATALOG_FINGERPRINT,
        current_consent_version=CONSENT_VERSION,
        now=now,
        lineage=active_row,
    )
    assert ready.state == "ready"

    postgres_session.execute(delete(User).where(User.id == users[0].id))
    postgres_session.flush()
    postgres_session.refresh(build)
    invalidated_row = repository.readiness(BUILD_ID)

    assert build.current_contributor_count == 11
    assert build.status == "invalidated"
    assert build.invalidation_epoch == 1
    assert build.invalidated_at is not None
    assert invalidated_row is not None
    assert invalidated_row.contributor_count == 11
    assert invalidated_row.status == "invalidated"
    invalidated = evaluate_collaborative_readiness(
        component,
        catalog_fingerprint=CATALOG_FINGERPRINT,
        current_consent_version=CONSENT_VERSION,
        now=now,
        lineage=invalidated_row,
    )
    assert invalidated.state == "stale"
    assert invalidated.reason == "privacy_invalid"


def test_retired_registry_row_remains_observable_and_cannot_be_reactivated_by_path(
    postgres_session: Session,
) -> None:
    now = datetime.now(UTC)
    build = _build(now=now, status="retired", retired_at=now)
    postgres_session.add(build)
    postgres_session.flush()

    row = CollaborativeArtifactRegistryRepository(postgres_session).readiness(BUILD_ID)
    assert row is not None
    assert row.status == "retired"
    assert row.contributor_count == 0
    component = CollaborativeArtifactComponent.loaded(
        _artifact(valid_until=build.valid_until),
        source_kind="live",
    )

    readiness = evaluate_collaborative_readiness(
        component,
        catalog_fingerprint=CATALOG_FINGERPRINT,
        current_consent_version=CONSENT_VERSION,
        now=now,
        lineage=row,
    )

    assert readiness.state == "stale"
    assert readiness.reason == "artifact_retired"


@pytest.mark.parametrize(
    "changes",
    [
        {"build_id": "invalid build id"},
        {"source_kind": "fixture"},
        {"registered_revision": -1},
        {"expected_contributor_count": 0},
        {"expected_contributor_count": 1, "current_contributor_count": 2},
        {"catalog_fingerprint": "A" * 64},
        {"status": "active", "invalidation_epoch": 1},
        {"status": "invalidated", "invalidation_epoch": 1},
        {"valid_until": datetime(2020, 1, 1, tzinfo=UTC)},
    ],
)
def test_registry_constraints_reject_invalid_or_inconsistent_lineage(
    postgres_session: Session,
    changes: dict[str, object],
) -> None:
    postgres_session.add(_build(now=datetime.now(UTC), **changes))

    with pytest.raises(IntegrityError):
        postgres_session.flush()
