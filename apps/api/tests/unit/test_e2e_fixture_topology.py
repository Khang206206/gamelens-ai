import yaml
from app.core.config import PROJECT_ROOT

COMPOSE_PATH = PROJECT_ROOT / "infra" / "docker-compose.e2e.yml"
ARTIFACT_SET = "/tmp/gamelens-e2e/artifact-set"
EVENT_EVIDENCE = "/tmp/gamelens-e2e/evidence"


def _compose() -> dict[str, object]:
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def test_fixture_topology_uses_guarded_database_and_fresh_artifact_set() -> None:
    services = _compose()["services"]

    database = services["test-db"]
    assert database["environment"]["POSTGRES_DB"] == "gamelens_e2e_test"
    assert database["tmpfs"] == ["/var/lib/postgresql/data"]
    assert "ports" not in database

    setup = services["e2e-setup"]
    assert "@test-db:5432/gamelens_e2e_test" in setup["environment"]["DATABASE_URL"]
    assert setup["depends_on"] == {"test-db": {"condition": "service_healthy"}}

    owner_init = services["e2e-artifact-init"]
    assert owner_init["user"] == "root"
    assert owner_init["volumes"] == [f"e2e_artifact_set:{ARTIFACT_SET}"]
    assert "find" in owner_init["command"][-1]
    assert "chown --no-dereference gamelens:gamelens" in owner_init["command"][-1]


def test_fixture_builders_and_validators_are_explicit_and_non_root() -> None:
    services = _compose()["services"]

    for builder in ("e2e-model", "e2e-collaborative-model"):
        service = services[builder]
        assert service["read_only"] is True
        assert service.get("user") != "root"
        assert 'id -u)" -ne 0' in service["command"][-1]
        assert service["volumes"] == [f"e2e_artifact_set:{ARTIFACT_SET}"]

    content_validator = services["e2e-model-validate"]
    collaborative_validator = services["e2e-collaborative-validate"]
    for validator in (content_validator, collaborative_validator):
        assert validator["read_only"] is True
        assert validator["volumes"] == [f"e2e_artifact_set:{ARTIFACT_SET}:ro"]
        assert "validate" in validator["command"]
    assert content_validator["depends_on"] == {
        "e2e-model": {"condition": "service_completed_successfully"}
    }
    assert collaborative_validator["depends_on"] == {
        "e2e-collaborative-model": {"condition": "service_completed_successfully"}
    }


def test_fixture_api_waits_for_both_artifacts_and_cannot_write_them() -> None:
    services = _compose()["services"]
    api = services["e2e-fixture-api"]

    assert api["profiles"] == ["fixture"]
    assert api["depends_on"] == {
        "e2e-model-validate": {"condition": "service_completed_successfully"},
        "e2e-collaborative-validate": {"condition": "service_completed_successfully"},
    }
    assert api["read_only"] is True
    assert api["volumes"] == [f"e2e_artifact_set:{ARTIFACT_SET}:ro"]
    assert api["environment"]["COLLABORATIVE_ALLOW_TEST_FIXTURE"] == "true"
    assert api["environment"]["COLLABORATIVE_LIVE_DATA_ENABLED"] == "false"
    assert api["environment"]["COLLABORATIVE_CONTRIBUTION_CONSENT_VERSION"] == ""
    assert api["environment"]["COLLABORATIVE_LIVE_PROMOTION_ENABLED"] == "false"
    assert "ports" not in api

    web = services["e2e-fixture-web"]
    assert web["profiles"] == ["fixture"]
    assert web["network_mode"] == "service:e2e-fixture-api"
    assert "ports" not in web

    browser = services["e2e-fixture"]
    assert browser["profiles"] == ["fixture"]
    assert browser["depends_on"] == {
        "e2e-fixture-web": {"condition": "service_healthy"},
        "e2e-test-evidence-init": {"condition": "service_completed_successfully"},
    }
    assert browser["environment"]["WEB_BASE_URL"] == "http://gamelens.test:3000"
    assert browser["environment"]["COLLABORATIVE_FIXTURE_E2E"] == "1"
    assert browser["environment"]["STAGE5_EVENT_EVIDENCE_DIR"] == EVENT_EVIDENCE
    assert browser["volumes"] == [f"e2e_test_evidence:{EVENT_EVIDENCE}"]
    assert "--workers=1 --retries=0 --project=chromium" in browser["command"][-1]
    assert "e2e/hybrid.fixture.spec.ts" in browser["command"][-1]
    assert "--project=firefox-smoke" in browser["command"][-1]
    assert "--project=webkit-smoke e2e/hybrid.fixture.smoke.spec.ts" in browser["command"][-1]
    assert "ports" not in browser


def test_hybrid_event_evidence_stays_out_of_the_browser_database_boundary() -> None:
    services = _compose()["services"]

    evidence_init = services["e2e-test-evidence-init"]
    assert evidence_init["user"] == "root"
    assert evidence_init["volumes"] == [f"e2e_test_evidence:{EVENT_EVIDENCE}"]
    assert "find" in evidence_init["command"][-1]
    assert "chown --no-dereference 1001:1001" in evidence_init["command"][-1]
    assert "chmod 0755" in evidence_init["command"][-1]

    browser = services["e2e-fixture"]
    assert "DATABASE_URL" not in browser["environment"]
    assert "ANONYMOUS_SESSION_SECRET" not in browser["environment"]

    event_assertion = services["e2e-fixture-events"]
    assert event_assertion["read_only"] is True
    assert "@test-db:5432/gamelens_e2e_test" in event_assertion["environment"]["DATABASE_URL"]
    assert event_assertion["volumes"] == [f"e2e_test_evidence:{EVENT_EVIDENCE}:ro"]
    assert event_assertion["command"][-1] == "events"


def test_content_only_browser_route_remains_independent() -> None:
    services = _compose()["services"]

    assert services["e2e-api"]["environment"]["COLLABORATIVE_ARTIFACT_PATH"] == ""
    assert services["e2e-api"]["environment"]["COLLABORATIVE_ALLOW_TEST_FIXTURE"] == "false"
    assert services["e2e-web"]["depends_on"] == {"e2e-api": {"condition": "service_healthy"}}
    assert services["e2e"]["depends_on"] == {"e2e-web": {"condition": "service_healthy"}}


def test_api_image_allows_only_the_committed_collaborative_fixture_input() -> None:
    dockerfile = (PROJECT_ROOT / "apps" / "api" / "Dockerfile").read_text(encoding="utf-8")
    ignore = (PROJECT_ROOT / "apps" / "api" / "Dockerfile.dockerignore").read_text(encoding="utf-8")
    fixture = "data/fixtures/interactions/collaborative-interactions.json"

    assert fixture in dockerfile
    assert f"!{fixture}" in ignore
    assert "!data/fixtures/**" not in ignore
    assert "data/external" not in dockerfile


def test_fixture_runner_replays_fresh_volume_and_always_tears_down() -> None:
    runner = (PROJECT_ROOT / "infra" / "run-e2e-fixture.sh").read_text(encoding="utf-8")

    assert '--project-name "$project"' in runner
    assert "--profile fixture" in runner
    assert runner.count("start_fresh_stack") == 3
    assert runner.count("teardown") >= 4
    assert "down --volumes --remove-orphans" in runner
    assert "compose run --rm --no-deps e2e-test-evidence-init" in runner
    assert "e2e_fixture_stack runtime" in runner
    assert "compose run --rm --no-deps e2e-fixture" in runner
    assert "compose run --rm --no-deps e2e-fixture-events" in runner
    assert "e2e-fixture-immutability" in runner
