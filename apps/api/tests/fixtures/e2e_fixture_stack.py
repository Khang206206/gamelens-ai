from __future__ import annotations

import argparse
import errno
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from gamelens_recommender.collaborative_artifacts import inspect_collaborative_artifact
from gamelens_recommender.training import inspect_artifact

ARTIFACT_SET = Path("/tmp/gamelens-e2e/artifact-set")
CONTENT_ARTIFACT = ARTIFACT_SET / "content-v1"
COLLABORATIVE_ARTIFACT = ARTIFACT_SET / "collaborative-fixture-v1"
FIXTURE_PATH = Path("/workspace/data/fixtures/interactions/collaborative-interactions.json")
CATALOG_PATH = Path("/workspace/data/catalog/games.json")


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe the disposable fixture stack")
    parser.add_argument("mode", choices=("runtime", "immutability"))
    args = parser.parse_args()
    result = runtime_probe() if args.mode == "runtime" else immutability_probe()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
