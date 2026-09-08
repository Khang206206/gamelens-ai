from pathlib import Path

import yaml
from app.core.config import PROJECT_ROOT

COMPOSE_PATH = PROJECT_ROOT / "infra" / "docker-compose.e2e.yml"
RUNNER_PATH = PROJECT_ROOT / "infra" / "run-e2e-fixture.sh"
ARTIFACT_SET = "/tmp/gamelens-e2e/artifact-set"
EVIDENCE = "/tmp/gamelens-e2e/evidence"


def _compose() -> dict[str, object]:
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def test_fallback_artifacts_are_disposable_validated_copies() -> None:
    services = _compose()["services"]
    preparation = services["e2e-fallback-artifacts"]

    assert preparation["profiles"] == ["fallback"]
    assert preparation["read_only"] is True
    assert preparation.get("user") != "root"
    assert preparation["depends_on"] == {
        "e2e-collaborative-validate": {"condition": "service_completed_successfully"}
    }
    assert preparation["volumes"] == [f"e2e_artifact_set:{ARTIFACT_SET}"]
    assert preparation["command"][-1] == "prepare-fallback"

    helper = (
        PROJECT_ROOT / "apps" / "api" / "tests" / "fixtures" / "e2e_fixture_stack.py"
    ).read_text(encoding="utf-8")
    for name in (
        "collaborative-fixture-corrupt",
        "collaborative-fixture-expired",
        "collaborative-fixture-catalog-mismatch",
    ):
        assert name in helper
    assert "artifact_integrity_failed" in helper
    assert "artifact_expired" in helper
    assert "catalog_mismatch" in helper


def test_fallback_api_recreates_one_read_only_optional_component() -> None:
    services = _compose()["services"]
    api = services["e2e-fallback-api"]

    assert api["profiles"] == ["fallback"]
    assert api["read_only"] is True
    assert api["volumes"] == [f"e2e_artifact_set:{ARTIFACT_SET}:ro"]
    assert api["environment"]["MODEL_ARTIFACT_PATH"].startswith(
        "${E2E_FALLBACK_CONTENT_ARTIFACT_PATH:-"
    )
    assert api["environment"]["COLLABORATIVE_ARTIFACT_PATH"] == ("${E2E_FALLBACK_ARTIFACT_PATH:-}")
    assert api["environment"]["COLLABORATIVE_ALLOW_TEST_FIXTURE"] == (
        "${E2E_FALLBACK_ALLOW_TEST_FIXTURE:-false}"
    )
    assert api["environment"]["COLLABORATIVE_LIVE_DATA_ENABLED"] == "false"
    assert api["environment"]["COLLABORATIVE_CONTRIBUTION_CONSENT_VERSION"] == ""
    assert api["environment"]["COLLABORATIVE_LIVE_PROMOTION_ENABLED"] == "false"
    assert "ports" not in api

    web = services["e2e-fallback-web"]
    assert web["network_mode"] == "service:e2e-fallback-api"
    assert web["depends_on"] == {"e2e-fallback-api": {"condition": "service_healthy"}}
    assert "ports" not in web


def test_fallback_probes_cover_api_event_oracle_and_required_content_boundaries() -> None:
    services = _compose()["services"]
    probe = services["e2e-fallback-probe"]

    assert probe["read_only"] is True
    assert probe["volumes"] == [f"e2e_artifact_set:{ARTIFACT_SET}:ro"]
    assert "@test-db:5432/gamelens_e2e_test" in probe["environment"]["DATABASE_URL"]
    assert probe["environment"]["FALLBACK_API_URL"] == "http://e2e-fallback-api:8000"
    assert probe["command"][-1] == "fallback"

    runner = RUNNER_PATH.read_text(encoding="utf-8")
    for reason in (
        "not_configured",
        "artifact_missing",
        "artifact_corrupt",
        "artifact_expired",
        "catalog_stale",
        "fixture_not_allowed",
        "no_supported_sources",
    ):
        assert f"run_fallback_scenario {reason}" in runner
    assert "required-content" in runner
    assert runner.count("scenario_compose up --detach --wait --force-recreate --no-deps") == 4
    assert "e2e-fallback-api >&2" in runner
    assert "e2e-fallback-web >&2" in runner
    assert "scenario_compose rm --stop --force e2e-fallback-web e2e-fallback-api" in runner


def test_non_test_fixture_rejection_uses_valid_explicit_security_settings() -> None:
    services = _compose()["services"]
    development = services["e2e-fixture-development-rejection"]
    production = services["e2e-fixture-production-rejection"]

    assert development["environment"]["ENVIRONMENT"] == "development"
    assert development["environment"]["CORS_ORIGINS"] == "http://localhost:3000"
    assert development["environment"]["ANONYMOUS_SESSION_COOKIE_SECURE"] == "false"
    assert production["environment"]["ENVIRONMENT"] == "production"
    assert production["environment"]["CORS_ORIGINS"].startswith("https://")
    assert production["environment"]["ANONYMOUS_SESSION_COOKIE_SECURE"] == "true"
    for service in (development, production):
        assert service["read_only"] is True
        assert service["environment"]["COLLABORATIVE_ALLOW_TEST_FIXTURE"] == "false"
        assert service["volumes"] == [f"e2e_artifact_set:{ARTIFACT_SET}:ro"]
        assert service["command"][-1] == "environment-rejection"


def test_fallback_browser_services_receive_only_public_and_bounded_evidence_inputs() -> None:
    services = _compose()["services"]

    browser = services["e2e-fallback-browser"]
    smoke = services["e2e-fallback-smoke"]
    for service in (browser, smoke):
        assert service["profiles"] == ["fallback"]
        assert service["environment"]["WEB_BASE_URL"] == "http://gamelens.test:3000"
        assert service["environment"]["STAGE4_ORACLE_API_URL"] == ("http://gamelens.test:8000")
        assert service["environment"]["COLLABORATIVE_FALLBACK_E2E"] == "1"
        assert service["environment"]["STAGE5_EVENT_EVIDENCE_DIR"] == EVIDENCE
        assert service["volumes"] == [f"e2e_test_evidence:{EVIDENCE}"]
        assert "DATABASE_URL" not in service["environment"]
        assert "ANONYMOUS_SESSION_SECRET" not in service["environment"]
    assert "--project=chromium" in browser["command"][-1]
    assert "e2e/fallback.fixture.spec.ts" in browser["command"][-1]
    assert "--project=firefox-smoke --project=webkit-smoke" in smoke["command"][-1]
    assert "e2e/fallback.fixture.smoke.spec.ts" in smoke["command"][-1]


def test_fallback_runner_prepares_recreates_and_tears_down_only_its_project() -> None:
    runner = RUNNER_PATH.read_text(encoding="utf-8")

    assert '--project-name "$project"' in runner
    assert "--profile fixture --profile fallback" in runner
    assert "MSYS_NO_PATHCONV=1" in runner
    assert "compose run --rm --no-deps e2e-fallback-artifacts" in runner
    assert "e2e-fixture-development-rejection" in runner
    assert "e2e-fixture-production-rejection" in runner
    assert ". infra/e2e-ownership.sh" in runner
    assert "trap cleanup EXIT" in runner
    assert "docker system prune" not in runner
    assert "docker volume prune" not in runner
    assert str(Path("data") / "external") not in runner
