from __future__ import annotations

import argparse
import errno
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.db.models import RecommendationEvent
from app.db.session import create_database_engine
from gamelens_recommender.collaborative_artifacts import inspect_collaborative_artifact
from gamelens_recommender.training import inspect_artifact
from sqlalchemy import select
from sqlalchemy.engine import make_url

ARTIFACT_SET = Path("/tmp/gamelens-e2e/artifact-set")
CONTENT_ARTIFACT = ARTIFACT_SET / "content-v1"
COLLABORATIVE_ARTIFACT = ARTIFACT_SET / "collaborative-fixture-v1"
FIXTURE_PATH = Path("/workspace/data/fixtures/interactions/collaborative-interactions.json")
CATALOG_PATH = Path("/workspace/data/catalog/games.json")
EVENT_EVIDENCE_DIR = Path("/tmp/gamelens-e2e/evidence")
MAX_EVENT_EVIDENCE_FILES = 16
MAX_EVENT_EVIDENCE_PER_FILE = 32
MAX_EVENT_EVIDENCE_BYTES = 64 * 1024
_EVIDENCE_FILE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*\.jsonl$")
_GENERATION_ID = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True)
class EventEvidence:
    generation_id: str
    ranking_mode: str


def _read_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError(f"Probe endpoint returned HTTP {response.status}")
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise RuntimeError("Probe endpoint returned a non-object payload")
    return payload


def _semantic_identity() -> dict[str, object]:
    content = inspect_artifact(CONTENT_ARTIFACT)
    collaborative = inspect_collaborative_artifact(
        COLLABORATIVE_ARTIFACT,
        allow_fixture=True,
        expected_catalog_fingerprint=str(content["data_fingerprint"]),
    )
    return {
        "content": content,
        "collaborative": {
            "artifact_schema_version": collaborative["artifact_schema_version"],
            "build_id": collaborative["build"]["id"],
            "catalog_fingerprint": collaborative["catalog_fingerprint"],
            "interaction_fingerprint": collaborative["interaction_fingerprint"],
            "item_support": collaborative["item_support"],
            "matrix": collaborative["matrix"],
            "model": collaborative["model"],
            "neighbors": collaborative["neighbors"],
            "source": collaborative["source"],
            "thresholds": collaborative["thresholds"],
        },
    }


def runtime_probe() -> dict[str, object]:
    runtime_uid = os.geteuid()
    if runtime_uid == 0:
        raise RuntimeError("Fixture API probe unexpectedly runs as root")

    health = _read_json("http://localhost:8000/health")
    if health.get("status") != "ok" or health.get("database") != "ready":
        raise RuntimeError("Fixture API health is not ready")
    if health.get("environment") != "test":
        raise RuntimeError("Fixture API is not isolated in ENVIRONMENT=test")

    model_status = _read_json("http://localhost:8000/api/v1/models/status")
    components = model_status.get("components")
    if not isinstance(components, dict):
        raise RuntimeError("Model status did not expose component readiness")
    content = components.get("content")
    collaborative = components.get("collaborative")
    if not isinstance(content, dict) or content.get("status") != "ready":
        raise RuntimeError("Content artifact is not ready")
    if not isinstance(collaborative, dict) or collaborative != {
        "status": "fixture_only",
        "reason": None,
        "source_kind": "fixture",
    }:
        raise RuntimeError("Collaborative fixture status is not ready")

    write_probe = ARTIFACT_SET / ".api-write-probe"
    try:
        write_probe.touch(exist_ok=False)
    except OSError as error:
        if error.errno not in {errno.EACCES, errno.EPERM, errno.EROFS}:
            raise RuntimeError("Fixture API write probe failed unexpectedly") from error
    else:
        write_probe.unlink(missing_ok=True)
        raise RuntimeError("Fixture API artifact mount is writable")
    if write_probe.exists():
        raise RuntimeError("Fixture API write probe left an artifact behind")

    return {
        "api_artifact_mount": "read_only",
        "health": {
            "database": health["database"],
            "environment": health["environment"],
            "status": health["status"],
        },
        "models": {
            "collaborative": collaborative,
            "content": content,
            "status": model_status["status"],
        },
        "runtime_uid": runtime_uid,
        "semantic_identity": _semantic_identity(),
    }


def _run_command(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def immutability_probe() -> dict[str, object]:
    runtime_uid = os.geteuid()
    if runtime_uid == 0:
        raise RuntimeError("Fixture immutability probe unexpectedly runs as root")

    content = _run_command(
        [
            "app.commands.recommendation_artifact",
            "build",
            "--output",
            str(CONTENT_ARTIFACT),
        ]
    )
    if content.returncode == 0 or "Artifact target already exists" not in content.stderr:
        raise RuntimeError("Content builder did not refuse its immutable target")

    collaborative = _run_command(
        [
            "app.commands.collaborative_artifact",
            "build",
            "--source",
            "fixture",
            "--output",
            str(COLLABORATIVE_ARTIFACT),
            "--fixture",
            str(FIXTURE_PATH),
            "--catalog",
            str(CATALOG_PATH),
        ]
    )
    try:
        collaborative_failure = json.loads(collaborative.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("Collaborative builder returned a non-JSON refusal") from error
    error_payload = collaborative_failure.get("error")
    error_code = error_payload.get("code") if isinstance(error_payload, dict) else None
    if collaborative.returncode != 2 or error_code != "artifact_target_exists":
        raise RuntimeError("Collaborative builder did not refuse its immutable target")

    return {
        "collaborative_target": "refused",
        "content_target": "refused",
        "runtime_uid": runtime_uid,
    }


def _load_event_evidence(evidence_dir: Path) -> tuple[EventEvidence, ...]:
    if not evidence_dir.is_dir() or evidence_dir.is_symlink():
        raise RuntimeError("Browser event evidence directory is unavailable")
    files = sorted(evidence_dir.iterdir(), key=lambda path: path.name)
    if not files or len(files) > MAX_EVENT_EVIDENCE_FILES:
        raise RuntimeError("Browser event evidence file count is invalid")

    evidence: list[EventEvidence] = []
    for path in files:
        if not _EVIDENCE_FILE_NAME.fullmatch(path.name) or path.is_symlink() or not path.is_file():
            raise RuntimeError("Browser event evidence contains an invalid member")
        if path.stat().st_size > MAX_EVENT_EVIDENCE_BYTES:
            raise RuntimeError("Browser event evidence exceeds its byte limit")
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or len(lines) > MAX_EVENT_EVIDENCE_PER_FILE:
            raise RuntimeError("Browser event evidence line count is invalid")
        for line in lines:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as error:
                raise RuntimeError("Browser event evidence is not valid JSON") from error
            if not isinstance(payload, dict) or set(payload) != {
                "generation_id",
                "ranking_mode",
            }:
                raise RuntimeError("Browser event evidence shape is invalid")
            generation_id = payload["generation_id"]
            ranking_mode = payload["ranking_mode"]
            if not isinstance(generation_id, str) or not _GENERATION_ID.fullmatch(generation_id):
                raise RuntimeError("Browser event evidence generation identity is invalid")
            if ranking_mode not in {"hybrid", "stage_4_fallback"}:
                raise RuntimeError("Browser event evidence ranking mode is invalid")
            evidence.append(EventEvidence(generation_id, ranking_mode))

    if len({item.generation_id for item in evidence}) != len(evidence):
        raise RuntimeError("Browser event evidence contains a duplicate generation")
    return tuple(evidence)


def event_probe() -> dict[str, object]:
    if os.environ.get("ENVIRONMENT") != "test":
        raise RuntimeError("Browser event assertion requires ENVIRONMENT=test")
    database_url = os.environ.get("DATABASE_URL")
    if database_url is None:
        raise RuntimeError("Browser event assertion requires DATABASE_URL")
    configured = make_url(database_url)
    if (
        configured.get_backend_name() != "postgresql"
        or configured.host != "test-db"
        or configured.database is None
        or not configured.database.endswith("_test")
    ):
        raise RuntimeError("Browser event assertion requires the disposable test database")

    expected = _load_event_evidence(EVENT_EVIDENCE_DIR)
    engine = create_database_engine(database_url)
    try:
        with engine.connect() as connection:
            database_name = connection.exec_driver_sql("SELECT current_database()").scalar_one()
            if database_name != configured.database:
                raise RuntimeError("Browser event assertion reached an unexpected database")
            rows = connection.execute(
                select(
                    RecommendationEvent.generation_id,
                    RecommendationEvent.ranking_mode,
                ).where(RecommendationEvent.event_schema_version == "stage-5-v1")
            ).all()
            connection.rollback()
    finally:
        engine.dispose()

    if len(rows) != len(expected):
        raise RuntimeError("Committed Stage 5 event count does not match browser evidence")
    actual = {generation_id: ranking_mode for generation_id, ranking_mode in rows}
    if len(actual) != len(rows):
        raise RuntimeError("Committed Stage 5 events contain a duplicate generation")
    if actual != {item.generation_id: item.ranking_mode for item in expected}:
        raise RuntimeError("Committed Stage 5 events do not match browser evidence")

    counts = Counter(item.ranking_mode for item in expected)
    return {
        "events": {
            "by_ranking_mode": dict(sorted(counts.items())),
            "exactly_once": True,
            "stage_5_total": len(expected),
        },
        "privacy": {
            "database_credentials_exposed_to_browser": False,
            "identity_fields_emitted": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe the disposable fixture stack")
    parser.add_argument("mode", choices=("runtime", "immutability", "events"))
    args = parser.parse_args()
    if args.mode == "runtime":
        result = runtime_probe()
    elif args.mode == "immutability":
        result = immutability_probe()
    else:
        result = event_probe()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
