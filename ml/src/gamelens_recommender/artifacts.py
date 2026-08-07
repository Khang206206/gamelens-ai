from __future__ import annotations

import hashlib
import json
import math
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any

import numpy as np
import scipy
import sklearn
from numpy.lib import format as npy_format
from scipy import sparse

from gamelens_recommender.config import (
    ARTIFACT_LIMITS,
    ARTIFACT_SCHEMA_VERSION,
    CODE_COMPATIBILITY,
    FEATURE_CONFIG,
    MODEL_NAME,
    MODEL_VERSION,
    POPULARITY_CONFIG,
    RANKING_CONFIG,
)
from gamelens_recommender.features import restore_vectorizer
from gamelens_recommender.schemas import CatalogItem, canonical_snapshot

REQUIRED_MEMBERS = (
    "catalog-items.json",
    "vectorizer-config.json",
    "vocabulary.json",
    "inverse-document-frequency.npy",
    "matrix-data.npy",
    "matrix-indices.npy",
    "matrix-indptr.npy",
    "popularity.npy",
)
MATRIX_NORM_RTOL = 1e-9
MATRIX_NORM_ATOL = 1e-12


class ArtifactError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class LoadedArtifact:
    root: Path
    manifest: Mapping[str, Any]
    items: tuple[CatalogItem, ...]
    matrix: sparse.csr_matrix
    popularity: np.ndarray
    vectorizer: object
    slug_to_row: Mapping[str, int]

    @property
    def data_fingerprint(self) -> str:
        return str(self.manifest["data_fingerprint"])

    @property
    def model_name(self) -> str:
        return str(self.manifest["model"]["name"])

    @property
    def model_version(self) -> str:
        return str(self.manifest["model"]["version"])


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ArtifactError("manifest_invalid", f"Invalid JSON member: {path.name}") from error


def _safe_member(root: Path, name: str) -> Path:
    pure = PurePosixPath(name)
    if pure.is_absolute() or len(pure.parts) != 1 or pure.name in {"", ".", ".."}:
        raise ArtifactError("artifact_path_invalid", "Artifact member path is unsafe")
    path = (root / pure.name).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ArtifactError("artifact_path_invalid", "Artifact member escapes its root") from error
    return path


def _validate_manifest(root: Path, value: object, *, manifest_size: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ArtifactError("manifest_invalid", "Artifact manifest must be an object")
    manifest: dict[str, Any] = value
    if manifest.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise ArtifactError("artifact_schema_incompatible", "Artifact schema is incompatible")
    model = manifest.get("model")
    compatibility = manifest.get("compatibility")
    if not isinstance(model, dict) or model != {"name": MODEL_NAME, "version": MODEL_VERSION}:
        raise ArtifactError("model_incompatible", "Artifact model identity is incompatible")
    expected_compatibility = {
        "code": CODE_COMPATIBILITY,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "scikit_learn": sklearn.__version__,
    }
    if compatibility != expected_compatibility:
        raise ArtifactError("code_incompatible", "Artifact code compatibility is invalid")
    expected_config = {
        "feature_config": FEATURE_CONFIG.to_dict(),
        "popularity_config": POPULARITY_CONFIG.to_dict(),
        "ranking_config": RANKING_CONFIG.to_dict(),
        "limits": ARTIFACT_LIMITS.to_dict(),
    }
    if any(manifest.get(name) != expected for name, expected in expected_config.items()):
        raise ArtifactError("config_incompatible", "Artifact configuration is incompatible")
    built_at = manifest.get("built_at")
    if not isinstance(built_at, str) or not built_at.endswith("Z"):
        raise ArtifactError("manifest_invalid", "Artifact build timestamp is invalid")
    try:
        datetime.fromisoformat(f"{built_at[:-1]}+00:00")
    except ValueError as error:
        raise ArtifactError("manifest_invalid", "Artifact build timestamp is invalid") from error
    if manifest.get("random_seed", object()) is not None:
        raise ArtifactError("config_incompatible", "Artifact random seed is incompatible")
    members = manifest.get("members")
    if not isinstance(members, dict) or set(members) != set(REQUIRED_MEMBERS):
        raise ArtifactError("manifest_invalid", "Artifact member set is incomplete")
    if len(members) > ARTIFACT_LIMITS.max_members:
        raise ArtifactError("artifact_limit_exceeded", "Artifact has too many members")
    total = manifest_size
    for name, metadata in members.items():
        path = _safe_member(root, name)
        if not isinstance(metadata, dict) or not path.is_file():
            raise ArtifactError("artifact_missing", "Artifact member is missing")
        size = metadata.get("size")
        checksum = metadata.get("sha256")
        if type(size) is not int or not 0 <= size <= ARTIFACT_LIMITS.max_member_bytes:
            raise ArtifactError("artifact_limit_exceeded", "Artifact member size is invalid")
        total += size
        if path.stat().st_size != size or not isinstance(checksum, str):
            raise ArtifactError("artifact_integrity_failed", "Artifact member size mismatch")
        if sha256_file(path) != checksum:
            raise ArtifactError("artifact_integrity_failed", "Artifact checksum mismatch")
    if total > ARTIFACT_LIMITS.max_total_bytes:
        raise ArtifactError("artifact_limit_exceeded", "Artifact bundle is too large")
    item_count = manifest.get("item_count")
    vocabulary_size = manifest.get("vocabulary_size")
    matrix = manifest.get("matrix")
    if type(item_count) is not int or not 1 <= item_count <= ARTIFACT_LIMITS.max_items:
        raise ArtifactError("artifact_limit_exceeded", "Artifact item count is invalid")
    if (
        type(vocabulary_size) is not int
        or not 1 <= vocabulary_size <= ARTIFACT_LIMITS.max_vocabulary
    ):
        raise ArtifactError("artifact_limit_exceeded", "Artifact vocabulary size is invalid")
    if not isinstance(matrix, dict) or matrix.get("shape") != [item_count, vocabulary_size]:
        raise ArtifactError("artifact_shape_invalid", "Artifact matrix shape is invalid")
    nonzero = matrix.get("nonzero")
    if type(nonzero) is not int or not 1 <= nonzero <= ARTIFACT_LIMITS.max_matrix_nonzero:
        raise ArtifactError("artifact_limit_exceeded", "Artifact matrix size is invalid")
    if matrix.get("dtype") != "float64":
        raise ArtifactError("artifact_dtype_invalid", "Artifact matrix dtype is invalid")
    if matrix.get("format") != "csr-transparent-npy":
        raise ArtifactError("artifact_format_invalid", "Artifact matrix format is invalid")
    return manifest


def _load_numeric(
    root: Path,
    name: str,
    dtype: str,
    expected_shape: tuple[int, ...],
) -> np.ndarray:
    path = _safe_member(root, name)
    try:
        with path.open("rb") as stream:
            version = npy_format.read_magic(stream)
            if version == (1, 0):
                shape, fortran_order, header_dtype = npy_format.read_array_header_1_0(stream)
            elif version == (2, 0):
                shape, fortran_order, header_dtype = npy_format.read_array_header_2_0(stream)
            else:
                raise ValueError("Unsupported NPY format version")
            payload_start = stream.tell()
            stream.seek(0, 2)
            file_size = stream.tell()
            expected_payload_bytes = math.prod(expected_shape) * np.dtype(dtype).itemsize
            if shape != expected_shape:
                raise ArtifactError("artifact_shape_invalid", f"Invalid numeric shape: {name}")
            if header_dtype != np.dtype(dtype) or header_dtype.hasobject:
                raise ArtifactError("artifact_dtype_invalid", f"Invalid numeric dtype: {name}")
            if fortran_order or file_size - payload_start != expected_payload_bytes:
                raise ArtifactError("artifact_numeric_invalid", f"Invalid numeric payload: {name}")
            stream.seek(0)
            array = np.load(stream, allow_pickle=False)
    except ArtifactError:
        raise
    except (EOFError, OSError, ValueError) as error:
        raise ArtifactError(
            "artifact_numeric_invalid", f"Invalid numeric member: {name}"
        ) from error
    if array.dtype != np.dtype(dtype) or array.dtype.hasobject:
        raise ArtifactError("artifact_dtype_invalid", f"Invalid numeric dtype: {name}")
    if np.issubdtype(array.dtype, np.floating) and not np.isfinite(array).all():
        raise ArtifactError("artifact_numeric_invalid", f"Non-finite numeric member: {name}")
    return array


def load_artifact(path: str | Path) -> LoadedArtifact:
    root = Path(path).expanduser().resolve()
    manifest_path = root / "manifest.json"
    if not root.is_dir() or not manifest_path.is_file():
        raise ArtifactError("artifact_missing", "Configured artifact directory is missing")
    if manifest_path.stat().st_size > ARTIFACT_LIMITS.max_member_bytes:
        raise ArtifactError("artifact_limit_exceeded", "Artifact manifest is too large")
    manifest = _validate_manifest(
        root,
        _read_json(manifest_path),
        manifest_size=manifest_path.stat().st_size,
    )
    raw_items = _read_json(_safe_member(root, "catalog-items.json"))
    raw_vocabulary = _read_json(_safe_member(root, "vocabulary.json"))
    raw_config = _read_json(_safe_member(root, "vectorizer-config.json"))
    if not isinstance(raw_items, list) or not isinstance(raw_vocabulary, dict):
        raise ArtifactError("manifest_invalid", "Artifact metadata shape is invalid")
    if len(raw_items) != manifest["item_count"]:
        raise ArtifactError("artifact_shape_invalid", "Artifact catalog size is invalid")
    if len(raw_vocabulary) != manifest["vocabulary_size"]:
        raise ArtifactError("artifact_shape_invalid", "Artifact vocabulary size is invalid")
    if raw_config != FEATURE_CONFIG.to_dict():
        raise ArtifactError("feature_config_incompatible", "Feature configuration is incompatible")
    try:
        items = tuple(CatalogItem.from_dict(item) for item in raw_items)
        snapshot = canonical_snapshot(items)
        if not all(type(index) is int for index in raw_vocabulary.values()):
            raise ValueError("Vocabulary indices must be integers")
        vocabulary = dict(raw_vocabulary)
    except (KeyError, TypeError, ValueError) as error:
        raise ArtifactError("manifest_invalid", "Artifact catalog metadata is invalid") from error
    if (
        len(items) != manifest["item_count"]
        or items != snapshot.items
        or raw_items != [item.to_dict() for item in items]
        or snapshot.fingerprint != manifest["data_fingerprint"]
        or manifest.get("row_slugs") != [item.slug for item in snapshot.items]
    ):
        raise ArtifactError("artifact_integrity_failed", "Artifact catalog fingerprint mismatch")
    if sorted(vocabulary.values()) != list(range(len(vocabulary))):
        raise ArtifactError("artifact_shape_invalid", "Artifact vocabulary mapping is invalid")
    expected_shape = tuple(manifest["matrix"]["shape"])
    nonzero = manifest["matrix"]["nonzero"]
    idf = _load_numeric(
        root,
        "inverse-document-frequency.npy",
        "float64",
        (len(vocabulary),),
    )
    data = _load_numeric(root, "matrix-data.npy", "float64", (nonzero,))
    indices = _load_numeric(root, "matrix-indices.npy", "int32", (nonzero,))
    indptr = _load_numeric(root, "matrix-indptr.npy", "int32", (len(items) + 1,))
    popularity = _load_numeric(root, "popularity.npy", "float64", (len(items),))
    try:
        matrix = sparse.csr_matrix((data, indices, indptr), shape=expected_shape)
        matrix.check_format(full_check=True)
    except (ValueError, TypeError) as error:
        raise ArtifactError(
            "artifact_shape_invalid", "Artifact sparse matrix is invalid"
        ) from error
    if matrix.nnz != manifest["matrix"]["nonzero"]:
        raise ArtifactError("artifact_shape_invalid", "Artifact sparse matrix mismatch")
    if not matrix.has_canonical_format:
        raise ArtifactError(
            "artifact_format_invalid",
            "Artifact sparse matrix indices are not canonical",
        )
    if np.any(matrix.data < 0):
        raise ArtifactError("artifact_numeric_invalid", "Artifact feature weights are invalid")
    row_norms = np.sqrt(matrix.multiply(matrix).sum(axis=1)).A1
    if (
        not np.isfinite(row_norms).all()
        or np.any(row_norms <= 0)
        or not np.allclose(
            row_norms,
            1.0,
            rtol=MATRIX_NORM_RTOL,
            atol=MATRIX_NORM_ATOL,
        )
    ):
        raise ArtifactError(
            "artifact_numeric_invalid",
            "Artifact feature rows are not L2-normalized",
        )
    if np.any(popularity < 0) or np.any(popularity > 1):
        raise ArtifactError("artifact_numeric_invalid", "Artifact popularity is invalid")
    if np.any(idf < 1):
        raise ArtifactError("artifact_numeric_invalid", "Artifact IDF weights are invalid")
    for array in (matrix.data, matrix.indices, matrix.indptr, popularity, idf):
        array.flags.writeable = False
    vectorizer = restore_vectorizer(MappingProxyType(vocabulary), idf)
    return LoadedArtifact(
        root=root,
        manifest=_freeze(manifest),
        items=items,
        matrix=matrix,
        popularity=popularity,
        vectorizer=vectorizer,
        slug_to_row=MappingProxyType({item.slug: index for index, item in enumerate(items)}),
    )
