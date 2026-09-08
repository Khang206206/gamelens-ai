from pathlib import Path

import yaml
from app.core.config import PROJECT_ROOT

COMPOSE_PATH = PROJECT_ROOT / "infra" / "docker-compose.e2e.yml"
RUNNER_PATH = PROJECT_ROOT / "infra" / "run-e2e-lifecycle.sh"
ARTIFACT_SET = "/tmp/gamelens-e2e/artifact-set"
EVIDENCE = "/tmp/gamelens-e2e/lifecycle-evidence"
CURRENT = f"{ARTIFACT_SET}/collaborative-lifecycle-current-v1"
DATABASE = "postgresql+psycopg://gamelens_e2e:gamelens_e2e_only@test-db:5432/gamelens_e2e_test"


def _compose() -> dict[str, object]:
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def test_lifecycle_services_are_explicit_live_only_and_guarded() -> None:
    services = _compose()["services"]
    lifecycle = {
        name: service for name, service in services.items() if name.startswith("e2e-lifecycle-")
    }

    assert set(lifecycle) == {
        "e2e-lifecycle-evidence-init",
        "e2e-lifecycle-control",
        "e2e-lifecycle-api",
        "e2e-lifecycle-web",
        "e2e-lifecycle-browser",
    }
    assert all(service["profiles"] == ["lifecycle"] for service in lifecycle.values())
    for name in ("e2e-lifecycle-control", "e2e-lifecycle-api"):
        environment = services[name]["environment"]
        assert environment["DATABASE_URL"] == DATABASE
        assert environment["COLLABORATIVE_LIVE_DATA_ENABLED"] == "true"
        assert environment["COLLABORATIVE_ALLOW_TEST_FIXTURE"] == "false"
        assert environment["COLLABORATIVE_CONTRIBUTION_CONSENT_VERSION"] == (
            "stage-5-contribution-v1"
        )

    assert (
        services["e2e-lifecycle-control"]["environment"]["COLLABORATIVE_LIVE_PROMOTION_ENABLED"]
        == "true"
    )
    assert (
        services["e2e-lifecycle-api"]["environment"]["COLLABORATIVE_LIVE_PROMOTION_ENABLED"]
        == "false"
    )
    assert "GAMELENS_ALLOW_TEST_DATABASE_RESET" not in services["e2e-lifecycle-api"]["environment"]


def test_lifecycle_browser_state_is_private_and_api_artifacts_are_read_only() -> None:
    services = _compose()["services"]
    init = services["e2e-lifecycle-evidence-init"]
    browser = services["e2e-lifecycle-browser"]
    control = services["e2e-lifecycle-control"]
    api = services["e2e-lifecycle-api"]

    assert init["user"] == "root"
    assert init["volumes"] == [f"e2e_lifecycle_evidence:{EVIDENCE}"]
    assert "chown --no-dereference 1001:1000" in init["command"][-1]
    assert "chmod 0770" in init["command"][-1]
    assert browser["user"] == "1001:1000"
    assert "umask 007" in browser["command"][-1]
    assert browser["volumes"] == [f"e2e_lifecycle_evidence:{EVIDENCE}"]
    assert control["read_only"] is True
    assert control["tmpfs"] == ["/tmp:mode=1777"]
    assert control["environment"]["COLLABORATIVE_ARTIFACT_PATH"] == CURRENT
    assert f"e2e_artifact_set:{ARTIFACT_SET}" in control["volumes"]
    assert api["read_only"] is True
    assert api["volumes"] == [f"e2e_artifact_set:{ARTIFACT_SET}:ro"]
    assert "ports" not in api


def test_lifecycle_runner_serializes_fresh_scenarios_and_operator_recreation() -> None:
    runner = RUNNER_PATH.read_text(encoding="utf-8")
    compose = COMPOSE_PATH.read_text(encoding="utf-8")
    makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
    root_compose = yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

    assert '--project-name "$project"' in runner
    assert "--profile lifecycle" in runner
    assert "--profile fixture" not in runner
    assert "--profile live-source" not in runner
    assert "--workers=1 --retries=0" in compose
    assert '--project="$${STAGE8G_BROWSER_PROJECT}"' in compose
    assert runner.count("run_scenario ") == 6
    for scenario in (
        "preference-removal",
        "feedback-removal",
        "contribution-withdrawal",
        "clear-data",
        "reconsent",
    ):
        assert scenario in runner
    assert "browser_phase previous" in runner
    assert "--force-recreate --no-deps" in runner
    assert "private-transition regrant-contribution" in runner
    assert "control operator-cleanup" in runner
    assert runner.count("control audit") >= 2
    assert ". infra/e2e-ownership.sh" in runner
    assert "trap cleanup EXIT" in runner
    assert "docker system prune" not in runner
    assert "docker volume prune" not in runner
    assert str(Path("data") / "external") not in runner
    assert "test-e2e-lifecycle:" in makefile
    assert "sh infra/run-e2e-lifecycle.sh" in makefile
    assert (
        root_compose["services"]["quality"]["volumes"].count(
            "./infra/run-e2e-lifecycle.sh:/workspace/infra/run-e2e-lifecycle.sh:ro"
        )
        == 1
    )


def test_lifecycle_proof_uses_real_public_requests_and_private_aggregate_assertions() -> None:
    helper = (PROJECT_ROOT / "apps" / "api" / "tests" / "fixtures" / "e2e_lifecycle.py").read_text(
        encoding="utf-8"
    )

    assert "CollaborativeArtifactContributor" in helper
    assert 'code="rollback_candidate_not_ready"' in helper
    assert 'code="revision_race"' in helper
    assert 'code="cleanup_confirmation_mismatch"' in helper
    assert "path.unlink(missing_ok=False)" in helper
