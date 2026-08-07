from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import scipy
import sklearn

from gamelens_recommender.artifacts import (
    REQUIRED_MEMBERS,
    canonical_json_bytes,
    load_artifact,
    sha256_file,
)
from gamelens_recommender.baseline import popularity_baseline
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
from gamelens_recommender.features import fit_features
from gamelens_recommender.schemas import CatalogSnapshot, canonical_snapshot


def _write_bytes(path: Path, value: bytes) -> None:
    with path.open("wb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def _save_array(path: Path, value: np.ndarray) -> None:
    with path.open("wb") as stream:
        np.save(stream, value, allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())


def build_artifact(
    snapshot: CatalogSnapshot,
    output_path: str | Path,
    *,
    built_at: datetime | None = None,
) -> Path:
    RANKING_CONFIG.validate()
    if len(snapshot.items) > ARTIFACT_LIMITS.max_items:
        raise ValueError("Catalog exceeds artifact item limit")
    canonical = canonical_snapshot(snapshot.items)
    if snapshot.fingerprint != canonical.fingerprint:
        raise ValueError("Catalog snapshot fingerprint does not match its canonical items")
    snapshot = canonical
    target = Path(output_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"Artifact target already exists: {target.name}")
    timestamp = built_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("Artifact build timestamp must be timezone-aware")
    vectorizer, matrix = fit_features(snapshot.items)
    popularity = popularity_baseline(snapshot.items)
    if len(vectorizer.vocabulary_) > ARTIFACT_LIMITS.max_vocabulary:
        raise ValueError("Vocabulary exceeds artifact limit")
    if matrix.nnz > ARTIFACT_LIMITS.max_matrix_nonzero:
        raise ValueError("Sparse matrix exceeds artifact limit")
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent))
    try:
        _write_bytes(
            temporary / "catalog-items.json",
            canonical_json_bytes([item.to_dict() for item in snapshot.items]),
        )
        _write_bytes(
            temporary / "vectorizer-config.json",
            canonical_json_bytes(FEATURE_CONFIG.to_dict()),
        )
        vocabulary = dict(sorted(vectorizer.vocabulary_.items()))
        _write_bytes(temporary / "vocabulary.json", canonical_json_bytes(vocabulary))
        _save_array(
            temporary / "inverse-document-frequency.npy",
            np.asarray(vectorizer.idf_, dtype=np.float64),
        )
        _save_array(temporary / "matrix-data.npy", np.asarray(matrix.data, dtype=np.float64))
        _save_array(temporary / "matrix-indices.npy", np.asarray(matrix.indices, dtype=np.int32))
        _save_array(temporary / "matrix-indptr.npy", np.asarray(matrix.indptr, dtype=np.int32))
        _save_array(temporary / "popularity.npy", np.asarray(popularity, dtype=np.float64))
        members = {
            name: {
                "size": (temporary / name).stat().st_size,
                "sha256": sha256_file(temporary / name),
            }
            for name in REQUIRED_MEMBERS
        }
        manifest = {
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "model": {"name": MODEL_NAME, "version": MODEL_VERSION},
            "built_at": timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "data_fingerprint": snapshot.fingerprint,
            "item_count": len(snapshot.items),
            "row_slugs": [item.slug for item in snapshot.items],
            "vocabulary_size": len(vocabulary),
            "matrix": {
                "shape": [int(matrix.shape[0]), int(matrix.shape[1])],
                "nonzero": int(matrix.nnz),
                "dtype": "float64",
                "format": "csr-transparent-npy",
            },
            "feature_config": FEATURE_CONFIG.to_dict(),
            "popularity_config": POPULARITY_CONFIG.to_dict(),
            "ranking_config": RANKING_CONFIG.to_dict(),
            "limits": ARTIFACT_LIMITS.to_dict(),
            "compatibility": {
                "code": CODE_COMPATIBILITY,
                "python": f"{sys.version_info.major}.{sys.version_info.minor}",
                "numpy": np.__version__,
                "scipy": scipy.__version__,
                "scikit_learn": sklearn.__version__,
            },
            "random_seed": None,
            "members": members,
        }
        _write_bytes(temporary / "manifest.json", canonical_json_bytes(manifest))
        load_artifact(temporary)
        temporary.replace(target)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


def inspect_artifact(path: str | Path) -> dict[str, object]:
    artifact = load_artifact(path)
    return {
        "status": "valid",
        "model": {"name": artifact.model_name, "version": artifact.model_version},
        "artifact_schema_version": artifact.manifest["artifact_schema_version"],
        "data_fingerprint": artifact.data_fingerprint,
        "item_count": len(artifact.items),
        "vocabulary_size": artifact.matrix.shape[1],
        "matrix_nonzero": artifact.matrix.nnz,
    }


def inspect_json(path: str | Path) -> str:
    return json.dumps(inspect_artifact(path), indent=2, sort_keys=True)
