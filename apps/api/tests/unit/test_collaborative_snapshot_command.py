import json
import sys
from pathlib import Path

import pytest
from app.commands import collaborative_snapshot
from app.core.config import PROJECT_ROOT, Settings
from gamelens_recommender.interaction_snapshot import SnapshotAuditError

FIXTURE_PATH = (
    PROJECT_ROOT / "data" / "fixtures" / "interactions" / "collaborative-interactions.json"
)
CATALOG_PATH = PROJECT_ROOT / "data" / "catalog" / "games.json"


def _settings(**values: object) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        cors_origins=["http://testserver"],
        **values,
    )


def test_default_live_audit_is_blocked_without_database_access(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def unexpected_engine(_database_url: str):  # type: ignore[no-untyped-def]
        raise AssertionError("the default-off path must not create a database engine")

    monkeypatch.setattr(collaborative_snapshot, "create_database_engine", unexpected_engine)

    report = collaborative_snapshot.audit_live_source(_settings())

    assert report["status"] == "integration_blocked"
    assert report["reasons"] == ["unapproved_live_source"]
    assert report["approved_live_training_eligibility"] is False
    assert report["integration_gates"] == {
        "live_data_enabled": False,
        "contribution_consent_version_configured": False,
        "build_lineage_implemented": True,
        "live_promotion_enabled": False,
        "serving_activation_approved": False,
    }


def test_blocked_live_audit_reports_each_configured_gate_truthfully(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def unexpected_engine(_database_url: str):  # type: ignore[no-untyped-def]
        raise AssertionError("the disabled live path must not create a database engine")

    monkeypatch.setattr(collaborative_snapshot, "create_database_engine", unexpected_engine)

    report = collaborative_snapshot.audit_live_source(
        _settings(collaborative_contribution_consent_version="stage-5-contribution-v1")
    )

    assert report["status"] == "integration_blocked"
    assert report["integration_gates"]["live_data_enabled"] is False
    assert report["integration_gates"]["contribution_consent_version_configured"] is True
    assert report["integration_gates"]["build_lineage_implemented"] is True
    assert report["integration_gates"]["live_promotion_enabled"] is False
    assert report["integration_gates"]["serving_activation_approved"] is False


def test_promotion_enablement_is_reported_without_implying_approval() -> None:
    report = collaborative_snapshot.blocked_live_audit(
        live_data_enabled=False,
        contribution_consent_version_configured=False,
        live_promotion_enabled=True,
    )

    assert report["integration_gates"]["live_promotion_enabled"] is True
    assert report["integration_gates"]["serving_activation_approved"] is False
    assert report["approved_live_training_eligibility"] is False


def test_fixture_audit_requires_explicit_test_gate() -> None:
    with pytest.raises(SnapshotAuditError, match="explicit fixture access") as error:
        collaborative_snapshot.audit_fixture_source(
            _settings(),
            fixture_path=FIXTURE_PATH,
            catalog_path=CATALOG_PATH,
        )

    assert error.value.code == "fixture_not_allowed"


def test_fixture_audit_uses_exact_catalog_and_emits_no_row_snapshot() -> None:
    report = collaborative_snapshot.audit_fixture_source(
        _settings(collaborative_allow_test_fixture=True),
        fixture_path=FIXTURE_PATH,
        catalog_path=CATALOG_PATH,
    )

    assert report["source_kind"] == "fixture"
    assert report["ready_for_functional_build"] is True
    assert report["approved_live_training_eligibility"] is False
    assert report["privacy"]["row_level_snapshot_written"] is False
    assert report["catalog_fingerprint"] != "a" * 64


def test_fixture_audit_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SnapshotAuditError, match="strict JSON") as error:
        collaborative_snapshot.audit_fixture_source(
            _settings(collaborative_allow_test_fixture=True),
            fixture_path=tmp_path / "missing.json",
            catalog_path=CATALOG_PATH,
        )

    assert error.value.code == "fixture_invalid"


def test_blocked_audit_command_emits_one_successful_json_report(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(collaborative_snapshot, "get_settings", _settings)
    monkeypatch.setattr(
        sys,
        "argv",
        ["collaborative-snapshot", "audit", "--source", "live", "--format", "json"],
    )

    collaborative_snapshot.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "integration_blocked"
    assert payload["reasons"] == ["unapproved_live_source"]


def test_audit_command_failure_uses_stable_json_and_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(collaborative_snapshot, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        collaborative_snapshot,
        "audit_fixture_source",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            SnapshotAuditError("fixture_invalid", "fixture is invalid")
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["collaborative-snapshot", "audit", "--source", "fixture"],
    )

    with pytest.raises(SystemExit, match="2"):
        collaborative_snapshot.main()

    assert json.loads(capsys.readouterr().out) == {
        "status": "error",
        "error": {"code": "fixture_invalid", "message": "fixture is invalid"},
    }
