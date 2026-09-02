from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from gamelens_recommender.collaborative_artifacts import (
    CollaborativeArtifactError,
    LoadedCollaborativeArtifact,
    load_collaborative_artifact,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT
from app.db.session import begin_repeatable_read
from app.repositories.collaborative_registry import (
    CollaborativeArtifactRegistryRepository,
    CollaborativeRegistryLifecycleState,
    CollaborativeRegistryMutationError,
)

MAX_RETIREMENT_PREVIEW_ENTRIES = 256
_DATABASE_FINGERPRINT = re.compile(r"^[0-9a-f]{12}$")


class CollaborativeRetirementPreviewError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _BundleInventory:
    path: Path
    relative_path: str
    build_id: str
    source_kind: Literal["fixture", "live"]
    fingerprint: str


@dataclass(frozen=True)
class _ProtectedContentInventory:
    path: Path
    relative_path: str
    fingerprint: str


class CollaborativeRetirementPreviewService:
    """Describe exact non-active bundle paths without mutating registry or disk."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def preview(
        self,
        artifact_set: Path,
        *,
        database_fingerprint: str,
        configured_content_artifact: Path | None,
        configured_collaborative_artifact: Path | None,
    ) -> dict[str, object]:
        if _DATABASE_FINGERPRINT.fullmatch(database_fingerprint) is None:
            raise CollaborativeRetirementPreviewError(
                "database_fingerprint_invalid",
                "Resolved database fingerprint is invalid",
            )
        root = _artifact_set_root(artifact_set)
        configured_content_path = _resolved_comparison_path(configured_content_artifact)
        configured_collaborative_path = _resolved_comparison_path(configured_collaborative_artifact)
        if any(
            _path_contains(configured_path, root)
            for configured_path in (configured_content_path, configured_collaborative_path)
            if configured_path is not None
        ):
            raise CollaborativeRetirementPreviewError(
                "artifact_set_path_protected",
                "Artifact set cannot be a configured serving artifact",
            )
        bundles, protected_content = _inventory_artifact_set(
            root,
            configured_content_artifact=configured_content_path,
        )
        live_build_ids = tuple(
            bundle.build_id for bundle in bundles if bundle.source_kind == "live"
        )
        states = self._registry_states(live_build_ids)
        missing = sorted(set(live_build_ids) - set(states))
        if missing:
            raise CollaborativeRetirementPreviewError(
                "retirement_bundle_unregistered",
                "Artifact retirement preview requires every live bundle to be registered",
            )

        candidates: list[dict[str, object]] = []
        protected: list[dict[str, object]] = [
            {
                "path": str(item.path),
                "build_id": None,
                "registry_status": None,
                "reason": "configured_content_artifact",
                "bundle_fingerprint": item.fingerprint,
            }
            for item in protected_content
        ]
        for bundle in bundles:
            if bundle.source_kind == "fixture":
                if not _path_contains(bundle.path, configured_collaborative_path):
                    raise CollaborativeRetirementPreviewError(
                        "retirement_bundle_not_live",
                        "Artifact retirement preview accepts only registered live bundles",
                    )
                protected.append(
                    _bundle_report(
                        bundle,
                        registry_status=None,
                        reason="configured_collaborative_artifact",
                    )
                )
                continue

            state = states[bundle.build_id]
            if _path_contains(bundle.path, configured_collaborative_path):
                protected.append(
                    _bundle_report(
                        bundle,
                        registry_status=state.status,
                        reason="configured_collaborative_artifact",
                    )
                )
            elif state.status == "active":
                protected.append(
                    _bundle_report(
                        bundle,
                        registry_status=state.status,
                        reason="registry_active",
                    )
                )
            else:
                candidates.append(
                    _bundle_report(
                        bundle,
                        registry_status=state.status,
                        reason=f"registry_{state.status}",
                    )
                )

        candidates.sort(key=lambda item: str(item["path"]))
        protected.sort(key=lambda item: str(item["path"]))
        artifact_set_fingerprint = _artifact_set_fingerprint(root, bundles, protected_content)
        retirement_fingerprint = _retirement_fingerprint(
            database_fingerprint=database_fingerprint,
            artifact_set_fingerprint=artifact_set_fingerprint,
            candidates=candidates,
            protected=protected,
        )
        confirmation = (
            "CLEAN COLLABORATIVE "
            f"{database_fingerprint} {artifact_set_fingerprint} {retirement_fingerprint}"
        )
        return {
            "status": "ok",
            "operation": "retirement_preview",
            "database": {"fingerprint": database_fingerprint},
            "artifact_set": {
                "path": str(root),
                "fingerprint": artifact_set_fingerprint,
                "entry_count": len(bundles) + len(protected_content),
            },
            "summary": {
                "candidate_count": len(candidates),
                "protected_count": len(protected),
            },
            "candidates": candidates,
            "protected": protected,
            "retirement_fingerprint": retirement_fingerprint,
            "cleanup_confirmation": confirmation,
        }

    def _registry_states(
        self,
        build_ids: tuple[str, ...],
    ) -> dict[str, CollaborativeRegistryLifecycleState]:
        session = self.session_factory()
        try:
            begin_repeatable_read(session, read_only=True)
            states = CollaborativeArtifactRegistryRepository(session).lifecycle_states(build_ids)
            session.rollback()
            return states
        except (CollaborativeRegistryMutationError, CollaborativeRetirementPreviewError):
            session.rollback()
            raise
        except (RuntimeError, SQLAlchemyError) as error:
            session.rollback()
            raise CollaborativeRetirementPreviewError(
                "retirement_preview_database_failed",
                "PostgreSQL rejected the artifact retirement preview",
            ) from error
        finally:
            session.close()


def _artifact_set_root(path: Path) -> Path:
    candidate = Path(path).expanduser()
    try:
        if _is_link(candidate):
            raise CollaborativeRetirementPreviewError(
                "artifact_set_path_invalid",
                "Artifact set cannot be a symbolic link or junction",
            )
        root = candidate.resolve(strict=True)
    except CollaborativeRetirementPreviewError:
        raise
    except (OSError, RuntimeError) as error:
        raise CollaborativeRetirementPreviewError(
            "artifact_set_missing",
            "Artifact set directory is missing or unreadable",
        ) from error
    if not root.is_dir():
        raise CollaborativeRetirementPreviewError(
            "artifact_set_path_invalid",
            "Artifact set must be a directory",
        )
    repository_root = PROJECT_ROOT.resolve(strict=True)
    if root == Path(root.anchor) or root == repository_root or repository_root.is_relative_to(root):
        raise CollaborativeRetirementPreviewError(
            "artifact_set_path_protected",
            "Artifact set cannot be a filesystem or repository root",
        )
    return root


def _inventory_artifact_set(
    root: Path,
    *,
    configured_content_artifact: Path | None,
) -> tuple[list[_BundleInventory], list[_ProtectedContentInventory]]:
    try:
        entries = sorted(root.iterdir(), key=lambda entry: entry.name)
    except OSError as error:
        raise CollaborativeRetirementPreviewError(
            "artifact_set_path_invalid",
            "Artifact set directory cannot be enumerated",
        ) from error
    if len(entries) > MAX_RETIREMENT_PREVIEW_ENTRIES:
        raise CollaborativeRetirementPreviewError(
            "artifact_set_limit_exceeded",
            "Artifact set exceeds the retirement preview entry limit",
        )

    bundles: list[_BundleInventory] = []
    protected_content: list[_ProtectedContentInventory] = []
    build_paths: dict[str, Path] = {}
    for entry in entries:
        resolved = _safe_entry(root, entry)
        relative_path = resolved.relative_to(root).as_posix()
        if _path_contains(resolved, configured_content_artifact):
            protected_content.append(
                _ProtectedContentInventory(
                    path=resolved,
                    relative_path=relative_path,
                    fingerprint=_protected_entry_fingerprint(resolved, relative_path),
                )
            )
            continue
        if not resolved.is_dir():
            raise CollaborativeRetirementPreviewError(
                "artifact_set_entry_invalid",
                "Artifact set entries must be collaborative bundle directories",
            )
        bundle = _load_bundle(resolved, relative_path)
        duplicate = build_paths.get(bundle.build_id)
        if duplicate is not None:
            raise CollaborativeRetirementPreviewError(
                "artifact_set_build_ambiguous",
                "Artifact set contains duplicate paths for one build ID",
            )
        build_paths[bundle.build_id] = bundle.path
        bundles.append(bundle)
    return bundles, protected_content


def _safe_entry(root: Path, entry: Path) -> Path:
    try:
        entry_stat = entry.lstat()
        regular_entry = stat.S_ISDIR(entry_stat.st_mode) or stat.S_ISREG(entry_stat.st_mode)
        if _is_link(entry) or not regular_entry:
            raise CollaborativeRetirementPreviewError(
                "artifact_set_entry_invalid",
                "Artifact set entries cannot be links or special files",
            )
        resolved = entry.resolve(strict=True)
        if resolved.parent != root:
            raise CollaborativeRetirementPreviewError(
                "artifact_set_entry_invalid",
                "Artifact set entry escapes its root",
            )
        return resolved
    except CollaborativeRetirementPreviewError:
        raise
    except (OSError, RuntimeError) as error:
        raise CollaborativeRetirementPreviewError(
            "artifact_set_entry_invalid",
            "Artifact set entry cannot be inspected",
        ) from error


def _load_bundle(path: Path, relative_path: str) -> _BundleInventory:
    try:
        artifact = load_collaborative_artifact(
            path,
            allow_fixture=True,
            now=datetime.min.replace(tzinfo=UTC),
        )
    except (CollaborativeArtifactError, OSError, ValueError) as error:
        raise CollaborativeRetirementPreviewError(
            "retirement_bundle_invalid",
            "Artifact set contains an invalid collaborative bundle",
        ) from error
    raw_source_kind = artifact.manifest["source"]["kind"]
    if raw_source_kind not in {"fixture", "live"}:
        raise CollaborativeRetirementPreviewError(
            "retirement_bundle_invalid",
            "Artifact set contains a bundle with invalid source provenance",
        )
    source_kind: Literal["fixture", "live"] = raw_source_kind
    return _BundleInventory(
        path=artifact.root,
        relative_path=relative_path,
        build_id=artifact.build_id,
        source_kind=source_kind,
        fingerprint=_bundle_fingerprint(artifact, relative_path),
    )


def _bundle_fingerprint(artifact: LoadedCollaborativeArtifact, relative_path: str) -> str:
    manifest = artifact.manifest
    payload = {
        "path": relative_path,
        "build": _plain_json(manifest["build"]),
        "source": _plain_json(manifest["source"]),
        "catalog_fingerprint": manifest["catalog_fingerprint"],
        "interaction_fingerprint": manifest["interaction_fingerprint"],
        "lifecycle": _plain_json(manifest["lifecycle"]),
        "members": _plain_json(manifest["members"]),
    }
    return _fingerprint(payload)


def _protected_entry_fingerprint(path: Path, relative_path: str) -> str:
    try:
        metadata = path.stat()
        kind = "directory" if path.is_dir() else "file"
    except OSError as error:
        raise CollaborativeRetirementPreviewError(
            "artifact_set_entry_invalid",
            "Protected artifact set entry changed during preview",
        ) from error
    return _fingerprint(
        {
            "path": relative_path,
            "kind": kind,
            "size": metadata.st_size,
            "protected": "configured_content_artifact",
        }
    )


def _artifact_set_fingerprint(
    root: Path,
    bundles: list[_BundleInventory],
    protected_content: list[_ProtectedContentInventory],
) -> str:
    entries = [
        {
            "path": bundle.relative_path,
            "kind": "collaborative_bundle",
            "build_id": bundle.build_id,
            "source_kind": bundle.source_kind,
            "fingerprint": bundle.fingerprint,
        }
        for bundle in bundles
    ]
    entries.extend(
        {
            "path": item.relative_path,
            "kind": "protected_content_artifact",
            "fingerprint": item.fingerprint,
        }
        for item in protected_content
    )
    entries.sort(key=lambda item: str(item["path"]))
    return _fingerprint({"root": _comparison_key(root), "entries": entries})


def _retirement_fingerprint(
    *,
    database_fingerprint: str,
    artifact_set_fingerprint: str,
    candidates: list[dict[str, object]],
    protected: list[dict[str, object]],
) -> str:
    return _fingerprint(
        {
            "database_fingerprint": database_fingerprint,
            "artifact_set_fingerprint": artifact_set_fingerprint,
            "candidates": candidates,
            "protected": protected,
        }
    )


def _bundle_report(
    bundle: _BundleInventory,
    *,
    registry_status: str | None,
    reason: str,
) -> dict[str, object]:
    return {
        "path": str(bundle.path),
        "build_id": bundle.build_id,
        "registry_status": registry_status,
        "reason": reason,
        "bundle_fingerprint": bundle.fingerprint,
    }


def _plain_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json(item) for item in value]
    return value


def _fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _comparison_key(path: Path | None) -> str | None:
    resolved = _resolved_comparison_path(path)
    return None if resolved is None else os.path.normcase(str(resolved))


def _resolved_comparison_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    try:
        return Path(path).expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise CollaborativeRetirementPreviewError(
            "configured_artifact_path_invalid",
            "Configured serving artifact path cannot be normalized",
        ) from error


def _path_contains(parent: Path | None, child: Path | None) -> bool:
    if parent is None or child is None:
        return False
    parent_key = _comparison_key(parent)
    child_key = _comparison_key(child)
    if parent_key is None or child_key is None:
        return False
    try:
        return os.path.commonpath((parent_key, child_key)) == parent_key
    except ValueError:
        return False


def _is_link(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or (callable(is_junction) and is_junction())
