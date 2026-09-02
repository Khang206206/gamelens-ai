import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from app.repositories.collaborative_registry import CollaborativeRegistryLifecycleState
from app.services.collaborative_recovery import (
    PROMOTION_LOCK_BYTES,
    CollaborativeArtifactRecoveryService,
)
from app.services.collaborative_retirement import (
    CollaborativeRetirementPreviewError,
    _recovery_bundle_files,
)

BUILD_ID = "stage5-recovery-v1"
DATABASE_FINGERPRINT = "a" * 12


def _service() -> CollaborativeArtifactRecoveryService:
    service = CollaborativeArtifactRecoveryService(Mock())
    service.registry_reader._registry_states = Mock(
        return_value={
            BUILD_ID: CollaborativeRegistryLifecycleState(BUILD_ID, "retired", 1),
        }
    )
    return service


def _arguments(root: Path, target: Path, *, kind: str = "build") -> dict:
    return {
        "artifact_set": root,
        "target": target,
        "kind": kind,
        "database_fingerprint": DATABASE_FINGERPRINT,
        "configured_content_artifact": None,
        "configured_collaborative_artifact": None,
    }


def _build_debris(root: Path, *, with_lock: bool = True) -> tuple[Path, Path, Path]:
    target = root / "candidate"
    temporary = root / ".candidate.tmp-abcdefgh"
    temporary.mkdir()
    (temporary / "item-slugs.json").write_bytes(b"[]")
    (temporary / "manifest.json").write_bytes(b"partial-manifest")
    lock = root / ".candidate.promotion.lock"
    if with_lock:
        lock.write_bytes(PROMOTION_LOCK_BYTES)
    return target, temporary, lock


def _quarantine(root: Path) -> tuple[Path, Path]:
    identity = hashlib.sha256(BUILD_ID.encode()).hexdigest()[:16]
    quarantine = root / f".gamelens-cleanup-{identity}-{'b' * 32}"
    bundle = quarantine / "bundle"
    bundle.mkdir(parents=True)
    (bundle / "item-slugs.json").write_bytes(b"[]")
    (bundle / "manifest.json").write_bytes(b"partial-manifest")
    receipt = {
        "version": 1,
        "database_fingerprint": DATABASE_FINGERPRINT,
        "artifact_set": str(root),
        "candidate": {
            "path": str(root / "original"),
            "build_id": BUILD_ID,
            "registry_status": "retired",
            "reason": "registry_retired",
            "bundle_fingerprint": "c" * 64,
        },
        "files": _recovery_bundle_files(bundle),
    }
    (quarantine / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    return quarantine, bundle


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_build_recovery_preview_is_deterministic_read_only_and_aggregate_only(
    tmp_path: Path,
) -> None:
    target, _temporary, _lock = _build_debris(tmp_path)
    before = _snapshot(tmp_path)
    service = _service()
    arguments = _arguments(tmp_path, target)

    first = service.recover(**arguments)
    second = service.recover(**arguments)

    assert first == second
    assert first["operation"] == "recovery_preview"
    assert first["requires_stopped_writers"] is True
    assert len(first["candidates"]) == 2
    assert _snapshot(tmp_path) == before
    assert "user_id" not in json.dumps(first)
    assert "partial-manifest" not in json.dumps(first)
    service.registry_reader._registry_states.assert_not_called()


@pytest.mark.parametrize("with_lock", [True, False])
def test_confirmed_build_recovery_removes_only_exact_debris(
    tmp_path: Path, with_lock: bool
) -> None:
    target, temporary, lock = _build_debris(tmp_path, with_lock=with_lock)
    content = tmp_path / "content"
    content.write_bytes(b"protected-content")
    unrelated = tmp_path / ".other.tmp-abcdefgh"
    unrelated.mkdir()
    service = _service()
    arguments = _arguments(tmp_path, target)
    arguments["configured_content_artifact"] = content
    preview = service.recover(**arguments)

    result = service.recover(
        **arguments, confirmation=preview["recovery_confirmation"], writers_stopped=True
    )

    assert result["removed_count"] == 2
    assert not temporary.exists()
    assert not lock.exists()
    assert not target.exists()
    assert unrelated.is_dir()
    assert content.read_bytes() == b"protected-content"
    assert service.recover(**arguments)["candidates"] == []


@pytest.mark.parametrize("marker", [b"", b"collaborative-artifact", PROMOTION_LOCK_BYTES])
def test_recovery_handles_lock_creation_interrupted_during_marker_write(
    tmp_path: Path, marker: bytes
) -> None:
    target = tmp_path / "candidate"
    lock = tmp_path / ".candidate.promotion.lock"
    lock.write_bytes(marker)
    service = _service()
    arguments = _arguments(tmp_path, target)
    preview = service.recover(**arguments)

    result = service.recover(
        **arguments, confirmation=preview["recovery_confirmation"], writers_stopped=True
    )

    assert result["removed_count"] == 1
    assert not lock.exists()
    assert not target.exists()


def test_recovery_rejects_unrecognized_lock_contents(tmp_path: Path) -> None:
    lock = tmp_path / ".candidate.promotion.lock"
    lock.write_bytes(b"unrelated-data")

    with pytest.raises(CollaborativeRetirementPreviewError) as caught:
        _service().recover(**_arguments(tmp_path, tmp_path / "candidate"))

    assert caught.value.code == "recovery_lock_invalid"
    assert lock.read_bytes() == b"unrelated-data"


@pytest.mark.parametrize(
    ("confirmation", "writers_stopped", "code"),
    [
        ("wrong", True, "recovery_confirmation_mismatch"),
        ("wrong", False, "recovery_writers_not_stopped"),
    ],
)
def test_recovery_refusals_leave_all_bytes_unchanged(
    tmp_path: Path, confirmation: str, writers_stopped: bool, code: str
) -> None:
    target, _temporary, _lock = _build_debris(tmp_path)
    before = _snapshot(tmp_path)

    with pytest.raises(CollaborativeRetirementPreviewError) as caught:
        _service().recover(
            **_arguments(tmp_path, target),
            confirmation=confirmation,
            writers_stopped=writers_stopped,
        )

    assert caught.value.code == code
    assert _snapshot(tmp_path) == before


def test_stale_recovery_confirmation_rejects_new_bytes(tmp_path: Path) -> None:
    target, temporary, _lock = _build_debris(tmp_path)
    service = _service()
    arguments = _arguments(tmp_path, target)
    preview = service.recover(**arguments)
    (temporary / "manifest.json").write_bytes(b"changed")
    before = _snapshot(tmp_path)

    with pytest.raises(CollaborativeRetirementPreviewError) as caught:
        service.recover(
            **arguments, confirmation=preview["recovery_confirmation"], writers_stopped=True
        )

    assert caught.value.code == "recovery_confirmation_mismatch"
    assert _snapshot(tmp_path) == before


def test_recovery_rechecks_candidate_after_final_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, temporary, lock = _build_debris(tmp_path)
    service = _service()
    arguments = _arguments(tmp_path, target)
    preview = service.recover(**arguments)
    original_inspect = service._inspect
    inspection_count = 0

    def inspect_then_change(*args: object, **kwargs: object) -> object:
        nonlocal inspection_count
        plan = original_inspect(*args, **kwargs)
        inspection_count += 1
        if inspection_count == 2:
            (temporary / "manifest.json").write_bytes(b"changed-after-final-preview")
        return plan

    monkeypatch.setattr(service, "_inspect", inspect_then_change)
    with pytest.raises(CollaborativeRetirementPreviewError) as caught:
        service.recover(
            **arguments, confirmation=preview["recovery_confirmation"], writers_stopped=True
        )

    assert caught.value.code == "recovery_target_changed"
    assert (temporary / "item-slugs.json").read_bytes() == b"[]"
    assert (temporary / "manifest.json").read_bytes() == b"changed-after-final-preview"
    assert lock.exists()


def test_interrupted_build_recovery_retries_remaining_files_with_new_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, temporary, lock = _build_debris(tmp_path)
    service = _service()
    arguments = _arguments(tmp_path, target)
    preview = service.recover(**arguments)
    original_unlink = Path.unlink

    def fail_second_file(path: Path, *args: object, **kwargs: object) -> None:
        if path == temporary / "manifest.json":
            raise OSError("simulated interruption")
        original_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail_second_file)
        with pytest.raises(CollaborativeRetirementPreviewError, match="interrupted"):
            service.recover(
                **arguments, confirmation=preview["recovery_confirmation"], writers_stopped=True
            )

    assert lock.exists()
    assert not (temporary / "item-slugs.json").exists()
    updated = service.recover(**arguments)
    assert updated["recovery_confirmation"] != preview["recovery_confirmation"]
    service.recover(
        **arguments, confirmation=updated["recovery_confirmation"], writers_stopped=True
    )
    assert not temporary.exists()
    assert not lock.exists()


@pytest.mark.parametrize("junction", [False, True])
def test_recovery_rejects_symlink_or_windows_junction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, junction: bool
) -> None:
    root = tmp_path / "artifacts"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "manifest.json").write_bytes(b"must-survive")
    target = root / "candidate"
    temporary = root / ".candidate.tmp-abcdefgh"
    if junction:
        temporary.mkdir()
        monkeypatch.setattr(Path, "is_junction", lambda path: path == temporary, raising=False)
    else:
        temporary.symlink_to(outside, target_is_directory=True)

    with pytest.raises(CollaborativeRetirementPreviewError):
        _service().recover(**_arguments(root, target))

    assert (outside / "manifest.json").read_bytes() == b"must-survive"


def test_recovery_rejects_path_escape_and_configured_debris(tmp_path: Path) -> None:
    target, temporary, _lock = _build_debris(tmp_path)
    service = _service()
    with pytest.raises(CollaborativeRetirementPreviewError) as escaped:
        service.recover(**_arguments(tmp_path, tmp_path.parent / "outside"))
    assert escaped.value.code == "recovery_target_invalid"
    arguments = _arguments(tmp_path, target)
    arguments["configured_collaborative_artifact"] = temporary
    with pytest.raises(CollaborativeRetirementPreviewError) as protected:
        service.recover(**arguments)
    assert protected.value.code == "recovery_target_protected"
    assert temporary.is_dir()


def test_registered_bundle_is_not_deleted_as_temporary_build_debris(tmp_path: Path) -> None:
    target, temporary, lock = _build_debris(tmp_path)
    (temporary / "manifest.json").write_text(json.dumps({"build": {"id": BUILD_ID}}))
    before = _snapshot(tmp_path)

    with pytest.raises(CollaborativeRetirementPreviewError) as caught:
        _service().recover(**_arguments(tmp_path, target))

    assert caught.value.code == "recovery_temp_registered"
    assert _snapshot(tmp_path) == before
    assert lock.exists()


def test_cleanup_recovery_accepts_only_remaining_receipt_bytes(tmp_path: Path) -> None:
    quarantine, bundle = _quarantine(tmp_path)
    (bundle / "manifest.json").unlink()
    service = _service()
    arguments = _arguments(tmp_path, quarantine, kind="cleanup")
    before = _snapshot(tmp_path)
    preview = service.recover(**arguments)
    assert service.recover(**arguments) == preview
    assert _snapshot(tmp_path) == before

    result = service.recover(
        **arguments, confirmation=preview["recovery_confirmation"], writers_stopped=True
    )

    assert result["removed_count"] == 1
    assert not quarantine.exists()
    assert not (tmp_path / "original").exists()
    assert service.recover(**arguments)["candidates"] == []


@pytest.mark.parametrize("status", ["active", "unregistered"])
def test_cleanup_recovery_refuses_active_or_unregistered_build(tmp_path: Path, status: str) -> None:
    quarantine, _bundle = _quarantine(tmp_path)
    service = _service()
    service.registry_reader._registry_states.return_value = (
        {BUILD_ID: CollaborativeRegistryLifecycleState(BUILD_ID, "active", 0)}
        if status == "active"
        else {}
    )
    before = _snapshot(tmp_path)

    with pytest.raises(CollaborativeRetirementPreviewError) as caught:
        service.recover(**_arguments(tmp_path, quarantine, kind="cleanup"))

    assert caught.value.code == "recovery_registry_unsafe"
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("change", ["database", "root", "content", "occupied", "protected"])
def test_cleanup_receipt_mismatch_fails_closed(tmp_path: Path, change: str) -> None:
    quarantine, bundle = _quarantine(tmp_path)
    arguments = _arguments(tmp_path, quarantine, kind="cleanup")
    if change == "database":
        arguments["database_fingerprint"] = "d" * 12
    elif change == "root":
        receipt_path = quarantine / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["artifact_set"] = str(tmp_path.parent)
        receipt_path.write_text(json.dumps(receipt))
    elif change == "content":
        (bundle / "item-slugs.json").write_bytes(b"changed")
    elif change == "occupied":
        (tmp_path / "original").mkdir()
    else:
        arguments["configured_collaborative_artifact"] = tmp_path / "original"
    before = _snapshot(tmp_path)

    with pytest.raises(CollaborativeRetirementPreviewError):
        _service().recover(**arguments)

    assert _snapshot(tmp_path) == before


def test_interrupted_cleanup_recovery_preserves_receipt_for_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quarantine, bundle = _quarantine(tmp_path)
    service = _service()
    arguments = _arguments(tmp_path, quarantine, kind="cleanup")
    preview = service.recover(**arguments)
    original_unlink = Path.unlink

    def fail_second_file(path: Path, *args: object, **kwargs: object) -> None:
        if path == bundle / "manifest.json":
            raise OSError("simulated interruption")
        original_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail_second_file)
        with pytest.raises(CollaborativeRetirementPreviewError):
            service.recover(
                **arguments, confirmation=preview["recovery_confirmation"], writers_stopped=True
            )
    assert (quarantine / "receipt.json").is_file()
    updated = service.recover(**arguments)
    service.recover(
        **arguments, confirmation=updated["recovery_confirmation"], writers_stopped=True
    )
    assert not quarantine.exists()


@pytest.mark.parametrize("with_receipt", [False, True])
def test_empty_cleanup_metadata_is_recoverable(tmp_path: Path, with_receipt: bool) -> None:
    quarantine = tmp_path / f".gamelens-cleanup-{'a' * 16}-{'b' * 32}"
    quarantine.mkdir()
    if with_receipt:
        (quarantine / "receipt.json").write_bytes(b"interrupted-receipt-write")
    service = _service()
    arguments = _arguments(tmp_path, quarantine, kind="cleanup")
    preview = service.recover(**arguments)
    service.recover(
        **arguments, confirmation=preview["recovery_confirmation"], writers_stopped=True
    )
    assert not quarantine.exists()
