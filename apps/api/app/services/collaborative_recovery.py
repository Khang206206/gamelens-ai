from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from typing import Literal, cast

from gamelens_recommender.collaborative_artifacts import (
    EXPECTED_DIRECTORY_MEMBERS,
    MAX_MANIFEST_BYTES,
)
from sqlalchemy.orm import Session

from app.services.collaborative_retirement import (
    MAX_RETIREMENT_PREVIEW_ENTRIES,
    CollaborativeRetirementPreviewError,
    CollaborativeRetirementPreviewService,
    _artifact_set_root,
    _cleanup_candidates,
    _comparison_key,
    _fingerprint,
    _fsync_directory,
    _is_link,
    _load_bundle,
    _path_contains,
    _recovery_bundle_files,
    _recovery_file_record,
    _safe_entry,
)

RecoveryKind = Literal["build", "cleanup"]
PROMOTION_LOCK_BYTES = b"collaborative-artifact-promotion\n"
MAX_RECEIPT_BYTES = 16384
_QUARANTINE_NAME = re.compile(r"^\.gamelens-cleanup-([0-9a-f]{16})-[0-9a-f]{32}$")


@dataclass(frozen=True)
class _RecoveryEntry:
    path: Path
    kind: Literal["build_temp", "promotion_lock", "cleanup_quarantine"]
    files: list[dict[str, object]]
    directories: tuple[Path, ...] = ()

    def report(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "kind": self.kind,
            "files": self.files,
            "directories": [str(path) for path in self.directories],
        }


@dataclass(frozen=True)
class _RecoveryPlan:
    root: Path
    target: Path
    kind: RecoveryKind
    database_fingerprint: str
    context: dict[str, object]
    entries: list[_RecoveryEntry]

    def report(self) -> dict[str, object]:
        payload = {
            "database": {"fingerprint": self.database_fingerprint},
            "artifact_set": str(self.root),
            "target": str(self.target),
            "kind": self.kind,
            "context": self.context,
            "candidates": [entry.report() for entry in self.entries],
        }
        fingerprint = _fingerprint(payload)
        return {
            "status": "ok",
            "operation": "recovery_preview",
            **payload,
            "recovery_fingerprint": fingerprint,
            "recovery_confirmation": (
                f"RECOVER COLLABORATIVE {self.database_fingerprint} {fingerprint}"
            ),
            "requires_stopped_writers": True,
        }


class CollaborativeArtifactRecoveryService:
    """Explicit, quiesced recovery of known build debris or cleanup receipts.

    A promotion marker contains no owner identity, so neither its age nor its
    presence proves that a writer stopped. Execution requires the operator's
    explicit quiescence acknowledgement as well as an exact fresh preview.
    Complete orphan registration remains the separate live `recover` operation.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.registry_reader = CollaborativeRetirementPreviewService(session_factory)

    def recover(
        self,
        artifact_set: Path,
        *,
        target: Path,
        kind: RecoveryKind,
        database_fingerprint: str,
        configured_content_artifact: Path | None,
        configured_collaborative_artifact: Path | None,
        confirmation: str | None = None,
        writers_stopped: bool = False,
    ) -> dict[str, object]:
        if confirmation is not None and not writers_stopped:
            raise CollaborativeRetirementPreviewError(
                "recovery_writers_not_stopped",
                "Recovery requires explicit acknowledgement that all artifact writers stopped",
            )
        arguments = {
            "target": target,
            "kind": kind,
            "database_fingerprint": database_fingerprint,
            "configured_content_artifact": configured_content_artifact,
            "configured_collaborative_artifact": configured_collaborative_artifact,
        }
        plan = self._inspect(artifact_set, **arguments)
        report = plan.report()
        if confirmation is None:
            return report
        if confirmation != report["recovery_confirmation"]:
            raise CollaborativeRetirementPreviewError(
                "recovery_confirmation_mismatch",
                "Recovery confirmation does not match the current preview",
            )
        verified = self._inspect(artifact_set, **arguments)
        if verified.report() != report:
            raise CollaborativeRetirementPreviewError(
                "recovery_target_changed", "Recovery targets changed after confirmation validation"
            )

        entries = list(plan.entries)
        if (
            kind == "build"
            and entries
            and not any(entry.kind == "promotion_lock" for entry in entries)
        ):
            # Block a new builder until recovery finishes, even for temp-only debris.
            lock = plan.root / f".{plan.target.name}.promotion.lock"
            _require_unprotected(
                lock, (configured_content_artifact, configured_collaborative_artifact)
            )
            try:
                with lock.open("xb") as stream:
                    stream.write(PROMOTION_LOCK_BYTES)
                    stream.flush()
                    os.fsync(stream.fileno())
                _fsync_directory(plan.root)
            except OSError as error:
                raise CollaborativeRetirementPreviewError(
                    "recovery_target_changed", "A builder acquired the target before recovery"
                ) from error
            entries.append(_lock_entry(plan.root, lock))

        removed: list[dict[str, object]] = []
        for entry in entries:
            current = self._inspect(artifact_set, **arguments)
            selected = next((item for item in current.entries if item.path == entry.path), None)
            if current.context != plan.context or selected != entry:
                raise CollaborativeRetirementPreviewError(
                    "recovery_target_changed", "Recovery candidate changed before removal"
                )
            _remove_entry(plan.root, entry)
            removed.append({"path": str(entry.path), "kind": entry.kind})
        return {
            "status": "ok",
            "operation": "recovery_cleanup",
            "database": report["database"],
            "artifact_set": str(plan.root),
            "target": str(plan.target),
            "kind": kind,
            "recovery_fingerprint": report["recovery_fingerprint"],
            "removed_count": len(removed),
            "removed": removed,
        }

    def _inspect(
        self,
        artifact_set: Path,
        *,
        target: Path,
        kind: RecoveryKind,
        database_fingerprint: str,
        configured_content_artifact: Path | None,
        configured_collaborative_artifact: Path | None,
    ) -> _RecoveryPlan:
        if re.fullmatch(r"[0-9a-f]{12}", database_fingerprint) is None:
            raise CollaborativeRetirementPreviewError(
                "database_fingerprint_invalid", "Resolved database fingerprint is invalid"
            )
        root = _artifact_set_root(artifact_set)
        protected = (configured_content_artifact, configured_collaborative_artifact)
        if any(_path_contains(path, root) for path in protected):
            raise CollaborativeRetirementPreviewError(
                "artifact_set_path_protected",
                "Recovery root cannot be a configured serving artifact",
            )
        target = _direct_target(root, target)
        if kind == "cleanup":
            context, entries = self._cleanup_entries(root, target, database_fingerprint, protected)
        elif kind == "build":
            context, entries = self._build_entries(root, target)
        else:
            raise CollaborativeRetirementPreviewError(
                "recovery_kind_invalid", "Recovery kind must be build or cleanup"
            )
        for entry in entries:
            _require_unprotected(entry.path, protected)
        return _RecoveryPlan(root, target, kind, database_fingerprint, context, entries)

    def _build_entries(
        self, root: Path, target: Path
    ) -> tuple[dict[str, object], list[_RecoveryEntry]]:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", target.name) is None:
            raise CollaborativeRetirementPreviewError(
                "recovery_target_invalid", "Build recovery requires a safe explicit output name"
            )
        context: dict[str, object] = {"artifact": None}
        if os.path.lexists(target):
            bundle = _load_bundle(_safe_entry(root, target), target.name)
            states = self.registry_reader._registry_states((bundle.build_id,))
            state = states.get(bundle.build_id)
            context["artifact"] = {
                "path": str(target),
                "build_id": bundle.build_id,
                "fingerprint": bundle.fingerprint,
                "registry_status": state.status if state is not None else None,
            }
        siblings = list(islice(root.iterdir(), MAX_RETIREMENT_PREVIEW_ENTRIES + 1))
        if len(siblings) > MAX_RETIREMENT_PREVIEW_ENTRIES:
            raise CollaborativeRetirementPreviewError(
                "artifact_set_limit_exceeded", "Recovery artifact set exceeds its entry limit"
            )
        temporary_name = re.compile(rf"^\.{re.escape(target.name)}\.tmp-[a-z0-9_]{{8}}$")
        if any(
            path.name.startswith(f".{target.name}.tmp-")
            and temporary_name.fullmatch(path.name) is None
            for path in siblings
        ):
            raise CollaborativeRetirementPreviewError(
                "recovery_target_invalid", "Recovery found an ambiguous build temporary path"
            )
        entries = [
            _RecoveryEntry(
                _safe_entry(root, path), "build_temp", _recovery_bundle_files(path), (path,)
            )
            for path in sorted(siblings)
            if temporary_name.fullmatch(path.name)
        ]
        for entry in entries:
            build_id = _temporary_build_id(entry)
            if build_id is not None and self.registry_reader._registry_states((build_id,)):
                raise CollaborativeRetirementPreviewError(
                    "recovery_temp_registered",
                    "Registered bundles cannot be removed as build temporary files",
                )
        lock = root / f".{target.name}.promotion.lock"
        if os.path.lexists(lock):
            entries.append(_lock_entry(root, lock))
        return context, entries

    def _cleanup_entries(
        self,
        root: Path,
        target: Path,
        database_fingerprint: str,
        protected: tuple[Path | None, ...],
    ) -> tuple[dict[str, object], list[_RecoveryEntry]]:
        match = _QUARANTINE_NAME.fullmatch(target.name)
        if match is None:
            raise CollaborativeRetirementPreviewError(
                "recovery_target_invalid", "Cleanup recovery requires an exact quarantine path"
            )
        if not os.path.lexists(target):
            return {"cleanup": None}, []
        _safe_entry(root, target)
        if not target.is_dir():
            raise CollaborativeRetirementPreviewError(
                "recovery_target_invalid", "Cleanup quarantine must be a directory"
            )
        names = {path.name for path in islice(target.iterdir(), 3)}
        if not names <= {"receipt.json", "bundle"}:
            raise CollaborativeRetirementPreviewError(
                "recovery_receipt_required",
                "Nonempty legacy quarantine needs an inspectable cleanup receipt",
            )
        files: list[dict[str, object]] = []
        receipt_path = target / "receipt.json"
        context: dict[str, object] = {"cleanup": None}
        directories = (target,)
        if "receipt.json" in names:
            files.append(_recovery_file_record(receipt_path, maximum=MAX_RECEIPT_BYTES))
        if "bundle" in names:
            if "receipt.json" not in names:
                raise CollaborativeRetirementPreviewError(
                    "recovery_receipt_required", "Cleanup bundle recovery requires its receipt"
                )
            try:
                with receipt_path.open("rb") as stream:
                    receipt_bytes = stream.read(MAX_RECEIPT_BYTES + 1)
                if (
                    len(receipt_bytes) > MAX_RECEIPT_BYTES
                    or hashlib.sha256(receipt_bytes).hexdigest() != files[0]["sha256"]
                ):
                    raise ValueError("Receipt changed during inspection")
                receipt = json.loads(receipt_bytes)
                if (
                    not isinstance(receipt, dict)
                    or set(receipt)
                    != {"version", "database_fingerprint", "artifact_set", "candidate", "files"}
                    or type(receipt["version"]) is not int
                    or receipt["version"] != 1
                    or receipt["database_fingerprint"] != database_fingerprint
                    or receipt["artifact_set"] != str(root)
                ):
                    raise ValueError("Receipt identity mismatch")
                candidate = _cleanup_candidates({"candidates": [receipt["candidate"]]}, root)[0]
                if hashlib.sha256(candidate.build_id.encode()).hexdigest()[:16] != match[1]:
                    raise ValueError("Quarantine identity mismatch")
                _require_unprotected(candidate.path, protected)
                if os.path.lexists(candidate.path):
                    raise ValueError("Original artifact path is occupied")
                expected = _receipt_files(receipt["files"])
            except (ValueError, KeyError, TypeError, IndexError) as error:
                raise CollaborativeRetirementPreviewError(
                    "recovery_receipt_invalid",
                    "Cleanup receipt is invalid or belongs to another target",
                ) from error
            state = self.registry_reader._registry_states((candidate.build_id,)).get(
                candidate.build_id
            )
            if state is None or state.status not in {"invalidated", "retired"}:
                raise CollaborativeRetirementPreviewError(
                    "recovery_registry_unsafe",
                    "Cleanup recovery requires a registered non-active build",
                )
            bundle = _safe_entry(target, target / "bundle")
            remaining = _recovery_bundle_files(bundle)
            if any(record not in expected for record in remaining):
                raise CollaborativeRetirementPreviewError(
                    "recovery_target_changed",
                    "Remaining bundle bytes do not match the cleanup receipt",
                )
            files.extend({**record, "name": f"bundle/{record['name']}"} for record in remaining)
            context["cleanup"] = {
                "build_id": candidate.build_id,
                "original_path": str(candidate.path),
                "registry_status": state.status,
                "invalidation_epoch": state.invalidation_epoch,
            }
            directories = (bundle, target)
        return context, [_RecoveryEntry(target, "cleanup_quarantine", files, directories)]


def _direct_target(root: Path, target: Path) -> Path:
    raw = Path(target).expanduser()
    if raw.name in {"", ".", ".."} or _comparison_key(raw.parent) != _comparison_key(root):
        raise CollaborativeRetirementPreviewError(
            "recovery_target_invalid",
            "Recovery target must be an explicit direct artifact-set child",
        )
    result = root / raw.name
    if _is_link(result):
        raise CollaborativeRetirementPreviewError(
            "recovery_target_invalid", "Recovery target cannot be a symbolic link or junction"
        )
    return result


def _require_unprotected(path: Path, protected: tuple[Path | None, ...]) -> None:
    if any(_path_contains(path, item) or _path_contains(item, path) for item in protected):
        raise CollaborativeRetirementPreviewError(
            "recovery_target_protected", "Recovery cannot remove a configured serving artifact"
        )


def _lock_entry(root: Path, path: Path) -> _RecoveryEntry:
    _safe_entry(root, path)
    record = _recovery_file_record(path, maximum=len(PROMOTION_LOCK_BYTES))
    with path.open("rb") as stream:
        marker = stream.read(len(PROMOTION_LOCK_BYTES) + 1)
    marker_fingerprint = hashlib.sha256(marker).hexdigest()
    if record["sha256"] != marker_fingerprint or not PROMOTION_LOCK_BYTES.startswith(marker):
        raise CollaborativeRetirementPreviewError(
            "recovery_lock_invalid", "Recovery lock is not a complete or partial promotion marker"
        )
    return _RecoveryEntry(path, "promotion_lock", [record])


def _temporary_build_id(entry: _RecoveryEntry) -> str | None:
    manifest_record = next(
        (record for record in entry.files if record["name"] == "manifest.json"), None
    )
    if manifest_record is None:
        return None
    with (entry.path / "manifest.json").open("rb") as stream:
        payload = stream.read(MAX_MANIFEST_BYTES + 1)
    if hashlib.sha256(payload).hexdigest() != manifest_record["sha256"]:
        raise CollaborativeRetirementPreviewError(
            "recovery_target_changed", "Temporary manifest changed during inspection"
        )
    try:
        manifest = json.loads(payload)
    except ValueError:
        return None  # A stopped builder may have left an incomplete manifest write.
    build = manifest.get("build") if isinstance(manifest, dict) else None
    build_id = build.get("id") if isinstance(build, dict) else None
    if isinstance(build_id, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", build_id):
        return build_id
    return None


def _receipt_files(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list) or len(value) > len(EXPECTED_DIRECTORY_MEMBERS):
        raise ValueError("Invalid receipt files")
    names: set[str] = set()
    for record in value:
        if (
            not isinstance(record, dict)
            or set(record) != {"name", "size", "sha256"}
            or record["name"] not in EXPECTED_DIRECTORY_MEMBERS
            or record["name"] in names
            or type(record["size"]) is not int
            or record["size"] < 0
            or not isinstance(record["sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is None
        ):
            raise ValueError("Invalid receipt file record")
        names.add(record["name"])
    return value


def _remove_entry(root: Path, entry: _RecoveryEntry) -> None:
    """Unlink only enumerated bytes; never recursively remove unconfirmed files."""
    try:
        _artifact_set_root(root)
        _safe_entry(root, entry.path)
        base = entry.path if entry.directories else entry.path.parent
        records = sorted(entry.files, key=lambda item: item["name"] == "receipt.json")
        for record in records:
            if record["name"] == "receipt.json":
                for directory in entry.directories[:-1]:
                    _safe_entry(directory.parent, directory)
                    directory.rmdir()
                _fsync_directory(entry.path)
            path = base / cast(str, record["name"])
            if path.parent != root:
                _safe_entry(path.parent.parent, path.parent)
            _safe_entry(path.parent, path)
            current = _recovery_file_record(path, maximum=cast(int, record["size"]))
            if {**current, "name": record["name"]} != record:
                raise CollaborativeRetirementPreviewError(
                    "recovery_target_changed", "Recovery file changed immediately before removal"
                )
            path.unlink()
        if entry.directories:
            entry.path.rmdir()
        _fsync_directory(root)
    except OSError as error:
        raise CollaborativeRetirementPreviewError(
            "recovery_filesystem_failed",
            "Recovery was interrupted; preview remaining files before retry",
        ) from error
