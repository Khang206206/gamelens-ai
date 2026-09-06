from pathlib import Path

import yaml
from app.core.config import PROJECT_ROOT

COMPOSE_PATH = PROJECT_ROOT / "infra" / "docker-compose.e2e.yml"
RUNNER_PATH = PROJECT_ROOT / "infra" / "run-e2e-live-source.sh"
ARTIFACT_SET = "/tmp/gamelens-e2e/artifact-set"
EVIDENCE = "/tmp/gamelens-e2e/live-evidence"
DATABASE = "postgresql+psycopg://gamelens_e2e:gamelens_e2e_only@test-db:5432/gamelens_e2e_test"
PREVIOUS = f"{ARTIFACT_SET}/collaborative-live-previous-v1"
CURRENT = f"{ARTIFACT_SET}/collaborative-live-current-v1"


def _compose() -> dict[str, object]:
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def test_live_source_mode_is_explicit_and_cannot_enable_the_fixture_gate() -> None:
    services = _compose()["services"]
    live_services = {
        name: service for name, service in services.items() if name.startswith("e2e-live-")
    }

    assert live_services
    assert all(service["profiles"] == ["live-source"] for service in live_services.values())
    for name, service in live_services.items():
        environment = service.get("environment")
        if environment is None:
            assert name == "e2e-live-evidence-init"
            continue
        assert environment["COLLABORATIVE_ALLOW_TEST_FIXTURE"] == "false"
        assert environment["COLLABORATIVE_LIVE_DATA_ENABLED"] == "true"
        assert environment["COLLABORATIVE_CONTRIBUTION_CONSENT_VERSION"] == (
            "stage-5-contribution-v1"
        )
        assert environment["DATABASE_URL"] == DATABASE

    assert services["e2e-collaborative-model"]["profiles"] == ["fixture"]
    assert (
        services["e2e-collaborative-model"]["environment"]["COLLABORATIVE_LIVE_DATA_ENABLED"]
        == "false"
    )


def test_live_source_sequence_is_a_single_fail_closed_dependency_chain() -> None:
    services = _compose()["services"]
    sequence = (
        ("e2e-live-evidence-init", "e2e-model-validate"),
        ("e2e-live-cohort", "e2e-live-evidence-init"),
        ("e2e-live-audit", "e2e-live-cohort"),
        ("e2e-live-guard-failures", "e2e-live-audit"),
        ("e2e-live-registration-failure", "e2e-live-guard-failures"),
        ("e2e-live-previous-recover", "e2e-live-registration-failure"),
        ("e2e-live-previous-validate", "e2e-live-previous-recover"),
        ("e2e-live-previous-inspect", "e2e-live-previous-validate"),
        ("e2e-live-revision", "e2e-live-previous-inspect"),
        ("e2e-live-current-model", "e2e-live-revision"),
        ("e2e-live-current-validate", "e2e-live-current-model"),
        ("e2e-live-current-inspect", "e2e-live-current-validate"),
        ("e2e-live-existing-target", "e2e-live-current-inspect"),
        ("e2e-live-rollback", "e2e-live-existing-target"),
        ("e2e-live-verify", "e2e-live-rollback"),
        ("e2e-live-api", "e2e-live-verify"),
    )
    for service_name, dependency_name in sequence:
        assert services[service_name]["depends_on"] == {
            dependency_name: {"condition": "service_completed_successfully"}
        }


def test_live_build_recovery_validation_inspection_and_rollback_are_explicit() -> None:
    services = _compose()["services"]
    recovery = services["e2e-live-previous-recover"]["command"][-1]
    current = services["e2e-live-current-model"]["command"][-1]
    previous_validate = services["e2e-live-previous-validate"]["command"][-1]
    previous_inspect = services["e2e-live-previous-inspect"]["command"][-1]
    current_validate = services["e2e-live-current-validate"]["command"][-1]
    current_inspect = services["e2e-live-current-inspect"]["command"][-1]
    rollback = services["e2e-live-rollback"]["command"][-1]

    assert "recover" in recovery
    assert f"--artifact {PREVIOUS}" in recovery
    assert "--build-id stage8f-live-previous-v1" in recovery
    assert "--confirm-live-recovery stage8f-live-previous-v1" in recovery
    assert 'id -u)" -ne 0' in current
    assert "build --source live" in current
    assert f"--output {CURRENT}" in current
    assert "--build-id stage8f-live-current-v1" in current
    assert "--confirm-live-build stage8f-live-current-v1" in current
    for command, artifact in (
        (previous_validate, PREVIOUS),
        (current_validate, CURRENT),
    ):
        assert "validate" in command
        assert f"--artifact {artifact}" in command
    for command, artifact in (
        (previous_inspect, PREVIOUS),
        (current_inspect, CURRENT),
    ):
        assert "inspect" in command
        assert f"--artifact {artifact}" in command
    assert "rollback-check" in rollback
    assert f"--artifact {PREVIOUS}" in rollback


def test_live_build_writers_and_api_have_narrow_volume_permissions() -> None:
    services = _compose()["services"]
    evidence_init = services["e2e-live-evidence-init"]
    assert evidence_init["user"] == "root"
    assert evidence_init["volumes"] == [f"e2e_live_evidence:{EVIDENCE}"]
    assert "find" in evidence_init["command"][-1]
    assert "chown --no-dereference gamelens:gamelens" in evidence_init["command"][-1]

    for name in (
        "e2e-live-registration-failure",
        "e2e-live-previous-recover",
        "e2e-live-current-model",
    ):
        service = services[name]
        assert service["read_only"] is True
        assert service.get("user") != "root"
        assert f"e2e_artifact_set:{ARTIFACT_SET}" in service["volumes"]

    for name in (
        "e2e-live-previous-validate",
        "e2e-live-previous-inspect",
        "e2e-live-current-validate",
        "e2e-live-current-inspect",
        "e2e-live-rollback",
        "e2e-live-verify",
    ):
        assert f"e2e_artifact_set:{ARTIFACT_SET}:ro" in services[name]["volumes"]

    api = services["e2e-live-api"]
    assert api["read_only"] is True
    assert api["volumes"] == [f"e2e_artifact_set:{ARTIFACT_SET}:ro"]
    assert api["environment"]["COLLABORATIVE_ARTIFACT_PATH"] == CURRENT
    assert api["environment"]["COLLABORATIVE_LIVE_PROMOTION_ENABLED"] == "false"
    assert "GAMELENS_ALLOW_TEST_DATABASE_RESET" not in api["environment"]
    assert "ports" not in api


def test_live_source_verification_precedes_api_selection_and_saved_http_smoke() -> None:
    services = _compose()["services"]
    verification = services["e2e-live-verify"]
    smoke = services["e2e-live-smoke"]

    assert verification["command"][-1] == "verify"
    assert verification["volumes"] == [
        f"e2e_artifact_set:{ARTIFACT_SET}:ro",
        f"e2e_live_evidence:{EVIDENCE}:ro",
    ]
    assert smoke["command"][-1] == "saved-hybrid"
    assert smoke["environment"]["LIVE_API_URL"] == "http://e2e-live-api:8000"
    assert smoke["environment"]["COLLABORATIVE_LIVE_PROMOTION_ENABLED"] == "false"
    assert smoke["volumes"] == [f"e2e_artifact_set:{ARTIFACT_SET}:ro"]
    assert not any("playwright" in str(value).casefold() for value in smoke.values())


def test_live_source_runner_uses_one_unique_project_and_always_tears_down() -> None:
    runner = RUNNER_PATH.read_text(encoding="utf-8")
    makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")

    assert '--project-name "$project"' in runner
    assert "--profile live-source" in runner
    assert "--profile fixture" not in runner
    assert "compose config --quiet" in runner
    assert "compose up --detach --wait e2e-live-api" in runner
    assert "compose run --rm --no-deps e2e-live-smoke" in runner
    assert runner.count("teardown") >= 3
    assert "down --volumes --remove-orphans" in runner
    assert "docker system prune" not in runner
    assert "docker volume prune" not in runner
    assert str(Path("data") / "external") not in runner
    assert "test-e2e-live-source:" in makefile
    assert "sh infra/run-e2e-live-source.sh" in makefile


def test_live_source_probe_uses_real_registry_rejection_and_privacy_checks() -> None:
    helper = (
        PROJECT_ROOT / "apps" / "api" / "tests" / "fixtures" / "e2e_live_source.py"
    ).read_text(encoding="utf-8")

    assert "CREATE TRIGGER" in helper
    assert "BEFORE INSERT ON collaborative_artifact_builds" in helper
    assert 'code="live_promotion_rejected"' in helper
    assert 'code="rollback_candidate_not_ready"' in helper
    assert 'code="unapproved_live_source"' in helper
    assert 'code="live_build_confirmation_required"' in helper
    assert 'code="artifact_target_exists"' in helper
    assert "synthetic_postgresql" in helper
    assert "_assert_artifact_privacy" in helper
