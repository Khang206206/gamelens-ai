from __future__ import annotations

import argparse
import errno
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http.cookiejar import CookieJar
from pathlib import Path

from app.core.config import DEVELOPMENT_SESSION_SECRET, Settings
from app.db.models import RecommendationEvent
from app.db.session import create_database_engine, create_session_factory
from app.repositories.recommendation_catalog import RecommendationCatalogRepository
from app.services.recommendation import (
    create_collaborative_component,
    create_recommendation_service,
)
from gamelens_recommender import HYBRID_FALLBACK_REASONS, UserContext
from gamelens_recommender.collaborative_artifacts import (
    CollaborativeArtifactError,
    inspect_collaborative_artifact,
    load_collaborative_artifact,
)
from gamelens_recommender.training import inspect_artifact
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

ARTIFACT_SET = Path("/tmp/gamelens-e2e/artifact-set")
CONTENT_ARTIFACT = ARTIFACT_SET / "content-v1"
COLLABORATIVE_ARTIFACT = ARTIFACT_SET / "collaborative-fixture-v1"
CORRUPT_COLLABORATIVE_ARTIFACT = ARTIFACT_SET / "collaborative-fixture-corrupt"
EXPIRED_COLLABORATIVE_ARTIFACT = ARTIFACT_SET / "collaborative-fixture-expired"
CATALOG_MISMATCH_COLLABORATIVE_ARTIFACT = ARTIFACT_SET / "collaborative-fixture-catalog-mismatch"
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
    fallback_reason: str | None


@dataclass(frozen=True)
class HttpResult:
    status: int
    payload: dict[str, object] | None


def _read_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError(f"Probe endpoint returned HTTP {response.status}")
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise RuntimeError("Probe endpoint returned a non-object payload")
    return payload


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _copy_artifact(source: Path, target: Path) -> None:
    if target.exists() or target.is_symlink():
        raise RuntimeError(f"Fallback artifact target already exists: {target.name}")
    shutil.copytree(source, target, symlinks=False)


def prepare_fallback_artifacts() -> dict[str, object]:
    if os.geteuid() == 0:
        raise RuntimeError("Fallback artifact preparation unexpectedly runs as root")
    content = inspect_artifact(CONTENT_ARTIFACT)
    expected_catalog_fingerprint = str(content["data_fingerprint"])
    load_collaborative_artifact(
        COLLABORATIVE_ARTIFACT,
        allow_fixture=True,
        expected_catalog_fingerprint=expected_catalog_fingerprint,
    )

    _copy_artifact(COLLABORATIVE_ARTIFACT, CORRUPT_COLLABORATIVE_ARTIFACT)
    corrupt_manifest = json.loads(
        (CORRUPT_COLLABORATIVE_ARTIFACT / "manifest.json").read_text(encoding="utf-8")
    )
    member_name = sorted(corrupt_manifest["members"])[0]
    member_path = CORRUPT_COLLABORATIVE_ARTIFACT / member_name
    member = bytearray(member_path.read_bytes())
    if not member:
        raise RuntimeError("Cannot corrupt an empty collaborative artifact member")
    member[-1] ^= 0x01
    member_path.write_bytes(member)

    _copy_artifact(COLLABORATIVE_ARTIFACT, EXPIRED_COLLABORATIVE_ARTIFACT)
    expired_manifest_path = EXPIRED_COLLABORATIVE_ARTIFACT / "manifest.json"
    expired_manifest = json.loads(expired_manifest_path.read_text(encoding="utf-8"))
    built_at = datetime.fromisoformat(
        str(expired_manifest["build"]["built_at"]).replace("Z", "+00:00")
    )
    expired_manifest["lifecycle"]["valid_until"] = (
        (built_at.astimezone(UTC) + timedelta(microseconds=1))
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
    expired_manifest_path.write_bytes(_canonical_json(expired_manifest))

    _copy_artifact(COLLABORATIVE_ARTIFACT, CATALOG_MISMATCH_COLLABORATIVE_ARTIFACT)
    mismatch_manifest_path = CATALOG_MISMATCH_COLLABORATIVE_ARTIFACT / "manifest.json"
    mismatch_manifest = json.loads(mismatch_manifest_path.read_text(encoding="utf-8"))
    mismatch_fingerprint = "0" * 64
    if mismatch_fingerprint == expected_catalog_fingerprint:
        mismatch_fingerprint = "f" * 64
    mismatch_manifest["catalog_fingerprint"] = mismatch_fingerprint
    mismatch_manifest_path.write_bytes(_canonical_json(mismatch_manifest))

    expected_errors = {
        CORRUPT_COLLABORATIVE_ARTIFACT: "artifact_integrity_failed",
        EXPIRED_COLLABORATIVE_ARTIFACT: "artifact_expired",
        CATALOG_MISMATCH_COLLABORATIVE_ARTIFACT: "catalog_mismatch",
    }
    observed: dict[str, str] = {}
    for artifact_path, expected_code in expected_errors.items():
        try:
            load_collaborative_artifact(
                artifact_path,
                allow_fixture=True,
                expected_catalog_fingerprint=expected_catalog_fingerprint,
            )
        except CollaborativeArtifactError as error:
            if error.code != expected_code:
                raise RuntimeError(
                    f"Fallback artifact {artifact_path.name} failed with {error.code}"
                ) from error
            observed[artifact_path.name] = error.code
        else:
            raise RuntimeError(f"Fallback artifact {artifact_path.name} unexpectedly loaded")
    return {"fallback_artifacts": observed, "runtime_uid": os.geteuid()}


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


def _guarded_database_url() -> str:
    if os.environ.get("ENVIRONMENT") != "test":
        raise RuntimeError("Fallback assertion requires ENVIRONMENT=test")
    database_url = os.environ.get("DATABASE_URL")
    if database_url is None:
        raise RuntimeError("Fallback assertion requires DATABASE_URL")
    configured = make_url(database_url)
    if (
        configured.get_backend_name() != "postgresql"
        or configured.host != "test-db"
        or configured.database is None
        or not configured.database.endswith("_test")
    ):
        raise RuntimeError("Fallback assertion requires the disposable test database")
    return database_url


def _http_json(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> HttpResult:
    request_headers = dict(headers or {})
    body = None
    if payload is not None:
        body = _canonical_json(payload)
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method,
    )
    try:
        response = opener.open(request, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read()
        status = response.status
    if not raw:
        return HttpResult(status=status, payload=None)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("Fallback API returned a non-object payload")
    return HttpResult(status=status, payload=parsed)


def _expect_status(result: HttpResult, expected: int, label: str) -> dict[str, object]:
    if result.status != expected or result.payload is None:
        raise RuntimeError(f"{label} returned HTTP {result.status}")
    return result.payload


def _fallback_session(
    api_url: str,
    *,
    selected_game_id: int,
) -> tuple[urllib.request.OpenerDirector, str]:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    origin = "http://gamelens.test:3000"
    consent = _expect_status(
        _http_json(
            opener,
            f"{api_url}/api/v1/anonymous-sessions",
            method="POST",
            payload={"consent": True, "consent_version": "stage-4-v1"},
            headers={"Origin": origin},
        ),
        201,
        "Fallback consent",
    )
    csrf = consent.get("csrf_token")
    if not isinstance(csrf, str) or not re.fullmatch(r"[0-9a-f]{64}", csrf):
        raise RuntimeError("Fallback consent did not return a bounded CSRF token")
    preferences = _http_json(
        opener,
        f"{api_url}/api/v1/me/preferences",
        method="PUT",
        payload={
            "selected_game_ids": [selected_game_id],
            "preferred_genres": ["strategy"],
            "preferred_tags": [],
            "preferred_platforms": [],
        },
        headers={"Origin": origin, "X-CSRF-Token": csrf},
    )
    _expect_status(preferences, 200, "Fallback preference save")
    return opener, csrf


def _assert_exact_stage_4_fallback(
    body: dict[str, object],
    *,
    expected_reason: str,
    selected_game_slug: str,
) -> None:
    database_url = _guarded_database_url()
    engine = create_database_engine(database_url)
    try:
        factory = create_session_factory(engine)
        with factory() as session:
            catalog = RecommendationCatalogRepository(session).load()
            snapshot = catalog.model_snapshot
            if snapshot is None:
                raise RuntimeError("Fallback oracle catalog is not ready")
            oracle = create_recommendation_service(CONTENT_ARTIFACT).recommend_personalized(
                snapshot=snapshot,
                context=UserContext(
                    selected_game_slugs=(selected_game_slug,),
                    preferred_genres=("strategy",),
                    top_k=5,
                ),
                feedback=(),
            )
            generation_id = body.get("generation_id")
            event = session.scalar(
                select(RecommendationEvent).where(
                    RecommendationEvent.generation_id == generation_id
                )
            )
            event_snapshot = (
                None
                if event is None
                else {
                    "event_schema_version": event.event_schema_version,
                    "ranking_mode": event.ranking_mode,
                    "fallback_reason": event.fallback_reason,
                    "hybrid_policy_name": event.hybrid_policy_name,
                    "collaborative_model_name": event.collaborative_model_name,
                    "request_context": dict(event.request_context or {}),
                    "result_summary": list(event.result_summary or []),
                }
            )
            session.rollback()
    finally:
        engine.dispose()

    if body.get("ranking_mode") != "stage_4_fallback":
        raise RuntimeError("Fallback response did not use the Stage 4 path")
    if body.get("fallback_reason") != expected_reason:
        raise RuntimeError("Fallback response exposed the wrong typed reason")
    if body.get("hybrid_policy") is not None or body.get("collaborative_model") is not None:
        raise RuntimeError("Fallback response exposed applied collaborative identity")
    policy = body.get("policy")
    if policy != {"name": oracle.policy.name, "version": oracle.policy.version}:
        raise RuntimeError("Fallback response did not preserve the Stage 4 policy")
    if body.get("response_reason") != oracle.reason:
        raise RuntimeError("Fallback response did not preserve the Stage 4 result reason")
    raw_items = body.get("items")
    if not isinstance(raw_items, list):
        raise RuntimeError("Fallback response items are invalid")
    expected_items = [
        (item.slug, item.rank, item.base_score_units, item.final_score_units)
        for item in oracle.items
    ]
    actual_items: list[tuple[object, object, int, int]] = []
    for item in raw_items:
        if not isinstance(item, dict) or not isinstance(item.get("game"), dict):
            raise RuntimeError("Fallback response item is invalid")
        actual_items.append(
            (
                item["game"].get("slug"),
                item.get("rank"),
                round(float(item.get("base_ranking_score", -1)) * 1_000_000),
                round(float(item.get("ranking_score", -1)) * 1_000_000),
            )
        )
        if (
            item.get("candidate_origin") != "content"
            or item.get("collaborative_supported") is not False
            or item.get("collaborative_score") != 0
            or item.get("collaborative_weight") != 0
            or item.get("collaborative_contribution") != 0
            or item.get("collaborative_item_support") is not None
            or item.get("collaborative_source_edges") != []
        ):
            raise RuntimeError("Fallback response item contains collaborative evidence")
    if actual_items != expected_items:
        raise RuntimeError("Fallback response scores or order differ from the Stage 4 oracle")

    if event_snapshot is None:
        raise RuntimeError("Fallback response has no committed Stage 5 event")
    if (
        event_snapshot["event_schema_version"] != "stage-5-v1"
        or event_snapshot["ranking_mode"] != body["ranking_mode"]
        or event_snapshot["fallback_reason"] != body["fallback_reason"]
        or event_snapshot["hybrid_policy_name"] is not None
        or event_snapshot["collaborative_model_name"] is not None
        or event_snapshot["request_context"].get("ranking_mode") != body["ranking_mode"]
        or event_snapshot["request_context"].get("fallback_reason") != body["fallback_reason"]
    ):
        raise RuntimeError("Fallback event identity differs from the response")
    event_items = event_snapshot["result_summary"]
    if [(item.get("slug"), item.get("rank"), item.get("final_units")) for item in event_items] != [
        (item[0], item[1], item[3]) for item in expected_items
    ]:
        raise RuntimeError("Fallback event scores or order differ from the Stage 4 oracle")


def _collaborative_status_for_reason(reason: str) -> dict[str, object]:
    if reason == "not_configured":
        return {"status": "not_configured", "reason": reason, "source_kind": None}
    if reason in {"artifact_missing", "artifact_corrupt", "fixture_not_allowed"}:
        return {"status": "unavailable", "reason": reason, "source_kind": None}
    if reason == "catalog_stale":
        return {"status": "stale", "reason": reason, "source_kind": "fixture"}
    if reason == "artifact_expired":
        return {"status": "stale", "reason": reason, "source_kind": None}
    if reason == "no_supported_sources":
        return {"status": "fixture_only", "reason": None, "source_kind": "fixture"}
    raise RuntimeError(f"Unsupported fallback matrix reason: {reason}")


def fallback_probe() -> dict[str, object]:
    expected_reason = os.environ.get("E2E_EXPECTED_FALLBACK_REASON", "not_configured")
    if expected_reason not in HYBRID_FALLBACK_REASONS:
        raise RuntimeError("Expected fallback reason is invalid")
    api_url = os.environ.get("FALLBACK_API_URL", "http://e2e-fallback-api:8000").rstrip("/")
    selected_game_id = 4 if expected_reason == "no_supported_sources" else 1
    selected_game_slug = "abyssal-signal" if selected_game_id == 4 else "emberfall-tactics"

    health = _read_json(f"{api_url}/health")
    if health.get("status") != "ok" or health.get("database") != "ready":
        raise RuntimeError("Fallback API health is not ready")
    status = _read_json(f"{api_url}/api/v1/models/status")
    components = status.get("components")
    if status.get("status") != "ready" or not isinstance(components, dict):
        raise RuntimeError(
            "Fallback API did not preserve content readiness: " + json.dumps(status, sort_keys=True)
        )
    if components.get("content") != {"status": "ready", "reason": None}:
        raise RuntimeError("Fallback API content component is not ready")
    expected_collaborative = _collaborative_status_for_reason(expected_reason)
    if components.get("collaborative") != expected_collaborative:
        raise RuntimeError("Fallback API collaborative status is not truthful")

    opener, csrf = _fallback_session(api_url, selected_game_id=selected_game_id)
    response = _expect_status(
        _http_json(
            opener,
            f"{api_url}/api/v1/me/recommendations",
            method="POST",
            payload={"top_k": 5},
            headers={
                "Origin": "http://gamelens.test:3000",
                "X-CSRF-Token": csrf,
            },
        ),
        200,
        "Fallback generation",
    )
    _assert_exact_stage_4_fallback(
        response,
        expected_reason=expected_reason,
        selected_game_slug=selected_game_slug,
    )
    generation_id = response["generation_id"]
    deleted = _http_json(
        opener,
        f"{api_url}/api/v1/me",
        method="DELETE",
        headers={"Origin": "http://gamelens.test:3000", "X-CSRF-Token": csrf},
    )
    if deleted.status != 204:
        raise RuntimeError("Fallback probe could not remove its disposable session")

    engine = create_database_engine(_guarded_database_url())
    try:
        with create_session_factory(engine)() as session:
            retained = session.scalar(
                select(func.count())
                .select_from(RecommendationEvent)
                .where(RecommendationEvent.generation_id == generation_id)
            )
            session.rollback()
    finally:
        engine.dispose()
    if retained != 0:
        raise RuntimeError("Fallback probe session cleanup retained its event")
    return {
        "collaborative": expected_collaborative,
        "event": {"committed_before_cleanup": True, "matched_response": True},
        "fallback_reason": expected_reason,
        "stage_4_oracle": {"scores": "exact", "order": "exact"},
    }


def required_content_failure_probe() -> dict[str, object]:
    api_url = os.environ.get("FALLBACK_API_URL", "http://e2e-fallback-api:8000").rstrip("/")
    health = _read_json(f"{api_url}/health")
    if health.get("status") != "ok" or health.get("database") != "ready":
        raise RuntimeError("Required-content failure changed database health behavior")
    status = _read_json(f"{api_url}/api/v1/models/status")
    components = status.get("components")
    if (
        status.get("status") != "unavailable"
        or status.get("unavailable_reason") != "artifact_missing"
        or not isinstance(components, dict)
        or components.get("content") != {"status": "unavailable", "reason": "artifact_missing"}
    ):
        raise RuntimeError("Required-content status did not retain its distinct failure")

    engine = create_database_engine(_guarded_database_url())
    try:
        factory = create_session_factory(engine)
        with factory() as session:
            before = session.scalar(
                select(func.count())
                .select_from(RecommendationEvent)
                .where(RecommendationEvent.event_schema_version == "stage-5-v1")
            )
            session.rollback()
        opener, csrf = _fallback_session(api_url, selected_game_id=1)
        failed = _http_json(
            opener,
            f"{api_url}/api/v1/me/recommendations",
            method="POST",
            payload={"top_k": 5},
            headers={
                "Origin": "http://gamelens.test:3000",
                "X-CSRF-Token": csrf,
            },
        )
        error = failed.payload.get("error") if failed.payload else None
        if (
            failed.status != 503
            or not isinstance(error, dict)
            or error.get("code") != "artifact_missing"
        ):
            raise RuntimeError("Required-content failure became an optional fallback")
        with factory() as session:
            after = session.scalar(
                select(func.count())
                .select_from(RecommendationEvent)
                .where(RecommendationEvent.event_schema_version == "stage-5-v1")
            )
            session.rollback()
    finally:
        engine.dispose()
    if after != before:
        raise RuntimeError("Required-content failure committed a recommendation event")
    deleted = _http_json(
        opener,
        f"{api_url}/api/v1/me",
        method="DELETE",
        headers={"Origin": "http://gamelens.test:3000", "X-CSRF-Token": csrf},
    )
    if deleted.status != 204:
        raise RuntimeError("Required-content probe could not remove its disposable session")
    return {
        "content": {"status": "unavailable", "reason": "artifact_missing"},
        "database_health": "ready",
        "event_committed": False,
        "recommendation_status": 503,
    }


def environment_fixture_rejection_probe() -> dict[str, object]:
    expected_environment = os.environ.get("E2E_EXPECTED_ENVIRONMENT")
    if expected_environment not in {"development", "production"}:
        raise RuntimeError("Fixture rejection requires development or production")
    settings = Settings(_env_file=None)
    if settings.environment != expected_environment:
        raise RuntimeError("Fixture rejection loaded an unexpected environment")
    if settings.collaborative_allow_test_fixture:
        raise RuntimeError("Non-test fixture rejection must not enable the fixture gate")
    if settings.collaborative_artifact_path != COLLABORATIVE_ARTIFACT:
        raise RuntimeError("Fixture rejection did not receive the valid fixture artifact")
    if expected_environment == "production" and (
        not settings.anonymous_session_cookie_secure
        or any(origin.startswith("http://") for origin in settings.cors_origins)
        or settings.anonymous_session_secret.get_secret_value() == DEVELOPMENT_SESSION_SECRET
    ):
        raise RuntimeError("Production fixture rejection used invalid security settings")
    component = create_collaborative_component(
        settings.collaborative_artifact_path,
        environment=settings.environment,
        allow_test_fixture=settings.collaborative_allow_test_fixture,
    )
    if component.load_state != "unavailable" or component.unavailable_reason != (
        "fixture_not_allowed"
    ):
        raise RuntimeError("Fixture artifact was not rejected outside ENVIRONMENT=test")
    return {
        "environment": expected_environment,
        "fixture": {"status": "unavailable", "reason": "fixture_not_allowed"},
        "security_settings": "valid",
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
                "fallback_reason",
                "generation_id",
                "ranking_mode",
            }:
                raise RuntimeError("Browser event evidence shape is invalid")
            generation_id = payload["generation_id"]
            ranking_mode = payload["ranking_mode"]
            fallback_reason = payload["fallback_reason"]
            if not isinstance(generation_id, str) or not _GENERATION_ID.fullmatch(generation_id):
                raise RuntimeError("Browser event evidence generation identity is invalid")
            if ranking_mode not in {"hybrid", "stage_4_fallback"}:
                raise RuntimeError("Browser event evidence ranking mode is invalid")
            if (ranking_mode == "hybrid" and fallback_reason is not None) or (
                ranking_mode == "stage_4_fallback"
                and fallback_reason not in HYBRID_FALLBACK_REASONS
            ):
                raise RuntimeError("Browser event evidence fallback reason is invalid")
            evidence.append(EventEvidence(generation_id, ranking_mode, fallback_reason))

    if len({item.generation_id for item in evidence}) != len(evidence):
        raise RuntimeError("Browser event evidence contains a duplicate generation")
    return tuple(evidence)


def event_probe() -> dict[str, object]:
    database_url = _guarded_database_url()
    configured = make_url(database_url)

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
                    RecommendationEvent.fallback_reason,
                ).where(RecommendationEvent.event_schema_version == "stage-5-v1")
            ).all()
            connection.rollback()
    finally:
        engine.dispose()

    if len(rows) != len(expected):
        raise RuntimeError("Committed Stage 5 event count does not match browser evidence")
    actual = {
        generation_id: (ranking_mode, fallback_reason)
        for generation_id, ranking_mode, fallback_reason in rows
    }
    if len(actual) != len(rows):
        raise RuntimeError("Committed Stage 5 events contain a duplicate generation")
    if actual != {
        item.generation_id: (item.ranking_mode, item.fallback_reason) for item in expected
    }:
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
    parser.add_argument(
        "mode",
        choices=(
            "runtime",
            "immutability",
            "events",
            "prepare-fallback",
            "fallback",
            "required-content",
            "environment-rejection",
        ),
    )
    args = parser.parse_args()
    if args.mode == "runtime":
        result = runtime_probe()
    elif args.mode == "immutability":
        result = immutability_probe()
    elif args.mode == "events":
        result = event_probe()
    elif args.mode == "prepare-fallback":
        result = prepare_fallback_artifacts()
    elif args.mode == "fallback":
        result = fallback_probe()
    elif args.mode == "required-content":
        result = required_content_failure_probe()
    else:
        result = environment_fixture_rejection_probe()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
