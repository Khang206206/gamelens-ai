from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import math
import os
import re
import shutil
import stat
import sys
import tempfile
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np
import scipy
from numpy.lib import format as npy_format

from gamelens_recommender.collaborative_training import (
    MAX_NEIGHBOR_NONZERO,
    MAX_NEIGHBORS_PER_ITEM,
    CollaborativeNeighborhoods,
    quantize_similarity,
)
from gamelens_recommender.config import SCORE_SCALE
from gamelens_recommender.interaction_snapshot import (
    LABEL_POLICY_ID,
    MAX_PAIR_CONTRIBUTIONS,
    MAX_POSITIVE_EDGES,
    MAX_PROFILES,
    MAX_UNIQUE_ITEMS,
    MIN_ACTIVATION_EDGES,
    MIN_ACTIVATION_ITEMS,
    MIN_ACTIVATION_USERS,
    MIN_ITEM_SUPPORT,
    MIN_PAIR_SUPPORT,
    MIN_PROFILE_ITEMS,
)
from gamelens_recommender.schemas import SLUG_PATTERN

COLLABORATIVE_ARTIFACT_SCHEMA_VERSION = 1
COLLABORATIVE_MODEL_NAME = "gamelens-item-item-cosine"
COLLABORATIVE_MODEL_VERSION = "1.0.0"
COLLABORATIVE_CODE_COMPATIBILITY = "stage-5-v1"
MAX_ARTIFACT_MEMBERS = 6
MAX_MANIFEST_BYTES = 1 * 1024 * 1024
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_JSON_DEPTH = 16
MAX_NPY_HEADER_BYTES = 4096
MAX_BUILD_ID_LENGTH = 128
MAX_CONSENT_VERSION_LENGTH = 100
MAX_FIXTURE_ID_LENGTH = 128
MAX_GAME_SLUG_LENGTH = 220

ITEM_SLUGS_MEMBER = "item-slugs.json"
ITEM_SUPPORT_MEMBER = "item-support.npy"
NEIGHBOR_INDICES_MEMBER = "neighbors-indices.npy"
NEIGHBOR_INDPTR_MEMBER = "neighbors-indptr.npy"
SIMILARITY_UNITS_MEMBER = "similarity-units.npy"
PAIR_SUPPORT_MEMBER = "pair-support.npy"
REQUIRED_MEMBERS = (
    ITEM_SLUGS_MEMBER,
    ITEM_SUPPORT_MEMBER,
    NEIGHBOR_INDICES_MEMBER,
    NEIGHBOR_INDPTR_MEMBER,
    SIMILARITY_UNITS_MEMBER,
    PAIR_SUPPORT_MEMBER,
)
EXPECTED_DIRECTORY_MEMBERS = frozenset(("manifest.json", *REQUIRED_MEMBERS))

ITEM_SUPPORT_DTYPE = np.dtype("int64")
INDEX_DTYPE = np.dtype("int32")
SIMILARITY_UNITS_DTYPE = np.dtype("int32")
PAIR_SUPPORT_DTYPE = np.dtype("int64")

_LOWER_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_TIMESTAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z$")
_MANIFEST_KEYS = frozenset(
    {
        "artifact_schema_version",
        "model",
        "code_compatibility",
        "build",
        "source",
        "catalog_fingerprint",
        "interaction_fingerprint",
        "label_policy",
        "lifecycle",
        "thresholds",
        "numeric",
        "matrix",
        "neighbors",
        "limits",
        "members",
    }
)
_BUILD_KEYS = frozenset({"id", "built_at", "software"})
_SOURCE_KEYS = frozenset({"kind", "fixture_id", "contains_real_user_data", "quality_evidence"})
_LIFECYCLE_KEYS = frozenset({"cutoff", "consent_version", "data_revision", "valid_until"})
_MATRIX_KEYS = frozenset(
    {
        "retained_contributors",
        "retained_items",
        "retained_positive_edges",
        "pair_contributions",
    }
)
_NEIGHBOR_KEYS = frozenset({"shape", "nonzero", "format", "maximum_per_item"})
_MEMBER_METADATA_KEYS = frozenset({"size", "sha256"})


class CollaborativeArtifactError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CollaborativeBuildMetadata:
    source_kind: str
    catalog_fingerprint: str
    interaction_fingerprint: str
    build_id: str
    built_at: datetime
    fixture_id: str | None = None
    cutoff: datetime | None = None
    consent_version: str | None = None
    data_revision: int | None = None
    valid_until: datetime | None = None


@dataclass(frozen=True)
class LoadedCollaborativeArtifact:
    root: Path
    manifest: Mapping[str, Any]
    item_slugs: tuple[str, ...]
    item_support: np.ndarray
    neighbor_indices: np.ndarray
    neighbor_indptr: np.ndarray
    similarity_units: np.ndarray
    pair_support: np.ndarray
    slug_to_index: Mapping[str, int]

    @property
    def build_id(self) -> str:
        return str(self.manifest["build"]["id"])

    @property
    def catalog_fingerprint(self) -> str:
        return str(self.manifest["catalog_fingerprint"])

    @property
    def interaction_fingerprint(self) -> str:
        return str(self.manifest["interaction_fingerprint"])

    @property
    def model_name(self) -> str:
        return str(self.manifest["model"]["name"])

    @property
    def model_version(self) -> str:
        return str(self.manifest["model"]["version"])


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _exact_keys(value: object, expected: frozenset[str], *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or frozenset(value) != expected:
        raise CollaborativeArtifactError("manifest_invalid", f"{label} keys are invalid")
    return value


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and _LOWER_SHA256.fullmatch(value) is not None


def _is_safe_identifier(value: object, *, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= maximum
        and _SAFE_ID.fullmatch(value) is not None
    )


def _format_timestamp(value: datetime, *, label: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise CollaborativeArtifactError(
            "manifest_invalid", f"{label} must be a timezone-aware datetime"
        )
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: object, *, label: str) -> datetime:
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        raise CollaborativeArtifactError("manifest_invalid", f"{label} is invalid")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError as error:
        raise CollaborativeArtifactError("manifest_invalid", f"{label} is invalid") from error
    if _format_timestamp(parsed, label=label) != value:
        raise CollaborativeArtifactError("manifest_invalid", f"{label} is not canonical")
    return parsed


def _validate_build_metadata(
    metadata: CollaborativeBuildMetadata,
    *,
    allow_fixture: bool,
) -> None:
    if not isinstance(metadata, CollaborativeBuildMetadata):
        raise CollaborativeArtifactError("manifest_invalid", "Build metadata is invalid")
    if metadata.source_kind not in {"fixture", "live"}:
        raise CollaborativeArtifactError("manifest_invalid", "Artifact source kind is invalid")
    if not _is_sha256(metadata.catalog_fingerprint):
        raise CollaborativeArtifactError("catalog_mismatch", "Catalog fingerprint is invalid")
    if not _is_sha256(metadata.interaction_fingerprint):
        raise CollaborativeArtifactError("manifest_invalid", "Interaction fingerprint is invalid")
    if not _is_safe_identifier(metadata.build_id, maximum=MAX_BUILD_ID_LENGTH):
        raise CollaborativeArtifactError("manifest_invalid", "Build ID is invalid")
    built_at = _parse_timestamp(
        _format_timestamp(metadata.built_at, label="Build timestamp"),
        label="Build timestamp",
    )
    if metadata.source_kind == "fixture":
        if not allow_fixture:
            raise CollaborativeArtifactError(
                "fixture_not_allowed", "Fixture artifacts require explicit permission"
            )
        if not _is_safe_identifier(metadata.fixture_id, maximum=MAX_FIXTURE_ID_LENGTH) or not str(
            metadata.fixture_id
        ).startswith("stage-5-"):
            raise CollaborativeArtifactError("manifest_invalid", "Fixture ID is invalid")
        if any(
            value is not None
            for value in (
                metadata.cutoff,
                metadata.consent_version,
                metadata.data_revision,
            )
        ):
            raise CollaborativeArtifactError(
                "manifest_invalid", "Fixture artifacts cannot contain live lifecycle fields"
            )
        if metadata.valid_until is None:
            raise CollaborativeArtifactError(
                "manifest_invalid", "Fixture artifact validity horizon is required"
            )
        valid_until = _parse_timestamp(
            _format_timestamp(metadata.valid_until, label="Validity horizon"),
            label="Validity horizon",
        )
        if valid_until <= built_at:
            raise CollaborativeArtifactError(
                "manifest_invalid", "Fixture validity horizon must follow its build time"
            )
        return

    if metadata.fixture_id is not None:
        raise CollaborativeArtifactError(
            "manifest_invalid", "Live artifacts cannot contain a fixture ID"
        )
    if (
        not isinstance(metadata.consent_version, str)
        or not metadata.consent_version.strip()
        or metadata.consent_version != metadata.consent_version.strip()
        or len(metadata.consent_version) > MAX_CONSENT_VERSION_LENGTH
    ):
        raise CollaborativeArtifactError("manifest_invalid", "Live consent version is invalid")
    if type(metadata.data_revision) is not int or metadata.data_revision < 0:
        raise CollaborativeArtifactError("manifest_invalid", "Live data revision is invalid")
    if metadata.cutoff is None or metadata.valid_until is None:
        raise CollaborativeArtifactError(
            "manifest_invalid", "Live lifecycle timestamps are required"
        )
    cutoff = _parse_timestamp(
        _format_timestamp(metadata.cutoff, label="Cutoff"),
        label="Cutoff",
    )
    valid_until = _parse_timestamp(
        _format_timestamp(metadata.valid_until, label="Validity horizon"),
        label="Validity horizon",
    )
    if cutoff > built_at or valid_until <= built_at or valid_until <= cutoff:
        raise CollaborativeArtifactError(
            "manifest_invalid", "Live lifecycle timestamp order is invalid"
        )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CollaborativeArtifactError("manifest_invalid", f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_finite_constant(value: str) -> None:
    raise CollaborativeArtifactError(
        "manifest_invalid", f"Non-finite JSON constant is forbidden: {value}"
    )


def _validate_json_depth(value: object, *, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise CollaborativeArtifactError("artifact_limit_exceeded", "JSON nesting is too deep")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise CollaborativeArtifactError("manifest_invalid", "JSON object key is invalid")
            _validate_json_depth(child, depth=depth + 1)
    elif isinstance(value, list):
        for child in value:
            _validate_json_depth(child, depth=depth + 1)


def _load_strict_json(payload: bytes, *, name: str) -> object:
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite_constant,
        )
        _validate_json_depth(value)
        canonical = _canonical_json_bytes(value)
    except CollaborativeArtifactError:
        raise
    except (JSONDecodeErrorAlias, UnicodeError, RecursionError, TypeError, ValueError) as error:
        raise CollaborativeArtifactError(
            "manifest_invalid", f"Invalid JSON member: {name}"
        ) from error
    if canonical != payload:
        raise CollaborativeArtifactError(
            "manifest_invalid", f"JSON member is not canonical: {name}"
        )
    return value


# An alias keeps the exception tuple above readable without exposing json internals.
JSONDecodeErrorAlias = json.JSONDecodeError


def _expected_thresholds() -> dict[str, int]:
    return {
        "minimum_profile_items": MIN_PROFILE_ITEMS,
        "minimum_item_support": MIN_ITEM_SUPPORT,
        "minimum_pair_support": MIN_PAIR_SUPPORT,
        "activation_minimum_users": MIN_ACTIVATION_USERS,
        "activation_minimum_edges": MIN_ACTIVATION_EDGES,
        "activation_minimum_items": MIN_ACTIVATION_ITEMS,
    }


def _expected_numeric() -> dict[str, object]:
    return {
        "score_scale": SCORE_SCALE,
        "rounding": "half-up",
        "build_float_dtype": "float64",
        "item_support_dtype": ITEM_SUPPORT_DTYPE.name,
        "index_dtype": INDEX_DTYPE.name,
        "similarity_units_dtype": SIMILARITY_UNITS_DTYPE.name,
        "pair_support_dtype": PAIR_SUPPORT_DTYPE.name,
        "selection_order": [
            "similarity_units_desc",
            "pair_support_desc",
            "neighbor_slug_asc",
        ],
        "storage_order": "neighbor_index_asc",
    }


def _expected_limits() -> dict[str, int]:
    return {
        "maximum_members": MAX_ARTIFACT_MEMBERS,
        "maximum_manifest_bytes": MAX_MANIFEST_BYTES,
        "maximum_member_bytes": MAX_MEMBER_BYTES,
        "maximum_total_bytes": MAX_TOTAL_BYTES,
        "maximum_json_depth": MAX_JSON_DEPTH,
        "maximum_profiles": MAX_PROFILES,
        "maximum_unique_items": MAX_UNIQUE_ITEMS,
        "maximum_positive_edges": MAX_POSITIVE_EDGES,
        "maximum_pair_contributions": MAX_PAIR_CONTRIBUTIONS,
        "maximum_neighbor_nonzero": MAX_NEIGHBOR_NONZERO,
        "maximum_neighbors_per_item": MAX_NEIGHBORS_PER_ITEM,
    }


def _expected_software() -> dict[str, str]:
    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }


def _metadata_from_manifest(manifest: dict[str, Any]) -> CollaborativeBuildMetadata:
    build = _exact_keys(manifest.get("build"), _BUILD_KEYS, label="Build metadata")
    source = _exact_keys(manifest.get("source"), _SOURCE_KEYS, label="Source metadata")
    lifecycle = _exact_keys(manifest.get("lifecycle"), _LIFECYCLE_KEYS, label="Lifecycle metadata")
    built_at = _parse_timestamp(build.get("built_at"), label="Build timestamp")
    cutoff_value = lifecycle.get("cutoff")
    valid_until_value = lifecycle.get("valid_until")
    cutoff = None if cutoff_value is None else _parse_timestamp(cutoff_value, label="Cutoff")
    valid_until = (
        None
        if valid_until_value is None
        else _parse_timestamp(valid_until_value, label="Validity horizon")
    )
    return CollaborativeBuildMetadata(
        source_kind=source.get("kind"),
        catalog_fingerprint=manifest.get("catalog_fingerprint"),
        interaction_fingerprint=manifest.get("interaction_fingerprint"),
        build_id=build.get("id"),
        built_at=built_at,
        fixture_id=source.get("fixture_id"),
        cutoff=cutoff,
        consent_version=lifecycle.get("consent_version"),
        data_revision=lifecycle.get("data_revision"),
        valid_until=valid_until,
    )


def _validate_manifest(
    value: object,
    *,
    manifest_size: int,
    allow_fixture: bool,
) -> tuple[dict[str, Any], CollaborativeBuildMetadata]:
    manifest = _exact_keys(value, _MANIFEST_KEYS, label="Manifest")
    if manifest.get("artifact_schema_version") != COLLABORATIVE_ARTIFACT_SCHEMA_VERSION:
        raise CollaborativeArtifactError(
            "artifact_schema_incompatible", "Collaborative artifact schema is incompatible"
        )
    if manifest.get("model") != {
        "name": COLLABORATIVE_MODEL_NAME,
        "version": COLLABORATIVE_MODEL_VERSION,
    }:
        raise CollaborativeArtifactError(
            "model_incompatible", "Collaborative model identity is incompatible"
        )
    if manifest.get("code_compatibility") != COLLABORATIVE_CODE_COMPATIBILITY:
        raise CollaborativeArtifactError(
            "code_incompatible", "Collaborative code compatibility is invalid"
        )
    build = _exact_keys(manifest.get("build"), _BUILD_KEYS, label="Build metadata")
    if build.get("software") != _expected_software():
        raise CollaborativeArtifactError(
            "code_incompatible", "Collaborative build software is incompatible"
        )
    source = _exact_keys(manifest.get("source"), _SOURCE_KEYS, label="Source metadata")
    expected_source_flags = {
        "contains_real_user_data": source.get("kind") == "live",
        "quality_evidence": False,
    }
    if any(source.get(key) != expected for key, expected in expected_source_flags.items()):
        raise CollaborativeArtifactError("manifest_invalid", "Source provenance flags are invalid")
    metadata = _metadata_from_manifest(manifest)
    _validate_build_metadata(metadata, allow_fixture=allow_fixture)
    if manifest.get("label_policy") != LABEL_POLICY_ID:
        raise CollaborativeArtifactError(
            "model_incompatible", "Collaborative label policy is incompatible"
        )
    if manifest.get("thresholds") != _expected_thresholds():
        raise CollaborativeArtifactError(
            "config_incompatible", "Collaborative thresholds are incompatible"
        )
    if manifest.get("numeric") != _expected_numeric():
        raise CollaborativeArtifactError(
            "config_incompatible", "Collaborative numeric policy is incompatible"
        )
    if manifest.get("limits") != _expected_limits():
        raise CollaborativeArtifactError(
            "config_incompatible", "Collaborative resource limits are incompatible"
        )

    matrix = _exact_keys(manifest.get("matrix"), _MATRIX_KEYS, label="Matrix metadata")
    neighbors = _exact_keys(manifest.get("neighbors"), _NEIGHBOR_KEYS, label="Neighbor metadata")
    for key in _MATRIX_KEYS:
        if type(matrix.get(key)) is not int:
            raise CollaborativeArtifactError("manifest_invalid", "Matrix count is invalid")
    retained_items = matrix["retained_items"]
    neighbor_nonzero = neighbors.get("nonzero")
    if (
        type(retained_items) is not int
        or not MIN_ACTIVATION_ITEMS <= retained_items <= MAX_UNIQUE_ITEMS
        or neighbors.get("shape") != [retained_items, retained_items]
        or type(neighbor_nonzero) is not int
        or not 1 <= neighbor_nonzero <= MAX_NEIGHBOR_NONZERO
        or neighbors.get("format") != "csr-transparent-npy"
        or neighbors.get("maximum_per_item") != MAX_NEIGHBORS_PER_ITEM
    ):
        raise CollaborativeArtifactError(
            "artifact_shape_invalid", "Collaborative neighbor metadata is invalid"
        )

    members = manifest.get("members")
    if not isinstance(members, dict) or frozenset(members) != frozenset(REQUIRED_MEMBERS):
        raise CollaborativeArtifactError("manifest_invalid", "Artifact member set is invalid")
    if len(members) != MAX_ARTIFACT_MEMBERS:
        raise CollaborativeArtifactError(
            "artifact_limit_exceeded", "Artifact member count is invalid"
        )
    total_size = manifest_size
    for name in REQUIRED_MEMBERS:
        member = _exact_keys(
            members.get(name), _MEMBER_METADATA_KEYS, label=f"Member metadata for {name}"
        )
        size = member.get("size")
        checksum = member.get("sha256")
        if type(size) is not int or not 1 <= size <= MAX_MEMBER_BYTES:
            raise CollaborativeArtifactError(
                "artifact_limit_exceeded", f"Artifact member size is invalid: {name}"
            )
        if not _is_sha256(checksum):
            raise CollaborativeArtifactError(
                "manifest_invalid", f"Artifact member checksum is invalid: {name}"
            )
        total_size += size
    if total_size > MAX_TOTAL_BYTES:
        raise CollaborativeArtifactError(
            "artifact_limit_exceeded", "Collaborative artifact is too large"
        )
    return manifest, metadata


def _resolved_artifact_root(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    try:
        if candidate.is_symlink():
            raise CollaborativeArtifactError(
                "artifact_path_invalid", "Artifact root cannot be a symbolic link"
            )
        root = candidate.resolve(strict=True)
    except CollaborativeArtifactError:
        raise
    except (OSError, RuntimeError) as error:
        raise CollaborativeArtifactError(
            "artifact_missing", "Configured collaborative artifact is missing"
        ) from error
    if not root.is_dir():
        raise CollaborativeArtifactError(
            "artifact_missing", "Configured collaborative artifact is not a directory"
        )
    return root


def _validated_directory_entries(root: Path) -> dict[str, Path]:
    try:
        entries = root.iterdir()
    except OSError as error:
        raise CollaborativeArtifactError(
            "artifact_missing", "Collaborative artifact directory is unreadable"
        ) from error
    paths: dict[str, Path] = {}
    try:
        for entry in entries:
            if len(paths) >= len(EXPECTED_DIRECTORY_MEMBERS):
                raise CollaborativeArtifactError(
                    "artifact_path_invalid", "Artifact directory contains unexpected members"
                )
            try:
                entry_stat = entry.lstat()
            except OSError as error:
                raise CollaborativeArtifactError(
                    "artifact_path_invalid", "Artifact member cannot be inspected"
                ) from error
            if entry.is_symlink() or not stat.S_ISREG(entry_stat.st_mode):
                raise CollaborativeArtifactError(
                    "artifact_path_invalid", "Artifact members must be regular files"
                )
            try:
                entry.resolve(strict=True).relative_to(root)
            except (OSError, RuntimeError, ValueError) as error:
                raise CollaborativeArtifactError(
                    "artifact_path_invalid", "Artifact member escapes its root"
                ) from error
            paths[entry.name] = entry
    except CollaborativeArtifactError:
        raise
    except OSError as error:
        raise CollaborativeArtifactError(
            "artifact_path_invalid", "Artifact directory changed during validation"
        ) from error
    actual = frozenset(paths)
    missing = EXPECTED_DIRECTORY_MEMBERS - actual
    if missing:
        raise CollaborativeArtifactError("artifact_missing", "Artifact member is missing")
    if actual != EXPECTED_DIRECTORY_MEMBERS:
        raise CollaborativeArtifactError(
            "artifact_path_invalid", "Artifact directory contains unexpected members"
        )
    return paths


def _read_bounded(path: Path, *, maximum: int, label: str) -> bytes:
    try:
        with path.open("rb") as stream:
            descriptor_stat = os.fstat(stream.fileno())
            if not stat.S_ISREG(descriptor_stat.st_mode):
                raise CollaborativeArtifactError(
                    "artifact_path_invalid", f"{label} is not a regular file"
                )
            if descriptor_stat.st_size > maximum:
                raise CollaborativeArtifactError(
                    "artifact_limit_exceeded", f"{label} exceeds its byte limit"
                )
            payload = stream.read(maximum + 1)
    except CollaborativeArtifactError:
        raise
    except OSError as error:
        raise CollaborativeArtifactError("artifact_missing", f"{label} is unreadable") from error
    if len(payload) > maximum:
        raise CollaborativeArtifactError(
            "artifact_limit_exceeded", f"{label} exceeds its byte limit"
        )
    return payload


def _load_npy(
    payload: bytes,
    *,
    name: str,
    dtype: np.dtype[Any],
    expected_shape: tuple[int, ...],
) -> np.ndarray:
    try:
        stream = BytesIO(payload)
        version = npy_format.read_magic(stream)
        if version == (1, 0):
            shape, fortran_order, header_dtype = npy_format.read_array_header_1_0(
                stream, max_header_size=MAX_NPY_HEADER_BYTES
            )
        elif version == (2, 0):
            shape, fortran_order, header_dtype = npy_format.read_array_header_2_0(
                stream, max_header_size=MAX_NPY_HEADER_BYTES
            )
        else:
            raise CollaborativeArtifactError(
                "artifact_format_invalid", f"Unsupported NPY version: {name}"
            )
        payload_start = stream.tell()
        expected_payload_bytes = math.prod(expected_shape) * dtype.itemsize
        if shape != expected_shape:
            raise CollaborativeArtifactError(
                "artifact_shape_invalid", f"Numeric member shape is invalid: {name}"
            )
        if header_dtype != dtype or header_dtype.hasobject:
            raise CollaborativeArtifactError(
                "artifact_dtype_invalid", f"Numeric member dtype is invalid: {name}"
            )
        if fortran_order or len(payload) - payload_start != expected_payload_bytes:
            raise CollaborativeArtifactError(
                "artifact_numeric_invalid", f"Numeric member payload is invalid: {name}"
            )
        stream.seek(0)
        loaded = np.load(
            stream,
            allow_pickle=False,
            max_header_size=MAX_NPY_HEADER_BYTES,
        )
    except CollaborativeArtifactError:
        raise
    except (EOFError, MemoryError, OSError, OverflowError, TypeError, ValueError) as error:
        raise CollaborativeArtifactError(
            "artifact_numeric_invalid", f"Numeric member is invalid: {name}"
        ) from error
    if loaded.dtype != dtype or loaded.shape != expected_shape or not loaded.flags.c_contiguous:
        raise CollaborativeArtifactError(
            "artifact_numeric_invalid", f"Numeric member contract is invalid: {name}"
        )
    immutable_payload = loaded.tobytes(order="C")
    immutable = np.frombuffer(immutable_payload, dtype=dtype).reshape(expected_shape)
    if immutable.flags.writeable:
        raise CollaborativeArtifactError(
            "artifact_numeric_invalid", f"Numeric member is unexpectedly mutable: {name}"
        )
    return immutable


def _validate_item_slugs(value: object, *, expected_count: int) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) != expected_count:
        raise CollaborativeArtifactError(
            "artifact_shape_invalid", "Collaborative item slug count is invalid"
        )
    if any(
        not isinstance(slug, str)
        or len(slug) > MAX_GAME_SLUG_LENGTH
        or SLUG_PATTERN.fullmatch(slug) is None
        for slug in value
    ):
        raise CollaborativeArtifactError("manifest_invalid", "Collaborative item slug is invalid")
    if value != sorted(set(value)):
        raise CollaborativeArtifactError(
            "artifact_format_invalid", "Collaborative item slugs are not canonical"
        )
    return tuple(value)


def _require_array(
    value: object,
    *,
    name: str,
    dtype: np.dtype[Any],
    shape: tuple[int, ...],
) -> np.ndarray:
    if not isinstance(value, np.ndarray) or value.dtype != dtype:
        raise CollaborativeArtifactError(
            "artifact_dtype_invalid", f"Collaborative array dtype is invalid: {name}"
        )
    if value.shape != shape:
        raise CollaborativeArtifactError(
            "artifact_shape_invalid", f"Collaborative array shape is invalid: {name}"
        )
    if not value.flags.c_contiguous:
        raise CollaborativeArtifactError(
            "artifact_format_invalid", f"Collaborative array must be C-contiguous: {name}"
        )
    return value


def _validate_count(value: object, *, label: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise CollaborativeArtifactError(
            "artifact_limit_exceeded", f"Collaborative {label} count is invalid"
        )
    return value


def _quantized_cosine(
    pair_support: np.ndarray,
    source_support: int,
    target_support: np.ndarray,
) -> np.ndarray:
    raw = pair_support.astype(np.float64) / np.sqrt(
        np.float64(source_support) * target_support.astype(np.float64)
    )
    try:
        return np.fromiter(
            (quantize_similarity(value) for value in raw),
            dtype=SIMILARITY_UNITS_DTYPE,
            count=len(raw),
        )
    except ValueError as error:
        raise CollaborativeArtifactError(
            "artifact_numeric_invalid", "Collaborative cosine could not be quantized"
        ) from error


def _validate_graph(
    *,
    item_slugs: tuple[str, ...],
    item_support: np.ndarray,
    neighbor_indices: np.ndarray,
    neighbor_indptr: np.ndarray,
    similarity_units: np.ndarray,
    pair_support: np.ndarray,
    retained_contributors: object,
    retained_positive_edges: object,
    pair_contributions: object,
) -> None:
    item_count = len(item_slugs)
    contributors = _validate_count(
        retained_contributors,
        label="retained contributor",
        minimum=MIN_ACTIVATION_USERS,
        maximum=MAX_PROFILES,
    )
    positive_edges = _validate_count(
        retained_positive_edges,
        label="retained positive edge",
        minimum=MIN_ACTIVATION_EDGES,
        maximum=MAX_POSITIVE_EDGES,
    )
    pair_contribution_count = _validate_count(
        pair_contributions,
        label="pair contribution",
        minimum=contributors,
        maximum=MAX_PAIR_CONTRIBUTIONS,
    )
    if not MIN_ACTIVATION_ITEMS <= item_count <= MAX_UNIQUE_ITEMS:
        raise CollaborativeArtifactError(
            "artifact_limit_exceeded", "Collaborative retained item count is invalid"
        )
    if positive_edges < contributors * MIN_PROFILE_ITEMS:
        raise CollaborativeArtifactError(
            "artifact_numeric_invalid", "Collaborative retained profile support is invalid"
        )
    maximum_pair_contributions = contributors * item_count * (item_count - 1) // 2
    if pair_contribution_count > maximum_pair_contributions:
        raise CollaborativeArtifactError(
            "artifact_numeric_invalid",
            "Collaborative pair contributions exceed their combinatorial bound",
        )

    item_support = _require_array(
        item_support,
        name=ITEM_SUPPORT_MEMBER,
        dtype=ITEM_SUPPORT_DTYPE,
        shape=(item_count,),
    )
    if (
        np.any(item_support < MIN_ITEM_SUPPORT)
        or np.any(item_support > contributors)
        or int(item_support.sum(dtype=np.int64)) != positive_edges
    ):
        raise CollaborativeArtifactError(
            "artifact_numeric_invalid", "Collaborative item support is invalid"
        )

    neighbor_indptr = _require_array(
        neighbor_indptr,
        name=NEIGHBOR_INDPTR_MEMBER,
        dtype=INDEX_DTYPE,
        shape=(item_count + 1,),
    )
    if neighbor_indptr[0] != 0 or np.any(neighbor_indptr[1:] < neighbor_indptr[:-1]):
        raise CollaborativeArtifactError(
            "artifact_format_invalid", "Collaborative neighbor indptr is invalid"
        )
    nonzero = int(neighbor_indptr[-1])
    if not 1 <= nonzero <= MAX_NEIGHBOR_NONZERO:
        raise CollaborativeArtifactError(
            "artifact_limit_exceeded", "Collaborative neighbor count is invalid"
        )
    neighbor_indices = _require_array(
        neighbor_indices,
        name=NEIGHBOR_INDICES_MEMBER,
        dtype=INDEX_DTYPE,
        shape=(nonzero,),
    )
    similarity_units = _require_array(
        similarity_units,
        name=SIMILARITY_UNITS_MEMBER,
        dtype=SIMILARITY_UNITS_DTYPE,
        shape=(nonzero,),
    )
    pair_support = _require_array(
        pair_support,
        name=PAIR_SUPPORT_MEMBER,
        dtype=PAIR_SUPPORT_DTYPE,
        shape=(nonzero,),
    )
    if (
        np.any(neighbor_indices < 0)
        or np.any(neighbor_indices >= item_count)
        or np.any(similarity_units <= 0)
        or np.any(similarity_units > SCORE_SCALE)
        or np.any(pair_support < MIN_PAIR_SUPPORT)
        or np.any(pair_support > contributors)
    ):
        raise CollaborativeArtifactError(
            "artifact_numeric_invalid", "Collaborative neighbor values are invalid"
        )

    retained_pair_support = 0
    for source_index in range(item_count):
        start = int(neighbor_indptr[source_index])
        end = int(neighbor_indptr[source_index + 1])
        row_count = end - start
        if row_count > MAX_NEIGHBORS_PER_ITEM:
            raise CollaborativeArtifactError(
                "artifact_limit_exceeded", "Collaborative neighbor row exceeds its cap"
            )
        row_indices = neighbor_indices[start:end]
        if row_count > 1 and np.any(row_indices[1:] <= row_indices[:-1]):
            raise CollaborativeArtifactError(
                "artifact_format_invalid",
                "Collaborative neighbor indices are not canonical",
            )
        if np.any(row_indices == source_index):
            raise CollaborativeArtifactError(
                "artifact_format_invalid", "Collaborative self-neighbor is forbidden"
            )
        row_pair_support = pair_support[start:end]
        target_support = item_support[row_indices]
        if np.any(row_pair_support > np.minimum(item_support[source_index], target_support)):
            raise CollaborativeArtifactError(
                "artifact_numeric_invalid", "Pair support exceeds endpoint support"
            )
        expected_similarity = _quantized_cosine(
            row_pair_support,
            int(item_support[source_index]),
            target_support,
        )
        if not np.array_equal(similarity_units[start:end], expected_similarity):
            raise CollaborativeArtifactError(
                "artifact_numeric_invalid", "Stored collaborative cosine is inconsistent"
            )
        for relative_offset, target_value in enumerate(row_indices):
            target_index = int(target_value)
            if target_index <= source_index:
                continue
            reverse_start = int(neighbor_indptr[target_index])
            reverse_end = int(neighbor_indptr[target_index + 1])
            reverse_indices = neighbor_indices[reverse_start:reverse_end]
            reverse_position = int(np.searchsorted(reverse_indices, source_index))
            if (
                reverse_position >= len(reverse_indices)
                or int(reverse_indices[reverse_position]) != source_index
            ):
                continue
            offset = start + relative_offset
            reverse_offset = reverse_start + reverse_position
            if (
                pair_support[offset] != pair_support[reverse_offset]
                or similarity_units[offset] != similarity_units[reverse_offset]
            ):
                raise CollaborativeArtifactError(
                    "artifact_numeric_invalid",
                    "Mutual collaborative neighbors are inconsistent",
                )
        retained_pair_support += int(row_pair_support.sum(dtype=np.int64))
    if retained_pair_support > 2 * pair_contribution_count:
        raise CollaborativeArtifactError(
            "artifact_numeric_invalid", "Retained pair support exceeds pair contributions"
        )


def _metadata_manifest_values(metadata: CollaborativeBuildMetadata) -> dict[str, object]:
    fixture = metadata.source_kind == "fixture"
    return {
        "build": {
            "id": metadata.build_id,
            "built_at": _format_timestamp(metadata.built_at, label="Build timestamp"),
            "software": _expected_software(),
        },
        "source": {
            "kind": metadata.source_kind,
            "fixture_id": metadata.fixture_id,
            "contains_real_user_data": not fixture,
            "quality_evidence": False,
        },
        "lifecycle": {
            "cutoff": (
                None
                if metadata.cutoff is None
                else _format_timestamp(metadata.cutoff, label="Cutoff")
            ),
            "consent_version": metadata.consent_version,
            "data_revision": metadata.data_revision,
            "valid_until": (
                None
                if metadata.valid_until is None
                else _format_timestamp(metadata.valid_until, label="Validity horizon")
            ),
        },
    }


def _manifest_for(
    neighborhoods: CollaborativeNeighborhoods,
    *,
    metadata: CollaborativeBuildMetadata,
    members: dict[str, dict[str, object]],
) -> dict[str, object]:
    metadata_values = _metadata_manifest_values(metadata)
    item_count = len(neighborhoods.item_slugs)
    nonzero = len(neighborhoods.neighbor_indices)
    return {
        "artifact_schema_version": COLLABORATIVE_ARTIFACT_SCHEMA_VERSION,
        "model": {
            "name": COLLABORATIVE_MODEL_NAME,
            "version": COLLABORATIVE_MODEL_VERSION,
        },
        "code_compatibility": COLLABORATIVE_CODE_COMPATIBILITY,
        "build": metadata_values["build"],
        "source": metadata_values["source"],
        "catalog_fingerprint": metadata.catalog_fingerprint,
        "interaction_fingerprint": metadata.interaction_fingerprint,
        "label_policy": LABEL_POLICY_ID,
        "lifecycle": metadata_values["lifecycle"],
        "thresholds": _expected_thresholds(),
        "numeric": _expected_numeric(),
        "matrix": {
            "retained_contributors": neighborhoods.retained_contributors,
            "retained_items": item_count,
            "retained_positive_edges": neighborhoods.retained_positive_edges,
            "pair_contributions": neighborhoods.pair_contributions,
        },
        "neighbors": {
            "shape": [item_count, item_count],
            "nonzero": nonzero,
            "format": "csr-transparent-npy",
            "maximum_per_item": MAX_NEIGHBORS_PER_ITEM,
        },
        "limits": _expected_limits(),
        "members": members,
    }


def _write_bytes(path: Path, value: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def _save_array(path: Path, value: np.ndarray) -> None:
    with path.open("xb") as stream:
        np.save(stream, value, allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _artifact_target(output_path: str | Path) -> tuple[Path, Path]:
    raw_target = Path(output_path).expanduser()
    if raw_target.name in {"", ".", ".."}:
        raise CollaborativeArtifactError(
            "artifact_path_invalid", "Collaborative artifact target is unsafe"
        )
    try:
        raw_target.parent.mkdir(parents=True, exist_ok=True)
        parent = raw_target.parent.resolve(strict=True)
    except OSError as error:
        raise CollaborativeArtifactError(
            "artifact_promotion_failed", "Collaborative artifact parent is unavailable"
        ) from error
    target = parent / raw_target.name
    lock = parent / f".{raw_target.name}.promotion.lock"
    return target, lock


def _acquire_promotion_lock(path: Path) -> int:
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(descriptor, b"collaborative-artifact-promotion\n")
        os.fsync(descriptor)
        return descriptor
    except FileExistsError as error:
        raise CollaborativeArtifactError(
            "artifact_target_exists", "Collaborative artifact promotion is already locked"
        ) from error
    except OSError as error:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
            with suppress(OSError):
                path.unlink(missing_ok=True)
        raise CollaborativeArtifactError(
            "artifact_promotion_failed", "Collaborative artifact lock could not be created"
        ) from error


def _rename_directory_no_replace(source: Path, target: Path) -> None:
    """Atomically publish a directory without ever replacing an existing path."""

    if os.name == "nt":
        try:
            os.rename(source, target)
        except FileExistsError as error:
            raise CollaborativeArtifactError(
                "artifact_target_exists", "Collaborative artifact target already exists"
            ) from error
        return

    if sys.platform.startswith("linux"):
        try:
            renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
        except (AttributeError, OSError) as error:
            raise CollaborativeArtifactError(
                "artifact_promotion_failed",
                "Atomic no-replace promotion is unavailable on this platform",
            ) from error
        renameat2.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        renameat2.restype = ctypes.c_int
        ctypes.set_errno(0)
        result = renameat2(
            -100,  # AT_FDCWD
            os.fsencode(source),
            -100,
            os.fsencode(target),
            1,  # RENAME_NOREPLACE
        )
        if result == 0:
            return
        error_number = ctypes.get_errno()
        if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
            raise CollaborativeArtifactError(
                "artifact_target_exists", "Collaborative artifact target already exists"
            )
        raise CollaborativeArtifactError(
            "artifact_promotion_failed", "Atomic collaborative artifact promotion failed"
        ) from OSError(error_number, os.strerror(error_number))

    raise CollaborativeArtifactError(
        "artifact_promotion_failed",
        "Atomic no-replace promotion is unavailable on this platform",
    )


def build_collaborative_artifact(
    neighborhoods: CollaborativeNeighborhoods,
    output_path: str | Path,
    *,
    metadata: CollaborativeBuildMetadata,
    allow_fixture: bool = False,
    revision_check: Callable[[int], bool | None] | None = None,
) -> Path:
    _validate_build_metadata(metadata, allow_fixture=allow_fixture)
    if metadata.source_kind == "live" and revision_check is None:
        raise CollaborativeArtifactError(
            "revision_race", "Live artifact promotion requires a revision recheck"
        )
    try:
        item_slugs = tuple(neighborhoods.item_slugs)
        item_support = neighborhoods.item_support
        neighbor_indices = neighborhoods.neighbor_indices
        neighbor_indptr = neighborhoods.neighbor_indptr
        similarity_units = neighborhoods.similarity_units
        pair_support = neighborhoods.pair_support
        retained_contributors = neighborhoods.retained_contributors
        retained_positive_edges = neighborhoods.retained_positive_edges
        pair_contributions = neighborhoods.pair_contributions
    except (AttributeError, TypeError) as error:
        raise CollaborativeArtifactError(
            "artifact_format_invalid", "Collaborative neighborhoods are invalid"
        ) from error
    _validate_item_slugs(list(item_slugs), expected_count=len(item_slugs))
    _validate_graph(
        item_slugs=item_slugs,
        item_support=item_support,
        neighbor_indices=neighbor_indices,
        neighbor_indptr=neighbor_indptr,
        similarity_units=similarity_units,
        pair_support=pair_support,
        retained_contributors=retained_contributors,
        retained_positive_edges=retained_positive_edges,
        pair_contributions=pair_contributions,
    )

    target, lock_path = _artifact_target(output_path)
    if target.exists() or target.is_symlink():
        raise CollaborativeArtifactError(
            "artifact_target_exists", "Collaborative artifact target already exists"
        )
    lock_descriptor = _acquire_promotion_lock(lock_path)
    temporary: Path | None = None
    try:
        if target.exists() or target.is_symlink():
            raise CollaborativeArtifactError(
                "artifact_target_exists", "Collaborative artifact target already exists"
            )
        temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
        _write_bytes(temporary / ITEM_SLUGS_MEMBER, _canonical_json_bytes(list(item_slugs)))
        _save_array(temporary / ITEM_SUPPORT_MEMBER, item_support)
        _save_array(temporary / NEIGHBOR_INDICES_MEMBER, neighbor_indices)
        _save_array(temporary / NEIGHBOR_INDPTR_MEMBER, neighbor_indptr)
        _save_array(temporary / SIMILARITY_UNITS_MEMBER, similarity_units)
        _save_array(temporary / PAIR_SUPPORT_MEMBER, pair_support)
        members: dict[str, dict[str, object]] = {}
        total_size = 0
        for name in REQUIRED_MEMBERS:
            member_path = temporary / name
            size = member_path.stat().st_size
            if not 1 <= size <= MAX_MEMBER_BYTES:
                raise CollaborativeArtifactError(
                    "artifact_limit_exceeded", f"Artifact member exceeds its limit: {name}"
                )
            total_size += size
            members[name] = {"size": size, "sha256": _sha256_file(member_path)}
        manifest = _manifest_for(neighborhoods, metadata=metadata, members=members)
        manifest_bytes = _canonical_json_bytes(manifest)
        if (
            len(manifest_bytes) > MAX_MANIFEST_BYTES
            or total_size + len(manifest_bytes) > MAX_TOTAL_BYTES
        ):
            raise CollaborativeArtifactError(
                "artifact_limit_exceeded", "Collaborative artifact exceeds its byte limit"
            )
        _write_bytes(temporary / "manifest.json", manifest_bytes)
        _fsync_directory(temporary)

        load_collaborative_artifact(
            temporary,
            allow_fixture=allow_fixture,
            expected_catalog_fingerprint=metadata.catalog_fingerprint,
            expected_data_revision=metadata.data_revision,
            expected_consent_version=metadata.consent_version,
        )
        if metadata.source_kind == "live":
            assert metadata.data_revision is not None
            try:
                current = revision_check(metadata.data_revision) if revision_check else False
            except CollaborativeArtifactError:
                raise
            except Exception as error:
                raise CollaborativeArtifactError(
                    "revision_race", "Live data revision recheck failed"
                ) from error
            if current is not None and current is not True:
                raise CollaborativeArtifactError(
                    "revision_race", "Live data revision changed before promotion"
                )
        if target.exists() or target.is_symlink():
            raise CollaborativeArtifactError(
                "artifact_target_exists", "Collaborative artifact target already exists"
            )
        _rename_directory_no_replace(temporary, target)
        temporary = None
        _fsync_directory(target.parent)
        return target
    except CollaborativeArtifactError:
        raise
    except OSError as error:
        raise CollaborativeArtifactError(
            "artifact_promotion_failed", "Collaborative artifact promotion failed"
        ) from error
    finally:
        with suppress(OSError):
            os.close(lock_descriptor)
        if temporary is not None:
            shutil.rmtree(temporary, ignore_errors=True)
        with suppress(OSError):
            lock_path.unlink(missing_ok=True)
        _fsync_directory(target.parent)


def load_collaborative_artifact(
    path: str | Path,
    *,
    allow_fixture: bool = False,
    expected_catalog_fingerprint: str | None = None,
    expected_data_revision: int | None = None,
    expected_consent_version: str | None = None,
    now: datetime | None = None,
) -> LoadedCollaborativeArtifact:
    if type(allow_fixture) is not bool:
        raise CollaborativeArtifactError("manifest_invalid", "Fixture permission must be a boolean")
    root = _resolved_artifact_root(path)
    paths = _validated_directory_entries(root)
    manifest_bytes = _read_bounded(
        paths["manifest.json"], maximum=MAX_MANIFEST_BYTES, label="Artifact manifest"
    )
    manifest, metadata = _validate_manifest(
        _load_strict_json(manifest_bytes, name="manifest.json"),
        manifest_size=len(manifest_bytes),
        allow_fixture=allow_fixture,
    )

    if expected_catalog_fingerprint is not None:
        if not _is_sha256(expected_catalog_fingerprint):
            raise CollaborativeArtifactError(
                "catalog_mismatch", "Expected catalog fingerprint is invalid"
            )
        if metadata.catalog_fingerprint != expected_catalog_fingerprint:
            raise CollaborativeArtifactError(
                "catalog_mismatch", "Collaborative artifact catalog does not match"
            )
    if expected_data_revision is not None:
        if type(expected_data_revision) is not int or expected_data_revision < 0:
            raise CollaborativeArtifactError(
                "artifact_stale_revision", "Expected data revision is invalid"
            )
        if metadata.data_revision != expected_data_revision:
            raise CollaborativeArtifactError(
                "artifact_stale_revision", "Collaborative artifact data revision is stale"
            )
    if expected_consent_version is not None:
        if (
            not isinstance(expected_consent_version, str)
            or expected_consent_version != expected_consent_version.strip()
            or not expected_consent_version
        ):
            raise CollaborativeArtifactError(
                "consent_policy_incompatible", "Expected consent version is invalid"
            )
        if metadata.consent_version != expected_consent_version:
            raise CollaborativeArtifactError(
                "consent_policy_incompatible", "Collaborative consent policy is incompatible"
            )
    if metadata.valid_until is not None:
        current_time = datetime.now(UTC) if now is None else now
        if (
            not isinstance(current_time, datetime)
            or current_time.tzinfo is None
            or current_time.utcoffset() is None
        ):
            raise CollaborativeArtifactError(
                "manifest_invalid", "Lifecycle validation time must be timezone-aware"
            )
        if current_time.astimezone(UTC) >= metadata.valid_until.astimezone(UTC):
            raise CollaborativeArtifactError(
                "artifact_expired", "Collaborative artifact validity horizon has expired"
            )

    member_payloads: dict[str, bytes] = {}
    declared_members = manifest["members"]
    for name in REQUIRED_MEMBERS:
        declared = declared_members[name]
        payload = _read_bounded(paths[name], maximum=MAX_MEMBER_BYTES, label=name)
        if len(payload) != declared["size"]:
            raise CollaborativeArtifactError(
                "artifact_integrity_failed", f"Artifact member size mismatch: {name}"
            )
        if hashlib.sha256(payload).hexdigest() != declared["sha256"]:
            raise CollaborativeArtifactError(
                "artifact_integrity_failed", f"Artifact member checksum mismatch: {name}"
            )
        member_payloads[name] = payload

    matrix = manifest["matrix"]
    neighbors = manifest["neighbors"]
    item_count = matrix["retained_items"]
    nonzero = neighbors["nonzero"]
    item_slugs = _validate_item_slugs(
        _load_strict_json(member_payloads[ITEM_SLUGS_MEMBER], name=ITEM_SLUGS_MEMBER),
        expected_count=item_count,
    )
    item_support = _load_npy(
        member_payloads[ITEM_SUPPORT_MEMBER],
        name=ITEM_SUPPORT_MEMBER,
        dtype=ITEM_SUPPORT_DTYPE,
        expected_shape=(item_count,),
    )
    neighbor_indices = _load_npy(
        member_payloads[NEIGHBOR_INDICES_MEMBER],
        name=NEIGHBOR_INDICES_MEMBER,
        dtype=INDEX_DTYPE,
        expected_shape=(nonzero,),
    )
    neighbor_indptr = _load_npy(
        member_payloads[NEIGHBOR_INDPTR_MEMBER],
        name=NEIGHBOR_INDPTR_MEMBER,
        dtype=INDEX_DTYPE,
        expected_shape=(item_count + 1,),
    )
    similarity_units = _load_npy(
        member_payloads[SIMILARITY_UNITS_MEMBER],
        name=SIMILARITY_UNITS_MEMBER,
        dtype=SIMILARITY_UNITS_DTYPE,
        expected_shape=(nonzero,),
    )
    pair_support = _load_npy(
        member_payloads[PAIR_SUPPORT_MEMBER],
        name=PAIR_SUPPORT_MEMBER,
        dtype=PAIR_SUPPORT_DTYPE,
        expected_shape=(nonzero,),
    )
    _validate_graph(
        item_slugs=item_slugs,
        item_support=item_support,
        neighbor_indices=neighbor_indices,
        neighbor_indptr=neighbor_indptr,
        similarity_units=similarity_units,
        pair_support=pair_support,
        retained_contributors=matrix["retained_contributors"],
        retained_positive_edges=matrix["retained_positive_edges"],
        pair_contributions=matrix["pair_contributions"],
    )
    if nonzero != len(neighbor_indices):
        raise CollaborativeArtifactError(
            "artifact_shape_invalid", "Collaborative neighbor count is inconsistent"
        )
    return LoadedCollaborativeArtifact(
        root=root,
        manifest=_freeze(manifest),
        item_slugs=item_slugs,
        item_support=item_support,
        neighbor_indices=neighbor_indices,
        neighbor_indptr=neighbor_indptr,
        similarity_units=similarity_units,
        pair_support=pair_support,
        slug_to_index=MappingProxyType({slug: index for index, slug in enumerate(item_slugs)}),
    )


def _neighbor_count_distribution(counts: np.ndarray) -> dict[str, int]:
    result = {
        "0": 0,
        "1": 0,
        "2": 0,
        "3-4": 0,
        "5-9": 0,
        "10-24": 0,
        "25-49": 0,
        "50-99": 0,
        "100": 0,
    }
    for count_value in counts:
        count = int(count_value)
        if count == 0:
            result["0"] += 1
        elif count == 1:
            result["1"] += 1
        elif count == 2:
            result["2"] += 1
        elif count <= 4:
            result["3-4"] += 1
        elif count <= 9:
            result["5-9"] += 1
        elif count <= 24:
            result["10-24"] += 1
        elif count <= 49:
            result["25-49"] += 1
        elif count <= 99:
            result["50-99"] += 1
        else:
            result["100"] += 1
    return result


def inspect_collaborative_artifact(
    path: str | Path,
    *,
    allow_fixture: bool = False,
    expected_catalog_fingerprint: str | None = None,
    expected_data_revision: int | None = None,
    expected_consent_version: str | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    artifact = load_collaborative_artifact(
        path,
        allow_fixture=allow_fixture,
        expected_catalog_fingerprint=expected_catalog_fingerprint,
        expected_data_revision=expected_data_revision,
        expected_consent_version=expected_consent_version,
        now=now,
    )
    matrix = artifact.manifest["matrix"]
    neighbors = artifact.manifest["neighbors"]
    row_counts = np.diff(artifact.neighbor_indptr.astype(np.int64, copy=False))
    return {
        "status": "valid",
        "artifact_schema_version": artifact.manifest["artifact_schema_version"],
        "model": {
            "name": artifact.model_name,
            "version": artifact.model_version,
        },
        "code_compatibility": artifact.manifest["code_compatibility"],
        "build": {
            "id": artifact.build_id,
            "built_at": artifact.manifest["build"]["built_at"],
        },
        "source": {
            "kind": artifact.manifest["source"]["kind"],
            "fixture_id": artifact.manifest["source"]["fixture_id"],
            "quality_evidence": False,
        },
        "catalog_fingerprint": artifact.catalog_fingerprint,
        "interaction_fingerprint": artifact.interaction_fingerprint,
        "label_policy": artifact.manifest["label_policy"],
        "lifecycle": dict(artifact.manifest["lifecycle"]),
        "matrix": dict(matrix),
        "neighbors": {
            "shape": list(neighbors["shape"]),
            "nonzero": neighbors["nonzero"],
            "minimum_per_item": int(row_counts.min()),
            "maximum_per_item": int(row_counts.max()),
            "count_distribution": _neighbor_count_distribution(row_counts),
        },
        "item_support": {
            "minimum": int(artifact.item_support.min()),
            "maximum": int(artifact.item_support.max()),
            "total": int(artifact.item_support.sum(dtype=np.int64)),
        },
        "thresholds": dict(artifact.manifest["thresholds"]),
        "numeric": dict(artifact.manifest["numeric"]),
        "limits": dict(artifact.manifest["limits"]),
    }
