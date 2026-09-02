import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from app.db.models import (
    CollaborativeArtifactBuild,
    CollaborativeArtifactContributor,
    CollaborativeContributionConsent,
)
from app.db.session import create_session_factory
from app.repositories.collaborative_registry import (
    CollaborativeArtifactRegistryRepository,
    CollaborativeRegistryMutationError,
)
from app.services.collaborative_lifecycle import CollaborativeLifecycleService
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.conftest import make_consented_user

pytestmark = pytest.mark.integration

BUILD_ID = "stage5-live-operator-lifecycle-v1"
CONTRIBUTION_VERSION = "stage-5-contribution-v1"


def _register_active_build(session: Session) -> None:
    now = datetime.now(UTC)
    user = make_consented_user(
        "operator-lifecycle-contributor",
        consented_at=now - timedelta(days=30),
        expires_at=now + timedelta(days=60),
    )
    session.add(user)
    session.flush()
    session.add_all(
        [
            CollaborativeContributionConsent(
                user_id=user.id,
                consent_version=CONTRIBUTION_VERSION,
                granted_at=now - timedelta(days=20),
            ),
            CollaborativeArtifactBuild(
                build_id=BUILD_ID,
                source_kind="live",
                status="active",
                registered_revision=7,
                invalidation_epoch=0,
                expected_contributor_count=1,
                current_contributor_count=0,
                consent_version=CONTRIBUTION_VERSION,
                catalog_fingerprint="a" * 64,
                interaction_fingerprint="b" * 64,
                cutoff=now - timedelta(hours=1),
                valid_until=now + timedelta(days=30),
            ),
        ]
    )
    session.flush()
    session.add(CollaborativeArtifactContributor(build_id=BUILD_ID, user_id=user.id))
    session.commit()


def test_operator_lifecycle_is_explicit_ordered_idempotent_and_terminal(
    postgres_engine: Engine,
    postgres_session: Session,
) -> None:
    _register_active_build(postgres_session)
    service = CollaborativeLifecycleService(create_session_factory(postgres_engine))

    invalidated = service.mutate(operation="invalidate", build_id=BUILD_ID)
    invalidated_again = service.mutate(operation="invalidate", build_id=BUILD_ID)
    retired = service.mutate(operation="retire", build_id=BUILD_ID)
    retired_again = service.mutate(operation="retire", build_id=BUILD_ID)

    assert invalidated["build"]["changed"] is True  # type: ignore[index]
    assert invalidated["build"]["previous_status"] == "active"  # type: ignore[index]
    assert invalidated["build"]["status"] == "invalidated"  # type: ignore[index]
    assert invalidated_again["build"]["changed"] is False  # type: ignore[index]
    assert (
        invalidated_again["build"]["effective_at"]
        == invalidated["build"][  # type: ignore[index]
            "effective_at"
        ]
    )
    assert retired["build"]["changed"] is True  # type: ignore[index]
    assert retired["build"]["previous_status"] == "invalidated"  # type: ignore[index]
    assert retired["build"]["status"] == "retired"  # type: ignore[index]
    assert retired_again["build"]["changed"] is False  # type: ignore[index]
    assert (
        retired_again["build"]["effective_at"]
        == retired["build"][  # type: ignore[index]
            "effective_at"
        ]
    )
    assert "user_id" not in json.dumps([invalidated, retired], sort_keys=True)

    postgres_session.expire_all()
    build = postgres_session.get(CollaborativeArtifactBuild, BUILD_ID)
    assert build is not None
    assert build.status == "retired"
    assert build.invalidation_epoch == 1
    assert build.invalidated_at is not None
    assert build.retired_at is not None
    assert build.retired_at >= build.invalidated_at
    assert (
        postgres_session.scalar(
            select(func.count())
            .select_from(CollaborativeArtifactContributor)
            .where(CollaborativeArtifactContributor.build_id == BUILD_ID)
        )
        == 1
    )

    with pytest.raises(CollaborativeRegistryMutationError) as terminal:
        service.mutate(operation="invalidate", build_id=BUILD_ID)

    assert terminal.value.code == "retired_build_terminal"


def test_operator_retirement_rejects_active_and_missing_builds_without_mutation(
    postgres_engine: Engine,
    postgres_session: Session,
) -> None:
    _register_active_build(postgres_session)
    service = CollaborativeLifecycleService(create_session_factory(postgres_engine))

    with pytest.raises(CollaborativeRegistryMutationError) as active:
        service.mutate(operation="retire", build_id=BUILD_ID)
    with pytest.raises(CollaborativeRegistryMutationError) as missing:
        service.mutate(operation="invalidate", build_id="stage5-live-missing-v1")

    assert active.value.code == "active_build_retirement_forbidden"
    assert missing.value.code == "build_not_registered"
    postgres_session.expire_all()
    build = postgres_session.get(CollaborativeArtifactBuild, BUILD_ID)
    assert build is not None
    assert build.status == "active"
    assert build.invalidation_epoch == 0
    assert build.invalidated_at is None
    assert build.retired_at is None


def test_concurrent_operator_invalidations_advance_the_epoch_exactly_once(
    postgres_engine: Engine,
    postgres_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register_active_build(postgres_session)
    postgres_session.rollback()
    barrier = threading.Barrier(2)
    original_locked_build = CollaborativeArtifactRegistryRepository._locked_build

    def synchronized_lock(
        repository: CollaborativeArtifactRegistryRepository,
        build_id: str,
    ) -> CollaborativeArtifactBuild:
        barrier.wait(timeout=5)
        return original_locked_build(repository, build_id)

    monkeypatch.setattr(
        CollaborativeArtifactRegistryRepository,
        "_locked_build",
        synchronized_lock,
    )

    def invalidate() -> dict[str, object]:
        return CollaborativeLifecycleService(create_session_factory(postgres_engine)).mutate(
            operation="invalidate",
            build_id=BUILD_ID,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: invalidate(), range(2)))

    assert sorted(result["build"]["changed"] for result in results) == [False, True]  # type: ignore[index]
    postgres_session.expire_all()
    build = postgres_session.get(CollaborativeArtifactBuild, BUILD_ID)
    assert build is not None
    assert build.status == "invalidated"
    assert build.invalidation_epoch == 1
    assert build.invalidated_at is not None
