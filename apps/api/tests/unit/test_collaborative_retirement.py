import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.repositories.collaborative_registry import CollaborativeRegistryLifecycleState
from app.services import collaborative_retirement
from app.services.collaborative_retirement import (
    CollaborativeRetirementPreviewError,
    CollaborativeRetirementPreviewService,
)
from sqlalchemy.orm import Session


def _loaded_bundle(path: Path, *, build_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        root=path.resolve(),
        build_id=build_id,
        manifest={
            "build": {"id": build_id, "built_at": "2026-09-02T00:00:00.000000Z"},
            "source": {"kind": "live"},
            "catalog_fingerprint": "a" * 64,
            "interaction_fingerprint": "b" * 64,
            "lifecycle": {
                "cutoff": "2026-09-01T00:00:00.000000Z",
                "consent_version": "stage-5-contribution-v1",
                "data_revision": 7,
                "valid_until": "2026-10-02T00:00:00.000000Z",
            },
            "members": {"manifest-member": {"size": 10, "sha256": "c" * 64}},
        },
    )


def _service(
    monkeypatch: pytest.MonkeyPatch,
    states: dict[str, CollaborativeRegistryLifecycleState],
) -> tuple[CollaborativeRetirementPreviewService, Mock, Mock]:
    session = Mock(spec=Session)
    repository = Mock()
    repository.lifecycle_states.return_value = states
    monkeypatch.setattr(collaborative_retirement, "begin_repeatable_read", Mock())
    monkeypatch.setattr(
        collaborative_retirement,
        "CollaborativeArtifactRegistryRepository",
        lambda received: repository if received is session else pytest.fail("unexpected session"),
    )
    return CollaborativeRetirementPreviewService(lambda: session), session, repository


def test_retirement_preview_is_deterministic_read_only_and_aggregate_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_set = tmp_path / "artifact-set"
    active_path = artifact_set / "active"
    invalidated_path = artifact_set / "invalidated"
    content_path = artifact_set / "content"
    active_path.mkdir(parents=True)
    invalidated_path.mkdir()
    content_path.write_bytes(b"protected-content")
    build_ids = {
        "active": "stage5-live-active-v1",
        "invalidated": "stage5-live-invalidated-v1",
    }
    monkeypatch.setattr(
        collaborative_retirement,
        "load_collaborative_artifact",
        lambda path, **_keywords: _loaded_bundle(Path(path), build_id=build_ids[Path(path).name]),
    )
    states = {
        build_ids["active"]: CollaborativeRegistryLifecycleState(
            build_id=build_ids["active"],
            status="active",
            invalidation_epoch=0,
        ),
        build_ids["invalidated"]: CollaborativeRegistryLifecycleState(
            build_id=build_ids["invalidated"],
            status="invalidated",
            invalidation_epoch=1,
        ),
    }
    service, session, repository = _service(monkeypatch, states)
    before = sorted(path.name for path in artifact_set.iterdir())

    first = service.preview(
        artifact_set,
        database_fingerprint="1" * 12,
        configured_content_artifact=content_path,
        configured_collaborative_artifact=None,
    )
    second = service.preview(
        artifact_set,
        database_fingerprint="1" * 12,
        configured_content_artifact=content_path,
        configured_collaborative_artifact=None,
    )

    assert first == second
    assert first["summary"] == {"candidate_count": 1, "protected_count": 2}
    assert first["candidates"] == [
        {
            "path": str(invalidated_path.resolve()),
            "build_id": build_ids["invalidated"],
            "registry_status": "invalidated",
            "reason": "registry_invalidated",
            "bundle_fingerprint": first["candidates"][0]["bundle_fingerprint"],  # type: ignore[index]
        }
    ]
    assert {item["reason"] for item in first["protected"]} == {  # type: ignore[union-attr]
        "configured_content_artifact",
        "registry_active",
    }
    assert first["cleanup_confirmation"].startswith("CLEAN COLLABORATIVE 111111111111 ")  # type: ignore[union-attr]
    assert "user_id" not in json.dumps(first, sort_keys=True)
    assert sorted(path.name for path in artifact_set.iterdir()) == before
    assert repository.lifecycle_states.call_count == 2
    assert session.commit.call_count == 0
    assert session.rollback.call_count == 2
    assert session.close.call_count == 2


def test_retirement_preview_rejects_unregistered_bundle_without_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_set = tmp_path / "artifact-set"
    bundle_path = artifact_set / "orphan"
    bundle_path.mkdir(parents=True)
    monkeypatch.setattr(
        collaborative_retirement,
        "load_collaborative_artifact",
        lambda path, **_keywords: _loaded_bundle(
            Path(path),
            build_id="stage5-live-orphan-v1",
        ),
    )
    service, session, _repository = _service(monkeypatch, {})

    with pytest.raises(CollaborativeRetirementPreviewError) as caught:
        service.preview(
            artifact_set,
            database_fingerprint="2" * 12,
            configured_content_artifact=None,
            configured_collaborative_artifact=None,
        )

    assert caught.value.code == "retirement_bundle_unregistered"
    assert bundle_path.is_dir()
    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()


def test_retirement_preview_rejects_configured_artifact_as_the_artifact_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_artifact = tmp_path / "configured-collaborative"
    artifact_set = configured_artifact / "nested-artifact-set"
    artifact_set.mkdir(parents=True)
    service, session, _repository = _service(monkeypatch, {})

    with pytest.raises(CollaborativeRetirementPreviewError) as caught:
        service.preview(
            artifact_set,
            database_fingerprint="3" * 12,
            configured_content_artifact=None,
            configured_collaborative_artifact=configured_artifact,
        )

    assert caught.value.code == "artifact_set_path_protected"
    assert artifact_set.is_dir()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
    session.close.assert_not_called()
