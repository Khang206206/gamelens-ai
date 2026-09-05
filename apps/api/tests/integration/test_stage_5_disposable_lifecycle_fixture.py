import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import pytest
from app.core.config import Settings
from app.core.security import session_token_digest
from app.db.models import (
    CollaborativeArtifactBuild,
    CollaborativeContributionConsent,
    RecommendationEvent,
    User,
)
from app.db.seed import load_seed_file, seed_database
from app.main import create_app
from app.repositories.collaborative_snapshot import (
    CollaborativeSnapshotRepository,
    begin_collaborative_snapshot,
)
from fastapi.testclient import TestClient
from gamelens_recommender import audit_profiles
from sqlalchemy import Engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.fixtures.collaborative_lifecycle import (
    CONTRIBUTION_CONSENT_VERSION,
    OUTDATED_PERSONALIZATION_CONSENT_VERSION,
    PERSONALIZATION_CONSENT_VERSION,
    SCENARIO_NAME,
    DisposableCollaborativeScenario,
    ScenarioControlError,
    _role_digest,
)

pytestmark = pytest.mark.integration


def _controller(
    engine: Engine,
    settings: Settings,
    *,
    process_environment: str | None = "test",
    allow_test_reset: str | None = "true",
) -> DisposableCollaborativeScenario:
    return DisposableCollaborativeScenario(
        engine,
        settings,
        process_environment=process_environment,
        allow_test_reset=allow_test_reset,
    )


def _seed_catalog(session: Session) -> None:
    seed_database(session, load_seed_file())


def _run_scenario_cli(
    command: str,
    *arguments: str,
    private_input: str | None = None,
) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.fixtures.collaborative_lifecycle",
            command,
            "--scenario",
            SCENARIO_NAME,
            *arguments,
        ],
        input=None if private_input is None else f"{private_input}\n",
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def _assert_private_output(payload: dict[str, object], *private_values: str) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    forbidden_keys = {"user_id", "user_ids", "token", "digest", "cohort_mapping"}

    def visit(value: object) -> None:
        if isinstance(value, dict):
            assert not (set(value) & forbidden_keys)
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(payload)
    for private_value in private_values:
        assert private_value not in serialized


def test_disposable_cohort_crosses_support_gate_and_keeps_exclusions_out(
    postgres_engine: Engine,
    postgres_session: Session,
    integration_settings: Settings,
) -> None:
    _seed_catalog(postgres_session)
    controller = _controller(postgres_engine, integration_settings)

    created = _run_scenario_cli("create-cohort")

    assert created["status"] == "created"
    assert created["cohort"] == {
        "defined_profiles": 17,
        "supported_profiles": 12,
        "positive_preferences": 47,
        "negative_signals": 2,
    }
    _assert_private_output(
        created,
        *(_role_digest(f"supported-{index:02d}") for index in range(1, 13)),
    )

    with Session(postgres_engine) as extraction_session:
        cutoff = begin_collaborative_snapshot(extraction_session)
        extracted = CollaborativeSnapshotRepository(extraction_session).extract(
            personalization_consent_version=PERSONALIZATION_CONSENT_VERSION,
            contribution_consent_version=CONTRIBUTION_CONSENT_VERSION,
        )
        report = audit_profiles(
            extracted.profiles,
            source_kind="live",
            catalog_fingerprint=extracted.catalog_fingerprint,
            exclusion_counts=extracted.exclusion_counts,
            cutoff=cutoff.isoformat(),
            data_revision=extracted.data_revision,
            consent_version=CONTRIBUTION_CONSENT_VERSION,
        )
        extraction_session.rollback()

    assert extracted.cutoff == cutoff
    assert extracted.eligible_contributors == 14
    assert len(extracted.profiles) == 14
    assert extracted.exclusion_counts == {
        "base_consent_mismatch": 1,
        "disliked": 1,
        "expired": 1,
        "low_rating": 1,
        "noncontributing": 0,
        "revoked": 1,
    }
    assert report["ready_for_functional_build"] is True
    assert report["candidate_profiles"] == {
        "contributors": 14,
        "positive_edges": 38,
        "distinct_items": 8,
        "profile_size_distribution": {
            "0": 1,
            "1": 0,
            "2": 1,
            "3-4": 12,
            "5-9": 0,
            "10+": 0,
        },
    }
    support = report["support_filter"]
    assert isinstance(support, dict)
    assert support["retained_contributors"] == 12
    assert support["retained_items"] == 6
    assert support["retained_positive_edges"] == 36

    inspected = _run_scenario_cli("inspect")
    assert inspected["cohort"] == {
        "defined_profiles": 17,
        "supported_profiles": 12,
        "positive_preferences": 47,
        "contribution_rows": 17,
        "withdrawn_contribution_rows": 0,
    }
    assert inspected["registry"] == {
        "total": 0,
        "by_status": {},
        "expected_status_matches": None,
    }
    assert inspected["events"] == {
        "stage_5_total": 0,
        "by_ranking_mode": {},
        "expected_mode_matches": None,
    }
    _assert_private_output(inspected)

    with pytest.raises(ScenarioControlError) as repeated:
        controller.create_cohort(scenario=SCENARIO_NAME)
    assert repeated.value.code == "scenario_already_exists"


def test_missing_catalog_refuses_without_creating_a_partial_cohort(
    postgres_engine: Engine,
    postgres_session: Session,
    integration_settings: Settings,
) -> None:
    with pytest.raises(ScenarioControlError) as missing_catalog:
        _controller(postgres_engine, integration_settings).create_cohort(scenario=SCENARIO_NAME)

    assert missing_catalog.value.code == "catalog_not_seeded"
    assert postgres_session.scalar(select(func.count()).select_from(User)) == 0


def test_partial_cohort_refuses_implicit_repair_without_deleting_data(
    postgres_engine: Engine,
    postgres_session: Session,
    integration_settings: Settings,
) -> None:
    _seed_catalog(postgres_session)
    now = datetime.now(UTC)
    postgres_session.add(
        User(
            anonymous_token_digest=_role_digest("supported-01"),
            consent_version=PERSONALIZATION_CONSENT_VERSION,
            consented_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=1),
            revoked_at=None,
        )
    )
    postgres_session.commit()

    with pytest.raises(ScenarioControlError) as partial:
        _controller(postgres_engine, integration_settings).create_cohort(scenario=SCENARIO_NAME)

    assert partial.value.code == "scenario_incomplete"
    assert postgres_session.scalar(select(func.count()).select_from(User)) == 1


def test_database_guards_fail_before_any_scenario_write(
    postgres_engine: Engine,
    postgres_session: Session,
    integration_settings: Settings,
) -> None:
    unsafe_controls = (
        _controller(
            postgres_engine,
            integration_settings,
            allow_test_reset=None,
        ),
        _controller(
            postgres_engine,
            integration_settings,
            process_environment="development",
        ),
        _controller(
            postgres_engine,
            integration_settings.model_copy(update={"environment": "development"}),
        ),
    )
    for controller in unsafe_controls:
        with pytest.raises(ScenarioControlError) as refused:
            controller.create_cohort(scenario=SCENARIO_NAME)
        assert refused.value.code == "unsafe_test_database"

    expected_url = make_url(integration_settings.database_url)
    alternate_host = "localhost" if expected_url.host != "localhost" else "test-db"
    mismatched_settings = integration_settings.model_copy(
        update={"database_url": expected_url.set(host=alternate_host).render_as_string(False)}
    )
    with pytest.raises(ScenarioControlError) as mismatched:
        _controller(postgres_engine, mismatched_settings).create_cohort(scenario=SCENARIO_NAME)
    assert mismatched.value.code == "database_connection_mismatch"
    assert postgres_session.scalar(select(func.count()).select_from(User)) == 0


def test_public_consent_does_not_grant_contribution_and_private_controls_are_repeatable(
    postgres_engine: Engine,
    postgres_session: Session,
    integration_settings: Settings,
) -> None:
    _seed_catalog(postgres_session)
    controller = _controller(postgres_engine, integration_settings)
    controller.create_cohort(scenario=SCENARIO_NAME)

    with TestClient(create_app(integration_settings)) as client:
        consent = client.post(
            "/api/v1/anonymous-sessions",
            headers={"Origin": "http://testserver"},
            json={"consent": True, "consent_version": PERSONALIZATION_CONSENT_VERSION},
        )
        assert consent.status_code == 201
        raw_token = client.cookies.get(integration_settings.anonymous_session_cookie_name)
        assert raw_token is not None
        raw_digest = session_token_digest(
            integration_settings.anonymous_session_secret,
            raw_token,
        )

        postgres_session.rollback()
        assert (
            postgres_session.scalar(
                select(func.count()).select_from(CollaborativeContributionConsent)
            )
            == 17
        )
        public_user = postgres_session.scalar(
            select(User).where(User.anonymous_token_digest == raw_digest)
        )
        assert public_user is not None
        public_user.consent_version = OUTDATED_PERSONALIZATION_CONSENT_VERSION
        public_user.consented_at = datetime.now(UTC) - timedelta(days=1)
        postgres_session.commit()

        lifecycle = client.get("/api/v1/me")
        assert lifecycle.status_code == 200
        assert lifecycle.json()["status"] == "consent_outdated"
        reconsented = client.post(
            "/api/v1/anonymous-sessions",
            headers={
                "Origin": "http://testserver",
                integration_settings.csrf_header_name: lifecycle.json()["csrf_token"],
            },
            json={"consent": True, "consent_version": PERSONALIZATION_CONSENT_VERSION},
        )
        assert reconsented.status_code == 200

        postgres_session.rollback()
        assert (
            postgres_session.scalar(
                select(func.count()).select_from(CollaborativeContributionConsent)
            )
            == 17
        )

    linked = _run_scenario_cli("link-session", private_input=raw_token)
    linked_again = controller.link_session(scenario=SCENARIO_NAME, raw_token=raw_token)
    assert linked["status"] == "updated"
    assert linked_again["status"] == "unchanged"

    outdated = _run_scenario_cli(
        "arrange-outdated-consent",
        private_input=raw_token,
    )
    outdated_again = controller.arrange_outdated_consent(
        scenario=SCENARIO_NAME,
        raw_token=raw_token,
    )
    assert outdated["status"] == "updated"
    assert outdated_again["status"] == "unchanged"

    withdrawn = _run_scenario_cli(
        "withdraw-contribution",
        private_input=raw_token,
    )
    withdrawn_again = controller.withdraw_contribution(
        scenario=SCENARIO_NAME,
        raw_token=raw_token,
    )
    assert withdrawn["status"] == "updated"
    assert withdrawn_again["status"] == "unchanged"
    for result in (linked, linked_again, outdated, outdated_again, withdrawn, withdrawn_again):
        _assert_private_output(result, raw_token, raw_digest)

    postgres_session.rollback()
    contribution = postgres_session.scalar(
        select(CollaborativeContributionConsent)
        .join(User, User.id == CollaborativeContributionConsent.user_id)
        .where(User.anonymous_token_digest == raw_digest)
    )
    assert contribution is not None
    assert contribution.withdrawn_at is not None
    controlled_user = postgres_session.scalar(
        select(User).where(User.anonymous_token_digest == raw_digest)
    )
    assert controlled_user is not None
    assert controlled_user.consent_version == OUTDATED_PERSONALIZATION_CONSENT_VERSION

    inspected = controller.inspect(scenario=SCENARIO_NAME)
    assert inspected["cohort"]["contribution_rows"] == 18  # type: ignore[index]
    assert inspected["cohort"]["withdrawn_contribution_rows"] == 1  # type: ignore[index]
    _assert_private_output(inspected, raw_token, raw_digest)


def test_inspection_performs_bounded_registry_and_event_assertions(
    postgres_engine: Engine,
    postgres_session: Session,
    integration_settings: Settings,
) -> None:
    _seed_catalog(postgres_session)
    controller = _controller(postgres_engine, integration_settings)
    controller.create_cohort(scenario=SCENARIO_NAME)
    user_id = postgres_session.scalar(
        select(User.id).where(User.anonymous_token_digest == _role_digest("supported-01"))
    )
    assert user_id is not None
    now = datetime.now(UTC)
    postgres_session.add(
        CollaborativeArtifactBuild(
            build_id="stage8b-inspection-build-v1",
            source_kind="live",
            status="active",
            registered_revision=1,
            invalidation_epoch=0,
            expected_contributor_count=1,
            current_contributor_count=0,
            consent_version=CONTRIBUTION_CONSENT_VERSION,
            catalog_fingerprint="a" * 64,
            interaction_fingerprint="b" * 64,
            cutoff=now - timedelta(days=1),
            valid_until=now + timedelta(days=1),
            invalidated_at=None,
            retired_at=None,
        )
    )
    postgres_session.add(
        RecommendationEvent(
            user_id=user_id,
            generation_id="stage8b-inspection-generation-v1",
            event_schema_version="stage-5-v1",
            model_name="gamelens-content-tfidf",
            model_version="1.0.0",
            data_fingerprint="c" * 64,
            ranking_policy_name="gamelens-feedback-adjustment",
            ranking_policy_version="1.0.0",
            ranking_mode="stage_4_fallback",
            fallback_reason="artifact_missing",
            hybrid_policy_name=None,
            hybrid_policy_version=None,
            collaborative_model_name=None,
            collaborative_model_version=None,
            collaborative_interaction_fingerprint=None,
            collaborative_policy_name=None,
            collaborative_policy_version=None,
            request_context={
                "ranking_mode": "stage_4_fallback",
                "fallback_reason": "artifact_missing",
            },
            result_summary=[],
        )
    )
    postgres_session.commit()

    result = controller.inspect(
        scenario=SCENARIO_NAME,
        expected_build_id="stage8b-inspection-build-v1",
        expected_build_status="active",
        expected_generation_id="stage8b-inspection-generation-v1",
        expected_ranking_mode="stage_4_fallback",
    )
    assert result["registry"] == {
        "total": 1,
        "by_status": {"active": 1},
        "expected_status_matches": True,
    }
    assert result["events"] == {
        "stage_5_total": 1,
        "by_ranking_mode": {"stage_4_fallback": 1},
        "expected_mode_matches": True,
    }
    _assert_private_output(result)

    with pytest.raises(ScenarioControlError) as mismatch:
        controller.inspect(
            scenario=SCENARIO_NAME,
            expected_build_id="stage8b-inspection-build-v1",
            expected_build_status="retired",
        )
    assert mismatch.value.code == "scenario_assertion_failed"


def test_private_cli_exposes_no_credential_argument() -> None:
    command = [
        sys.executable,
        "-m",
        "tests.fixtures.collaborative_lifecycle",
        "link-session",
        "--help",
    ]

    completed = subprocess.run(command, check=False, capture_output=True, text=True)

    assert completed.returncode == 0
    assert "--scenario" in completed.stdout
    assert "token" not in completed.stdout.casefold()
    assert "credential" not in completed.stdout.casefold()

    missing_target_environment = os.environ.copy()
    missing_target_environment.pop("GAMELENS_TEST_DATABASE_URL", None)
    refused = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.fixtures.collaborative_lifecycle",
            "create-cohort",
            "--scenario",
            SCENARIO_NAME,
        ],
        env=missing_target_environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert refused.returncode == 2
    assert refused.stderr == ""
    assert json.loads(refused.stdout) == {
        "error": {
            "code": "test_database_required",
            "message": "GAMELENS_TEST_DATABASE_URL is required; no fallback database is allowed",
        },
        "status": "error",
    }
    assert "gamelens_test_only" not in refused.stdout
