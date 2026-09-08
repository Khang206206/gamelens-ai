from __future__ import annotations

import argparse
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
from app.core.security import parse_session_credential
from app.db.models import (
    CollaborativeArtifactBuild,
    CollaborativeArtifactContributor,
    CollaborativeContributionConsent,
    Interaction,
    RecommendationEvent,
    User,
    UserPreference,
)
from app.db.session import create_database_engine, create_session_factory
from gamelens_recommender import inspect_collaborative_artifact
from sqlalchemy import Engine, func, select
from sqlalchemy.engine import make_url

from tests.fixtures.collaborative_lifecycle import (
    CONTRIBUTION_CONSENT_VERSION,
    PERSONALIZATION_CONSENT_VERSION,
    PROVENANCE,
    SCENARIO_NAME,
    DisposableCollaborativeScenario,
    _controller_from_environment,
)
from tests.fixtures.e2e_live_source import _assert_private

ARTIFACT_SET = Path("/tmp/gamelens-e2e/artifact-set")
EVIDENCE_DIR = Path("/tmp/gamelens-e2e/lifecycle-evidence")
CONTENT_ARTIFACT = ARTIFACT_SET / "content-v1"
PREVIOUS_ARTIFACT = ARTIFACT_SET / "collaborative-lifecycle-previous-v1"
CURRENT_ARTIFACT = ARTIFACT_SET / "collaborative-lifecycle-current-v1"
SCENARIOS = (
    "preference-removal",
    "feedback-removal",
    "contribution-withdrawal",
    "clear-data",
    "reconsent",
)
_STATE_PATHS = {
    "contributor": EVIDENCE_DIR / ".stage8g-contributor-state.json",
    "observer": EVIDENCE_DIR / ".stage8g-observer-state.json",
}
_BROWSER_EVIDENCE = EVIDENCE_DIR / "stage8g-browser-evidence.jsonl"
_SCENARIO_METADATA = EVIDENCE_DIR / "stage8g-scenario.json"


def _scenario() -> str:
    value = os.environ.get("STAGE8G_SCENARIO")
    if value not in SCENARIOS:
        raise RuntimeError(f"Unsupported Stage 8G scenario: {value or 'missing'}")
    return value


def _build_id(slot: str) -> str:
    if slot not in {"previous", "current"}:
        raise RuntimeError("Lifecycle build slot is invalid")
    return f"stage8g-{_scenario()}-{slot}-v1"


def _artifact(slot: str) -> Path:
    if slot == "previous":
        return PREVIOUS_ARTIFACT
    if slot == "current":
        return CURRENT_ARTIFACT
    raise RuntimeError("Lifecycle artifact slot is invalid")


def _settings() -> Settings:
    settings = Settings(_env_file=None)
    test_database_url = os.environ.get("GAMELENS_TEST_DATABASE_URL")
    if test_database_url is None or make_url(test_database_url) != make_url(settings.database_url):
        raise RuntimeError("Lifecycle workflow requires one explicit test database URL")
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
        raise RuntimeError("Lifecycle workflow gates are not isolated from fixture mode")
    return settings


@contextmanager
def _guarded_engine() -> Iterator[tuple[Settings, Engine]]:
    settings = _settings()
    engine = create_database_engine(settings.database_url)
    try:
        identity = resolve_database_identity(engine, settings.database_url)
        if identity.schema != "public" or not identity.database.endswith("_test"):
            raise RuntimeError("Lifecycle workflow reached an unsafe PostgreSQL identity")
        yield settings, engine
    finally:
        engine.dispose()


@contextmanager
def _controller() -> Iterator[DisposableCollaborativeScenario]:
    controller, engine = _controller_from_environment()
    try:
        yield controller
    finally:
        engine.dispose()


def _read_json(path: Path, *, maximum: int = 256 * 1024) -> object:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > maximum:
        raise RuntimeError(f"Lifecycle evidence is missing or invalid: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _private_token(settings: Settings, role: str) -> str:
    if role not in _STATE_PATHS:
        raise RuntimeError("Lifecycle browser role is invalid")
    payload = _read_json(_STATE_PATHS[role], maximum=64 * 1024)
    if not isinstance(payload, dict) or set(payload) != {"cookies", "origins"}:
        raise RuntimeError("Lifecycle browser state has an invalid shape")
    cookies = payload.get("cookies")
    if not isinstance(cookies, list):
        raise RuntimeError("Lifecycle browser state has no cookie list")
    matches = [
        cookie
        for cookie in cookies
        if isinstance(cookie, dict)
        and cookie.get("name") == settings.anonymous_session_cookie_name
        and cookie.get("domain") == "gamelens.test"
        and cookie.get("path") == settings.anonymous_session_cookie_path
    ]
    if len(matches) != 1 or not isinstance(matches[0].get("value"), str):
        raise RuntimeError("Lifecycle browser state has no exact session cookie")
    token = matches[0]["value"]
    if not token or len(token) > 4096:
        raise RuntimeError("Lifecycle browser session credential is invalid")
    return token


def _credential_digest(settings: Settings, role: str) -> str:
    credential = parse_session_credential(settings, _private_token(settings, role))
    if credential is None:
        raise RuntimeError("Lifecycle browser session credential cannot be verified")
    return credential.digest


def _run_cli(arguments: list[str]) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, "-m", *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if completed.stderr:
        raise RuntimeError("Lifecycle operator command wrote unexpected stderr output")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("Lifecycle operator command returned non-JSON output") from error
    if not isinstance(payload, dict):
        raise RuntimeError("Lifecycle operator command returned a non-object payload")
    _assert_private(payload)
    return completed.returncode, payload


def _expect_ok(arguments: list[str]) -> dict[str, object]:
    returncode, payload = _run_cli(arguments)
    if returncode != 0 or payload.get("status") not in {
        "ok",
        "valid",
        "ready_for_functional_build",
    }:
        raise RuntimeError("Lifecycle operator command did not succeed")
    return payload


def _expect_failure(arguments: list[str], *, code: str) -> dict[str, object]:
    returncode, payload = _run_cli(arguments)
    error = payload.get("error")
    if (
        returncode != 2
        or payload.get("status") != "error"
        or not isinstance(error, dict)
        or error.get("code") != code
    ):
        actual_code = error.get("code") if isinstance(error, dict) else None
        raise RuntimeError(
            "Lifecycle operator command returned the wrong guarded failure "
            f"(expected={code}, actual={actual_code}, exit={returncode})"
        )
    return payload


def create_cohort() -> dict[str, object]:
    with _controller() as controller:
        result = controller.create_cohort(scenario=SCENARIO_NAME)
    if result.get("provenance") != PROVENANCE:
        raise RuntimeError("Lifecycle cohort lost its synthetic provenance")
    return result


def link_browser_session() -> dict[str, object]:
    contributor_token = _private_token(_settings(), "contributor")
    with _controller() as controller:
        result = controller.link_session(
            scenario=SCENARIO_NAME,
            raw_token=contributor_token,
        )
    with _guarded_engine() as (settings, engine), create_session_factory(engine)() as session:
        contributor_digest = _credential_digest(settings, "contributor")
        observer_digest = _credential_digest(settings, "observer")
        rows = dict(
            session.execute(
                select(User.anonymous_token_digest, CollaborativeContributionConsent.user_id)
                .outerjoin(
                    CollaborativeContributionConsent,
                    CollaborativeContributionConsent.user_id == User.id,
                )
                .where(User.anonymous_token_digest.in_((contributor_digest, observer_digest)))
            ).all()
        )
        session.rollback()
    if (
        len(rows) != 2
        or rows.get(contributor_digest) is None
        or rows.get(observer_digest) is not None
    ):
        raise RuntimeError("Private lifecycle linkage did not preserve contribution separation")
    return {
        "operation": "link-browser-session",
        "status": result["status"],
        "contributor_linked": True,
        "observer_linked": False,
        "privacy": {"identity_fields_emitted": False},
    }


def audit_live_source() -> dict[str, object]:
    report = _expect_ok(
        ["app.commands.collaborative_snapshot", "audit", "--source", "live", "--format", "json"]
    )
    if (
        report.get("source_kind") != "live"
        or report.get("ready_for_functional_build") is not True
        or report.get("approved_live_training_eligibility") is not False
    ):
        raise RuntimeError("Lifecycle live audit did not retain the functional-only boundary")
    support = report.get("support_filter")
    if not isinstance(support, dict):
        raise RuntimeError("Lifecycle live audit omitted aggregate support evidence")
    return {
        "operation": "audit-live-source",
        "status": report["status"],
        "data_revision": report["data_revision"],
        "retained_contributors": support.get("retained_contributors"),
        "approved_live_training_eligibility": False,
        "privacy": {"identity_fields_emitted": False},
    }


def build_live_source(slot: str) -> dict[str, object]:
    build_id = _build_id(slot)
    report = _expect_ok(
        [
            "app.commands.collaborative_artifact",
            "build",
            "--source",
            "live",
            "--output",
            str(_artifact(slot)),
            "--build-id",
            build_id,
            "--confirm-live-build",
            build_id,
        ]
    )
    if (
        report.get("source", {}).get("kind") != "live"  # type: ignore[union-attr]
        or report.get("build", {}).get("id") != build_id  # type: ignore[union-attr]
        or report.get("promotion", {}).get("status") != "active"  # type: ignore[union-attr]
    ):
        raise RuntimeError("Lifecycle live build metadata is inconsistent")
    lifecycle = report.get("lifecycle")
    matrix = report.get("matrix")
    if not isinstance(lifecycle, dict) or not isinstance(matrix, dict):
        raise RuntimeError("Lifecycle live build omitted aggregate lineage evidence")
    return {
        "operation": "build-live-source",
        "slot": slot,
        "build_id": build_id,
        "data_revision": lifecycle.get("data_revision"),
        "retained_contributors": matrix.get("retained_contributors"),
        "registry_status": "active",
        "privacy": {"identity_fields_emitted": False},
    }


def advance_revision() -> dict[str, object]:
    with _controller() as controller:
        result = controller.advance_revision(scenario=SCENARIO_NAME)
    values = result.get("data_revision")
    if (
        result.get("status") != "updated"
        or result.get("positive_labels_changed") is not False
        or not isinstance(values, dict)
        or values.get("after") != values.get("before", 0) + 1
    ):
        raise RuntimeError("Lifecycle source revision did not advance exactly once")
    return result


def validate_slot(slot: str) -> dict[str, object]:
    artifact = _artifact(slot)
    build_id = _build_id(slot)
    validated = _expect_ok(
        ["app.commands.collaborative_artifact", "validate", "--artifact", str(artifact)]
    )
    inspected = _expect_ok(
        ["app.commands.collaborative_artifact", "inspect", "--artifact", str(artifact)]
    )
    rollback = _expect_ok(
        ["app.commands.collaborative_artifact", "rollback-check", "--artifact", str(artifact)]
    )
    if (
        validated.get("build", {}).get("id") != build_id  # type: ignore[union-attr]
        or inspected.get("source", {}).get("kind") != "live"  # type: ignore[union-attr]
        or rollback.get("build_id") != build_id
        or rollback.get("readiness") != "ready"
    ):
        raise RuntimeError("Lifecycle artifact validation or rollback check diverged")
    return {
        "slot": slot,
        "build_id": build_id,
        "source_kind": "live",
        "readiness": "ready",
        "privacy": {"identity_fields_emitted": False},
    }


def verify_ready_builds() -> dict[str, object]:
    with _guarded_engine() as (settings, engine), create_session_factory(engine)() as session:
        contributor_digest = _credential_digest(settings, "contributor")
        observer_digest = _credential_digest(settings, "observer")
        contributor = session.scalar(
            select(User).where(User.anonymous_token_digest == contributor_digest)
        )
        observer = session.scalar(
            select(User).where(User.anonymous_token_digest == observer_digest)
        )
        if contributor is None or observer is None:
            raise RuntimeError("Lifecycle browser sessions are unavailable before serving")
        builds = {
            row.build_id: (row.status, row.registered_revision)
            for row in session.execute(
                select(
                    CollaborativeArtifactBuild.build_id,
                    CollaborativeArtifactBuild.status,
                    CollaborativeArtifactBuild.registered_revision,
                ).where(
                    CollaborativeArtifactBuild.build_id.in_(
                        (_build_id("previous"), _build_id("current"))
                    )
                )
            )
        }
        contributor_id = contributor.id
        observer_id = observer.id
        lineage = set(
            session.execute(
                select(
                    CollaborativeArtifactContributor.build_id,
                    CollaborativeArtifactContributor.user_id,
                ).where(CollaborativeArtifactContributor.build_id.in_(tuple(builds)))
            ).all()
        )
        session.rollback()
    previous = builds.get(_build_id("previous"))
    current = builds.get(_build_id("current"))
    if (
        previous is None
        or current is None
        or previous[0] != "active"
        or current[0] != "active"
        or previous[1] >= current[1]
        or (_build_id("previous"), contributor_id) not in lineage
        or (_build_id("current"), contributor_id) not in lineage
        or (_build_id("previous"), observer_id) in lineage
        or (_build_id("current"), observer_id) in lineage
    ):
        raise RuntimeError("Lifecycle build selection or contributor lineage is inconsistent")
    reports = {
        slot: inspect_collaborative_artifact(
            _artifact(slot), expected_consent_version=CONTRIBUTION_CONSENT_VERSION
        )
        for slot in ("previous", "current")
    }
    if any(report["status"] != "valid" for report in reports.values()):
        raise RuntimeError("Lifecycle bundle failed intrinsic validation")
    return {
        "status": "ready",
        "builds": {
            "previous": {
                "build_id": _build_id("previous"),
                "registered_revision": previous[1],
                "retained_contributors": reports["previous"]["matrix"]["retained_contributors"],
            },
            "current": {
                "build_id": _build_id("current"),
                "registered_revision": current[1],
                "retained_contributors": reports["current"]["matrix"]["retained_contributors"],
            },
        },
        "selection": {"explicit_api_recreation_required": True},
        "privacy": {"identity_fields_emitted": False},
    }


def private_transition(operation: str) -> dict[str, object]:
    token = _private_token(_settings(), "contributor")
    with _controller() as controller:
        if operation == "arrange-outdated-consent":
            result = controller.arrange_outdated_consent(
                scenario=SCENARIO_NAME,
                raw_token=token,
            )
        elif operation == "withdraw-contribution":
            result = controller.withdraw_contribution(
                scenario=SCENARIO_NAME,
                raw_token=token,
            )
        elif operation == "regrant-contribution":
            result = controller.regrant_contribution(
                scenario=SCENARIO_NAME,
                raw_token=token,
            )
        else:
            raise RuntimeError("Unsupported private lifecycle transition")
    return result


def verify_invalidated_builds() -> dict[str, object]:
    with (
        _guarded_engine() as (_settings_value, engine),
        create_session_factory(engine)() as session,
    ):
        statuses = dict(
            session.execute(
                select(
                    CollaborativeArtifactBuild.build_id, CollaborativeArtifactBuild.status
                ).where(
                    CollaborativeArtifactBuild.build_id.in_(
                        (_build_id("previous"), _build_id("current"))
                    )
                )
            ).all()
        )
        session.rollback()
    if statuses != {
        _build_id("previous"): "invalidated",
        _build_id("current"): "invalidated",
    }:
        raise RuntimeError("Applicable live lineage was not invalidated atomically")
    return {
        "status": "invalidated",
        "builds": {"previous": "invalidated", "current": "invalidated"},
        "privacy": {"identity_fields_emitted": False},
    }


def _browser_records() -> list[dict[str, object]]:
    if not _BROWSER_EVIDENCE.is_file() or _BROWSER_EVIDENCE.is_symlink():
        raise RuntimeError("Lifecycle browser evidence is missing")
    if _BROWSER_EVIDENCE.stat().st_size > 1024 * 1024:
        raise RuntimeError("Lifecycle browser evidence exceeds its bound")
    records: list[dict[str, object]] = []
    for raw_line in _BROWSER_EVIDENCE.read_text(encoding="utf-8").splitlines():
        value = json.loads(raw_line)
        if not isinstance(value, dict) or set(value) != {
            "phase",
            "role",
            "generation_id",
            "ranking_mode",
            "fallback_reason",
        }:
            raise RuntimeError("Lifecycle browser evidence has an invalid shape")
        _assert_private(value)
        records.append(value)
    return records


def _assert_event_records(session, records: list[dict[str, object]], *, phase: str) -> int:
    selected = [
        record for record in records if record["phase"] == phase and record["role"] == "observer"
    ]
    if len(selected) != 1:
        raise RuntimeError(f"Lifecycle browser phase has no exact observer event: {phase}")
    record = selected[0]
    event = session.scalar(
        select(RecommendationEvent).where(
            RecommendationEvent.generation_id == record["generation_id"]
        )
    )
    count = session.scalar(
        select(func.count())
        .select_from(RecommendationEvent)
        .where(RecommendationEvent.generation_id == record["generation_id"])
    )
    if (
        count != 1
        or event is None
        or event.event_schema_version != "stage-5-v1"
        or event.ranking_mode != record["ranking_mode"]
        or event.fallback_reason != record["fallback_reason"]
    ):
        raise RuntimeError("Lifecycle response and committed event diverged")
    return 1


def verify_transition() -> dict[str, object]:
    scenario = _scenario()
    records = _browser_records()
    metadata = _read_json(_SCENARIO_METADATA)
    if not isinstance(metadata, dict) or metadata.get("scenario") != scenario:
        raise RuntimeError("Lifecycle browser scenario metadata does not match the runner")
    with _guarded_engine() as (settings, engine), create_session_factory(engine)() as session:
        contributor_digest = _credential_digest(settings, "contributor")
        observer_digest = _credential_digest(settings, "observer")
        contributor = session.scalar(
            select(User).where(User.anonymous_token_digest == contributor_digest)
        )
        observer = session.scalar(
            select(User).where(User.anonymous_token_digest == observer_digest)
        )
        if observer is None:
            raise RuntimeError("Lifecycle transition removed the independent observer")
        observer_preferences = session.scalar(
            select(func.count())
            .select_from(UserPreference)
            .where(UserPreference.user_id == observer.id)
        )
        observer_contribution = session.get(CollaborativeContributionConsent, observer.id)
        builds = {
            row.build_id: row.status
            for row in session.execute(
                select(
                    CollaborativeArtifactBuild.build_id, CollaborativeArtifactBuild.status
                ).where(
                    CollaborativeArtifactBuild.build_id.in_(
                        (_build_id("previous"), _build_id("current"))
                    )
                )
            )
        }
        _assert_event_records(session, records, phase="transition")

        contributor_preferences = 0
        active_feedback = 0
        contribution_active = False
        consent_current = False
        if contributor is not None:
            contributor_preferences = int(
                session.scalar(
                    select(func.count())
                    .select_from(UserPreference)
                    .where(UserPreference.user_id == contributor.id)
                )
                or 0
            )
            active_feedback = int(
                session.scalar(
                    select(func.count())
                    .select_from(Interaction)
                    .where(
                        Interaction.user_id == contributor.id,
                        Interaction.superseded_at.is_(None),
                    )
                )
                or 0
            )
            contribution = session.get(CollaborativeContributionConsent, contributor.id)
            contribution_active = contribution is not None and contribution.withdrawn_at is None
            consent_current = contributor.consent_version == PERSONALIZATION_CONSENT_VERSION
        session.rollback()

    if builds != {
        _build_id("previous"): "invalidated",
        _build_id("current"): "invalidated",
    }:
        raise RuntimeError("Lifecycle mutation did not invalidate every applicable live lineage")
    if not observer_preferences or observer_contribution is not None:
        raise RuntimeError("Lifecycle mutation changed the independent observer boundary")
    if scenario == "clear-data" and contributor is not None:
        raise RuntimeError("Public clear-data retained the contributing session")
    if scenario == "preference-removal" and (contributor is None or contributor_preferences != 0):
        raise RuntimeError("Public preference removal did not clear the contributing session")
    if scenario == "feedback-removal" and (contributor is None or active_feedback != 0):
        raise RuntimeError("Public feedback removal retained active feedback")
    if scenario in {"contribution-withdrawal", "reconsent"} and (
        contributor is None or not contribution_active or not consent_current
    ):
        raise RuntimeError("Guarded renewal or public re-consent changed authority unexpectedly")
    return {
        "status": "invalidated",
        "scenario": scenario,
        "builds": {"previous": "invalidated", "current": "invalidated"},
        "observer": {"saved_data_preserved": True, "contribution_created": False},
        "contributor": {
            "session_deleted": contributor is None,
            "preferences_cleared": contributor_preferences == 0,
            "active_feedback_cleared": active_feedback == 0,
            "contribution_active": contribution_active,
            "personalization_consent_current": consent_current,
        },
        "event": {
            "ranking_mode": "stage_4_fallback",
            "fallback_reason": "privacy_invalid",
            "committed_exactly_once": True,
        },
        "privacy": {"identity_fields_emitted": False},
    }


def operator_cleanup() -> dict[str, object]:
    previous_id = _build_id("previous")
    current_id = _build_id("current")
    for slot in ("previous", "current"):
        _expect_failure(
            [
                "app.commands.collaborative_artifact",
                "rollback-check",
                "--artifact",
                str(_artifact(slot)),
            ],
            code="rollback_candidate_not_ready",
        )
    _expect_failure(
        [
            "app.commands.collaborative_artifact",
            "recover",
            "--artifact",
            str(CURRENT_ARTIFACT),
            "--build-id",
            current_id,
            "--confirm-live-recovery",
            current_id,
        ],
        code="revision_race",
    )
    retired = _expect_ok(
        [
            "app.commands.collaborative_artifact",
            "retire",
            "--build-id",
            previous_id,
            "--confirm-retirement",
            previous_id,
        ]
    )
    preview = _expect_ok(
        [
            "app.commands.collaborative_artifact",
            "retirement-preview",
            "--artifact-set",
            str(ARTIFACT_SET),
        ]
    )
    candidates = preview.get("candidates")
    confirmation = preview.get("cleanup_confirmation")
    if (
        retired.get("build", {}).get("status") != "retired"  # type: ignore[union-attr]
        or not isinstance(candidates, list)
        or [candidate.get("build_id") for candidate in candidates] != [previous_id]
        or not isinstance(confirmation, str)
    ):
        raise RuntimeError("Lifecycle retirement preview selected the wrong bundle")
    _expect_failure(
        [
            "app.commands.collaborative_artifact",
            "cleanup",
            "--artifact-set",
            str(ARTIFACT_SET),
            "--confirm-cleanup",
            f"{confirmation}-mismatch",
        ],
        code="cleanup_confirmation_mismatch",
    )
    cleaned = _expect_ok(
        [
            "app.commands.collaborative_artifact",
            "cleanup",
            "--artifact-set",
            str(ARTIFACT_SET),
            "--confirm-cleanup",
            confirmation,
        ]
    )
    if (
        PREVIOUS_ARTIFACT.exists()
        or not CURRENT_ARTIFACT.is_dir()
        or not CONTENT_ARTIFACT.is_dir()
        or cleaned.get("summary", {}).get("removed_count") != 1  # type: ignore[union-attr]
    ):
        raise RuntimeError("Lifecycle cleanup did not preserve the configured artifacts")
    return {
        "status": "ok",
        "rollback_after_invalidation": "rejected",
        "recovery_after_invalidation": "rejected",
        "retired_build": previous_id,
        "confirmation_mismatch": "rejected",
        "cleanup": {
            "removed_count": 1,
            "content_preserved": True,
            "configured_current_preserved": True,
        },
        "privacy": {"identity_fields_emitted": False},
    }


def final_verification(*, operator: bool) -> dict[str, object]:
    records = _browser_records()
    with (
        _guarded_engine() as (_settings_value, engine),
        create_session_factory(engine)() as session,
    ):
        event_count = 0
        for phase in ("ready", "transition", "restart"):
            event_count += _assert_event_records(session, records, phase=phase)
        if operator:
            event_count += _assert_event_records(session, records, phase="previous")
        statuses = dict(
            session.execute(
                select(
                    CollaborativeArtifactBuild.build_id, CollaborativeArtifactBuild.status
                ).where(
                    CollaborativeArtifactBuild.build_id.in_(
                        (_build_id("previous"), _build_id("current"))
                    )
                )
            ).all()
        )
        session.rollback()
    expected_previous = "retired" if operator else "invalidated"
    if statuses != {
        _build_id("previous"): expected_previous,
        _build_id("current"): "invalidated",
    }:
        raise RuntimeError("Lifecycle final registry state is inconsistent")
    for path in _STATE_PATHS.values():
        path.unlink(missing_ok=False)
    return {
        "status": "passed",
        "scenario": _scenario(),
        "events_verified": event_count,
        "registry": {"previous": expected_previous, "current": "invalidated"},
        "private_browser_state_removed": True,
        "privacy": {"identity_fields_emitted": False},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Control one disposable Stage 8G lifecycle run")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in (
        "cohort",
        "link",
        "audit",
        "advance",
        "ready",
        "assert-invalidated",
        "assert-transition",
        "operator-cleanup",
        "isolation",
    ):
        commands.add_parser(name)
    build_parser = commands.add_parser("build")
    build_parser.add_argument("slot", choices=("previous", "current"))
    validate_parser = commands.add_parser("validate")
    validate_parser.add_argument("slot", choices=("previous", "current"))
    private_parser = commands.add_parser("private-transition")
    private_parser.add_argument(
        "operation",
        choices=(
            "arrange-outdated-consent",
            "withdraw-contribution",
            "regrant-contribution",
        ),
    )
    final_parser = commands.add_parser("final")
    final_parser.add_argument("--operator", action="store_true")
    args = parser.parse_args()

    if args.command == "isolation":
        from tests.fixtures.e2e_isolation import snapshot

        result = snapshot()
    elif args.command == "cohort":
        result = create_cohort()
    elif args.command == "link":
        result = link_browser_session()
    elif args.command == "audit":
        result = audit_live_source()
    elif args.command == "build":
        result = build_live_source(args.slot)
    elif args.command == "advance":
        result = advance_revision()
    elif args.command == "validate":
        result = validate_slot(args.slot)
    elif args.command == "ready":
        result = verify_ready_builds()
    elif args.command == "private-transition":
        result = private_transition(args.operation)
    elif args.command == "assert-invalidated":
        result = verify_invalidated_builds()
    elif args.command == "assert-transition":
        result = verify_transition()
    elif args.command == "operator-cleanup":
        result = operator_cleanup()
    else:
        result = final_verification(operator=args.operator)
    _assert_private(result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
