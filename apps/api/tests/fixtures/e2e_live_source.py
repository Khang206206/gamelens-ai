from __future__ import annotations

import argparse
import errno
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.commands.operator_safety import (
    resolve_database_identity,
    validate_test_execution_configuration,
)
from app.core.config import Settings
from app.db.models import (
    CollaborativeArtifactBuild,
    CollaborativeArtifactContributor,
    CollaborativeContributionConsent,
    CollaborativeDataRevision,
    RecommendationEvent,
)
from app.db.session import create_database_engine, create_session_factory
from gamelens_recommender import inspect_collaborative_artifact
from gamelens_recommender.training import inspect_artifact
from sqlalchemy import Engine, func, select, text
from sqlalchemy.engine import make_url

from tests.fixtures.collaborative_lifecycle import (
    CONTRIBUTION_CONSENT_VERSION,
    PROVENANCE,
    _scenario_digests,
)
from tests.fixtures.e2e_fixture_stack import (
    _expect_status,
    _fallback_session,
    _http_json,
    _read_json,
)

ARTIFACT_SET = Path("/tmp/gamelens-e2e/artifact-set")
EVIDENCE_DIR = Path("/tmp/gamelens-e2e/live-evidence")
CONTENT_ARTIFACT = ARTIFACT_SET / "content-v1"
PREVIOUS_ARTIFACT = ARTIFACT_SET / "collaborative-live-previous-v1"
CURRENT_ARTIFACT = ARTIFACT_SET / "collaborative-live-current-v1"
MISSING_AUTHORITY_ARTIFACT = ARTIFACT_SET / "stage8f-missing-authority"
MISMATCHED_CONFIRMATION_ARTIFACT = ARTIFACT_SET / "stage8f-mismatched-confirmation"
PREVIOUS_BUILD_ID = "stage8f-live-previous-v1"
CURRENT_BUILD_ID = "stage8f-live-current-v1"
EXISTING_TARGET_BUILD_ID = "stage8f-existing-target-v1"
REGISTRY_REJECTION_TRIGGER = "trg_stage8f_reject_registry_build"
REGISTRY_REJECTION_FUNCTION = "stage8f_reject_registry_build"
RECORD_NAMES = (
    "cohort",
    "audit",
    "guard-failures",
    "registration-failure",
    "previous-recover",
    "previous-validate",
    "previous-inspect",
    "revision",
    "current-build",
    "current-validate",
    "current-inspect",
    "existing-target",
    "rollback",
)
_FORBIDDEN_IDENTITY_KEYS = frozenset(
    {"anonymous_token", "anonymous_token_digest", "digest", "user_id", "user_ids"}
)


def _settings() -> Settings:
    settings = Settings(_env_file=None)
    test_database_url = os.environ.get("GAMELENS_TEST_DATABASE_URL")
    if test_database_url is None or make_url(test_database_url) != make_url(settings.database_url):
        raise RuntimeError("Live-source workflow requires one explicit test database URL")
    validate_test_execution_configuration(
        settings.database_url,
        settings_environment=settings.environment,
        process_environment=os.environ.get("ENVIRONMENT"),
        allow_test_reset=os.environ.get("GAMELENS_ALLOW_TEST_DATABASE_RESET"),
    )
    if (
        not settings.collaborative_live_data_enabled
        or settings.collaborative_contribution_consent_version != CONTRIBUTION_CONSENT_VERSION
        or settings.collaborative_allow_test_fixture
    ):
        raise RuntimeError("Live-source workflow gates are not isolated from fixture mode")
    return settings


@contextmanager
def _guarded_engine() -> Iterator[tuple[Settings, Engine]]:
    settings = _settings()
    engine = create_database_engine(settings.database_url)
    try:
        identity = resolve_database_identity(engine, settings.database_url)
        if identity.schema != "public" or not identity.database.endswith("_test"):
            raise RuntimeError("Live-source workflow reached an unsafe PostgreSQL identity")
        yield settings, engine
    finally:
        engine.dispose()


def _run_cli(
    arguments: list[str],
    *,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", *arguments],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _json_output(completed: subprocess.CompletedProcess[str]) -> dict[str, object]:
    if completed.stderr:
        raise RuntimeError("Collaborative CLI wrote unexpected stderr output")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("Collaborative CLI returned non-JSON output") from error
    if not isinstance(payload, dict):
        raise RuntimeError("Collaborative CLI returned a non-object payload")
    _assert_private(payload)
    return payload


def _expect_cli_failure(
    completed: subprocess.CompletedProcess[str],
    *,
    code: str,
) -> dict[str, object]:
    payload = _json_output(completed)
    error = payload.get("error")
    if (
        completed.returncode != 2
        or payload.get("status") != "error"
        or not isinstance(error, dict)
        or error.get("code") != code
    ):
        raise RuntimeError(f"Collaborative CLI did not fail safely with {code}")
    return payload


def _assert_private(payload: object) -> None:
    serialized = json.dumps(payload, allow_nan=False, sort_keys=True)
    for digest in _scenario_digests():
        if digest in serialized:
            raise RuntimeError("Live-source output exposed a synthetic contributor digest")

    def visit(value: object) -> None:
        if isinstance(value, dict):
            if _FORBIDDEN_IDENTITY_KEYS & {str(key).casefold() for key in value}:
                raise RuntimeError("Live-source output exposed a contributor identity field")
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(payload)


def _registered_build_count(engine: Engine, *build_ids: str) -> int:
    with create_session_factory(engine)() as session:
        count = session.scalar(
            select(func.count())
            .select_from(CollaborativeArtifactBuild)
            .where(CollaborativeArtifactBuild.build_id.in_(build_ids))
        )
        session.rollback()
    return int(count or 0)


def guard_failure_probe() -> dict[str, object]:
    with _guarded_engine() as (_live_settings, engine):
        missing_environment = os.environ.copy()
        missing_environment.update(
            {
                "COLLABORATIVE_LIVE_DATA_ENABLED": "false",
                "COLLABORATIVE_CONTRIBUTION_CONSENT_VERSION": "",
                "COLLABORATIVE_LIVE_PROMOTION_ENABLED": "false",
                "COLLABORATIVE_ALLOW_TEST_FIXTURE": "false",
            }
        )
        missing = _expect_cli_failure(
            _run_cli(
                [
                    "app.commands.collaborative_artifact",
                    "build",
                    "--source",
                    "live",
                    "--output",
                    str(MISSING_AUTHORITY_ARTIFACT),
                    "--build-id",
                    "stage8f-missing-authority-v1",
                    "--confirm-live-build",
                    "stage8f-missing-authority-v1",
                ],
                environment=missing_environment,
            ),
            code="unapproved_live_source",
        )
        mismatch = _expect_cli_failure(
            _run_cli(
                [
                    "app.commands.collaborative_artifact",
                    "build",
                    "--source",
                    "live",
                    "--output",
                    str(MISMATCHED_CONFIRMATION_ARTIFACT),
                    "--build-id",
                    "stage8f-mismatched-confirmation-v1",
                    "--confirm-live-build",
                    "stage8f-wrong-confirmation-v1",
                ]
            ),
            code="live_build_confirmation_required",
        )
        if MISSING_AUTHORITY_ARTIFACT.exists() or MISMATCHED_CONFIRMATION_ARTIFACT.exists():
            raise RuntimeError("A refused live build created an artifact target")
        if _registered_build_count(
            engine,
            "stage8f-missing-authority-v1",
            "stage8f-mismatched-confirmation-v1",
        ):
            raise RuntimeError("A refused live build created a registry row")
    return {
        "missing_authority": {"code": missing["error"]["code"], "state_created": False},  # type: ignore[index]
        "mismatched_confirmation": {
            "code": mismatch["error"]["code"],  # type: ignore[index]
            "state_created": False,
        },
        "privacy": {"contributor_identities_emitted": False},
    }


def _install_registry_rejection(engine: Engine) -> None:
    with engine.begin() as connection:
        existing = connection.scalar(
            text(
                "SELECT count(*) FROM pg_trigger WHERE tgname = :trigger_name AND NOT tgisinternal"
            ),
            {"trigger_name": REGISTRY_REJECTION_TRIGGER},
        )
        if existing:
            raise RuntimeError("Disposable registry rejection trigger already exists")
        connection.execute(
            text(
                f"""
                CREATE FUNCTION {REGISTRY_REJECTION_FUNCTION}()
                RETURNS trigger
                LANGUAGE plpgsql
                AS $$
                BEGIN
                    IF NEW.build_id = '{PREVIOUS_BUILD_ID}' THEN
                        RAISE EXCEPTION USING
                            ERRCODE = '55000',
                            MESSAGE = 'Stage 8F simulated disposable registry rejection';
                    END IF;
                    RETURN NEW;
                END;
                $$
                """
            )
        )
        connection.execute(
            text(
                f"""
                CREATE TRIGGER {REGISTRY_REJECTION_TRIGGER}
                BEFORE INSERT ON collaborative_artifact_builds
                FOR EACH ROW
                EXECUTE FUNCTION {REGISTRY_REJECTION_FUNCTION}()
                """
            )
        )


def _remove_registry_rejection(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                f"DROP TRIGGER IF EXISTS {REGISTRY_REJECTION_TRIGGER} "
                "ON collaborative_artifact_builds"
            )
        )
        connection.execute(text(f"DROP FUNCTION IF EXISTS {REGISTRY_REJECTION_FUNCTION}()"))


def registration_failure_probe() -> dict[str, object]:
    with _guarded_engine() as (settings, engine):
        if not settings.collaborative_live_promotion_enabled:
            raise RuntimeError("Registration failure probe requires the disposable promotion gate")
        if PREVIOUS_ARTIFACT.exists() or _registered_build_count(engine, PREVIOUS_BUILD_ID):
            raise RuntimeError("Registration failure probe requires a fresh previous target")
        _install_registry_rejection(engine)
        try:
            failed = _expect_cli_failure(
                _run_cli(
                    [
                        "app.commands.collaborative_artifact",
                        "build",
                        "--source",
                        "live",
                        "--output",
                        str(PREVIOUS_ARTIFACT),
                        "--build-id",
                        PREVIOUS_BUILD_ID,
                        "--confirm-live-build",
                        PREVIOUS_BUILD_ID,
                    ]
                ),
                code="live_promotion_rejected",
            )
            if not PREVIOUS_ARTIFACT.is_dir():
                raise RuntimeError("Simulated registry failure did not retain a recoverable bundle")
            inspect_collaborative_artifact(
                PREVIOUS_ARTIFACT,
                expected_consent_version=CONTRIBUTION_CONSENT_VERSION,
            )
            if _registered_build_count(engine, PREVIOUS_BUILD_ID):
                raise RuntimeError("Rejected live build unexpectedly entered the registry")
            rollback = _expect_cli_failure(
                _run_cli(
                    [
                        "app.commands.collaborative_artifact",
                        "rollback-check",
                        "--artifact",
                        str(PREVIOUS_ARTIFACT),
                    ]
                ),
                code="rollback_candidate_not_ready",
            )
        finally:
            _remove_registry_rejection(engine)
    return {
        "registration_failure": {
            "artifact_complete": True,
            "code": failed["error"]["code"],  # type: ignore[index]
            "ready": False,
            "registered": False,
        },
        "rollback_before_recovery": rollback["error"]["code"],  # type: ignore[index]
        "recovery_required": True,
        "privacy": {"contributor_identities_emitted": False},
    }


def existing_target_probe() -> dict[str, object]:
    with _guarded_engine() as (settings, engine):
        if not settings.collaborative_live_promotion_enabled:
            raise RuntimeError("Existing-target probe requires the disposable promotion gate")
        failed = _expect_cli_failure(
            _run_cli(
                [
                    "app.commands.collaborative_artifact",
                    "build",
                    "--source",
                    "live",
                    "--output",
                    str(CURRENT_ARTIFACT),
                    "--build-id",
                    EXISTING_TARGET_BUILD_ID,
                    "--confirm-live-build",
                    EXISTING_TARGET_BUILD_ID,
                ]
            ),
            code="artifact_target_exists",
        )
        if _registered_build_count(engine, EXISTING_TARGET_BUILD_ID):
            raise RuntimeError("Existing-target refusal created a registry row")
        report = inspect_collaborative_artifact(
            CURRENT_ARTIFACT,
            expected_consent_version=CONTRIBUTION_CONSENT_VERSION,
        )
        if report["build"]["id"] != CURRENT_BUILD_ID:  # type: ignore[index]
            raise RuntimeError("Existing-target refusal changed the immutable current bundle")
    return {
        "existing_target": {
            "code": failed["error"]["code"],  # type: ignore[index]
            "original_build_preserved": True,
            "registry_row_created": False,
        }
    }


def _read_records() -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for name in RECORD_NAMES:
        path = EVIDENCE_DIR / f".stage8f-{name}.json"
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 256 * 1024:
            raise RuntimeError(f"Live-source run record is missing or invalid: {name}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError(f"Live-source run record is not an object: {name}")
        _assert_private(payload)
        records[name] = payload
    return records


def _assert_artifact_privacy(path: Path) -> None:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    _assert_private(manifest)
    item_slugs = json.loads((path / "item-slugs.json").read_text(encoding="utf-8"))
    _assert_private(item_slugs)
    for member in path.iterdir():
        lowered = member.name.casefold()
        if any(key in lowered for key in _FORBIDDEN_IDENTITY_KEYS):
            raise RuntimeError("Collaborative bundle contains a contributor identity member")


def verification_probe() -> dict[str, object]:
    records = _read_records()
    if records["cohort"].get("provenance") != PROVENANCE:
        raise RuntimeError("Live-source run record lost its synthetic cohort provenance")
    audit = records["audit"]
    if (
        audit.get("source_kind") != "live"
        or audit.get("ready_for_functional_build") is not True
        or audit.get("approved_live_training_eligibility") is not False
    ):
        raise RuntimeError("Live-source audit did not retain its functional-only boundary")
    revision = records["revision"]
    revision_values = revision.get("data_revision")
    if (
        revision.get("positive_labels_changed") is not False
        or not isinstance(revision_values, dict)
        or revision_values.get("after") != revision_values.get("before", 0) + 1
    ):
        raise RuntimeError("Live-source revision handoff is not the bounded expected change")
    if records["previous-recover"].get("promotion", {}).get("recovery") != (  # type: ignore[union-attr]
        "orphan_registered"
    ):
        raise RuntimeError("Previous live bundle did not use the existing recovery contract")
    if records["rollback"].get("readiness") != "ready":
        raise RuntimeError("Previous live bundle is not a valid rollback candidate")

    content = inspect_artifact(CONTENT_ARTIFACT)
    expected_catalog = str(content["data_fingerprint"])
    reports = {
        "previous": inspect_collaborative_artifact(
            PREVIOUS_ARTIFACT,
            expected_catalog_fingerprint=expected_catalog,
            expected_consent_version=CONTRIBUTION_CONSENT_VERSION,
        ),
        "current": inspect_collaborative_artifact(
            CURRENT_ARTIFACT,
            expected_catalog_fingerprint=expected_catalog,
            expected_consent_version=CONTRIBUTION_CONSENT_VERSION,
        ),
    }
    for name, report in reports.items():
        expected_id = PREVIOUS_BUILD_ID if name == "previous" else CURRENT_BUILD_ID
        if (
            report["status"] != "valid"
            or report["source"]["kind"] != "live"  # type: ignore[index]
            or report["build"]["id"] != expected_id  # type: ignore[index]
            or report["matrix"]["retained_contributors"] != 12  # type: ignore[index]
        ):
            raise RuntimeError(f"{name.title()} live bundle metadata is inconsistent")
        _assert_artifact_privacy(PREVIOUS_ARTIFACT if name == "previous" else CURRENT_ARTIFACT)

    with (
        _guarded_engine() as (_live_settings, engine),
        create_session_factory(engine)() as session,
    ):
        builds = {
            row.build_id: row
            for row in session.execute(
                select(
                    CollaborativeArtifactBuild.build_id,
                    CollaborativeArtifactBuild.status,
                    CollaborativeArtifactBuild.registered_revision,
                    CollaborativeArtifactBuild.interaction_fingerprint,
                ).where(
                    CollaborativeArtifactBuild.build_id.in_((PREVIOUS_BUILD_ID, CURRENT_BUILD_ID))
                )
            )
        }
        lineage_counts = dict(
            session.execute(
                select(
                    CollaborativeArtifactContributor.build_id,
                    func.count(CollaborativeArtifactContributor.user_id),
                )
                .where(
                    CollaborativeArtifactContributor.build_id.in_(
                        (PREVIOUS_BUILD_ID, CURRENT_BUILD_ID)
                    )
                )
                .group_by(CollaborativeArtifactContributor.build_id)
            ).all()
        )
        current_revision = session.scalar(
            select(CollaborativeDataRevision.revision).where(
                CollaborativeDataRevision.singleton_id == 1
            )
        )
        session.rollback()
    if set(builds) != {PREVIOUS_BUILD_ID, CURRENT_BUILD_ID}:
        raise RuntimeError("Live-source registry does not contain exactly both expected builds")
    previous = builds[PREVIOUS_BUILD_ID]
    current = builds[CURRENT_BUILD_ID]
    if (
        previous.status != "active"
        or current.status != "active"
        or previous.registered_revision >= current.registered_revision
        or current.registered_revision != current_revision
        or lineage_counts != {PREVIOUS_BUILD_ID: 12, CURRENT_BUILD_ID: 12}
        or previous.registered_revision != reports["previous"]["lifecycle"]["data_revision"]  # type: ignore[index]
        or current.registered_revision != reports["current"]["lifecycle"]["data_revision"]  # type: ignore[index]
        or previous.interaction_fingerprint != current.interaction_fingerprint
    ):
        raise RuntimeError("Live-source registry lineage or revisions are inconsistent")

    return {
        "mode": "disposable_live_source",
        "source": {
            "kind": "live",
            "cohort": "synthetic_postgresql",
            "contains_real_user_data": False,
            "quality_evidence": False,
        },
        "builds": {
            "previous": {
                "id": PREVIOUS_BUILD_ID,
                "registered_revision": previous.registered_revision,
                "status": previous.status,
            },
            "current": {
                "id": CURRENT_BUILD_ID,
                "registered_revision": current.registered_revision,
                "status": current.status,
            },
        },
        "lineage": {"matched_real_snapshot": True, "retained_contributors": 12},
        "privacy": {
            "bundle_identity_members": False,
            "cli_identity_fields": False,
            "contributor_identities_emitted": False,
        },
        "selection": {
            "artifact": str(CURRENT_ARTIFACT),
            "explicit_restart_required": True,
        },
    }


def saved_hybrid_smoke() -> dict[str, object]:
    settings = _settings()
    if settings.collaborative_live_promotion_enabled:
        raise RuntimeError("Serving API must not retain the live promotion gate")
    api_url = os.environ.get("LIVE_API_URL", "http://e2e-live-api:8000").rstrip("/")
    health = _read_json(f"{api_url}/health")
    status = _read_json(f"{api_url}/api/v1/models/status")
    components = status.get("components")
    if (
        health.get("status") != "ok"
        or health.get("database") != "ready"
        or status.get("status") != "ready"
        or not isinstance(components, dict)
        or components.get("content") != {"status": "ready", "reason": None}
        or components.get("collaborative")
        != {"status": "ready", "reason": None, "source_kind": "live"}
    ):
        raise RuntimeError("Live-source API components are not ready")

    write_probe = ARTIFACT_SET / ".stage8f-api-write-probe"
    try:
        write_probe.touch(exist_ok=False)
    except OSError as error:
        if error.errno not in {errno.EACCES, errno.EPERM, errno.EROFS}:
            raise RuntimeError("Live-source API write probe failed unexpectedly") from error
    else:
        write_probe.unlink(missing_ok=True)
        raise RuntimeError("Live-source API artifact mount is writable")

    with (
        _guarded_engine() as (_live_settings, engine),
        create_session_factory(engine)() as session,
    ):
        contribution_count_before = session.scalar(
            select(func.count()).select_from(CollaborativeContributionConsent)
        )
        session.rollback()

    opener, csrf = _fallback_session(api_url, selected_game_id=1)
    _expect_status(
        _http_json(
            opener,
            f"{api_url}/api/v1/me/preferences",
            method="PUT",
            payload={
                "selected_game_ids": [1],
                "preferred_genres": ["simulation"],
                "preferred_tags": [],
                "preferred_platforms": [],
            },
            headers={
                "Origin": "http://gamelens.test:3000",
                "X-CSRF-Token": csrf,
            },
        ),
        200,
        "Live-source supported preference save",
    )
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
        "Live-source saved generation",
    )
    items = response.get("items")
    if (
        response.get("ranking_mode") != "hybrid"
        or response.get("fallback_reason") is not None
        or not isinstance(response.get("collaborative_model"), dict)
        or not isinstance(items, list)
        or not items
        or not any(
            isinstance(item, dict)
            and item.get("collaborative_supported") is True
            and float(item.get("collaborative_contribution", 0)) > 0
            and bool(item.get("collaborative_source_edges"))
            for item in items
        )
    ):
        raise RuntimeError("Live-source saved generation did not apply collaborative evidence")

    generation_id = response.get("generation_id")
    with (
        _guarded_engine() as (_live_settings, engine),
        create_session_factory(engine)() as session,
    ):
        event = session.scalar(
            select(RecommendationEvent).where(RecommendationEvent.generation_id == generation_id)
        )
        event_count = session.scalar(
            select(func.count())
            .select_from(RecommendationEvent)
            .where(RecommendationEvent.generation_id == generation_id)
        )
        contribution_count_after = session.scalar(
            select(func.count()).select_from(CollaborativeContributionConsent)
        )
        current_build = session.get(CollaborativeArtifactBuild, CURRENT_BUILD_ID)
        event_snapshot = (
            None
            if event is None
            else {
                "event_schema_version": event.event_schema_version,
                "ranking_mode": event.ranking_mode,
                "fallback_reason": event.fallback_reason,
                "collaborative_model_name": event.collaborative_model_name,
            }
        )
        current_build_status = None if current_build is None else current_build.status
        session.rollback()
    if (
        event_count != 1
        or event_snapshot is None
        or event_snapshot["event_schema_version"] != "stage-5-v1"
        or event_snapshot["ranking_mode"] != "hybrid"
        or event_snapshot["fallback_reason"] is not None
        or event_snapshot["collaborative_model_name"] != response["collaborative_model"].get("name")  # type: ignore[union-attr]
        or contribution_count_after != contribution_count_before
        or current_build_status != "active"
    ):
        raise RuntimeError("Live-source response, event, contribution, or registry state diverged")

    deleted = _http_json(
        opener,
        f"{api_url}/api/v1/me",
        method="DELETE",
        headers={"Origin": "http://gamelens.test:3000", "X-CSRF-Token": csrf},
    )
    if deleted.status != 204:
        raise RuntimeError("Live-source smoke could not remove its disposable session")
    with (
        _guarded_engine() as (_live_settings, engine),
        create_session_factory(engine)() as session,
    ):
        retained_event = session.scalar(
            select(func.count())
            .select_from(RecommendationEvent)
            .where(RecommendationEvent.generation_id == generation_id)
        )
        session.rollback()
    if retained_event:
        raise RuntimeError("Live-source smoke cleanup retained its event")
    return {
        "api_artifact_mount": "read_only",
        "collaborative": {"source_kind": "live", "status": "ready"},
        "contribution_grant_created": False,
        "event": {"committed_exactly_once": True, "matched_response": True},
        "ranking_mode": "hybrid",
        "saved_session_cleaned": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe the disposable live-source stack")
    parser.add_argument(
        "mode",
        choices=(
            "guard-failures",
            "registration-failure",
            "existing-target",
            "verify",
            "saved-hybrid",
        ),
    )
    args = parser.parse_args()
    if args.mode == "guard-failures":
        result = guard_failure_probe()
    elif args.mode == "registration-failure":
        result = registration_failure_probe()
    elif args.mode == "existing-target":
        result = existing_target_probe()
    elif args.mode == "verify":
        result = verification_probe()
    else:
        result = saved_hybrid_smoke()
    _assert_private(result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
