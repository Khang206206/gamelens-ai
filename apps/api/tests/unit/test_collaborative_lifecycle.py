from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from app.repositories.collaborative_registry import CollaborativeLifecycleTransition
from app.services import collaborative_lifecycle
from app.services.collaborative_lifecycle import (
    CollaborativeLifecycleError,
    CollaborativeLifecycleService,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session


def test_lifecycle_service_commits_one_transition_and_returns_aggregate_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=Session)
    transition = CollaborativeLifecycleTransition(
        operation="invalidate",
        build_id="stage5-live-v1",
        previous_status="active",
        status="invalidated",
        changed=True,
        invalidation_epoch=1,
        effective_at=datetime(2026, 9, 2, 12, 30, tzinfo=UTC),
    )
    repository = Mock()
    repository.invalidate_live_build.return_value = transition
    monkeypatch.setattr(collaborative_lifecycle, "begin_read_committed", Mock())
    monkeypatch.setattr(
        collaborative_lifecycle,
        "CollaborativeArtifactRegistryRepository",
        lambda received: repository if received is session else pytest.fail("unexpected session"),
    )

    result = CollaborativeLifecycleService(lambda: session).mutate(
        operation="invalidate",
        build_id="stage5-live-v1",
    )

    assert result == {
        "status": "ok",
        "operation": "invalidate",
        "build": {
            "id": "stage5-live-v1",
            "previous_status": "active",
            "status": "invalidated",
            "changed": True,
            "invalidation_epoch": 1,
            "effective_at": "2026-09-02T12:30:00.000000Z",
        },
    }
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()
    session.close.assert_called_once_with()


def test_lifecycle_service_rolls_back_and_hides_database_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=Session)
    repository = Mock()
    repository.retire_live_build.side_effect = OperationalError(
        "UPDATE collaborative_artifact_builds",
        {},
        RuntimeError("database detail"),
    )
    monkeypatch.setattr(collaborative_lifecycle, "begin_read_committed", Mock())
    monkeypatch.setattr(
        collaborative_lifecycle,
        "CollaborativeArtifactRegistryRepository",
        lambda _session: repository,
    )

    with pytest.raises(CollaborativeLifecycleError) as caught:
        CollaborativeLifecycleService(lambda: session).mutate(
            operation="retire",
            build_id="stage5-live-v1",
        )

    assert caught.value.code == "lifecycle_database_failed"
    assert "database detail" not in str(caught.value)
    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()
    session.close.assert_called_once_with()
