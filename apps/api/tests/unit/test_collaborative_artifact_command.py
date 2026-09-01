import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.commands import collaborative_artifact
from app.core.config import PROJECT_ROOT

FIXTURE_PATH = (
    PROJECT_ROOT / "data" / "fixtures" / "interactions" / "collaborative-interactions.json"
)
CATALOG_PATH = PROJECT_ROOT / "data" / "catalog" / "games.json"


def _settings(
    tmp_path: Path,
    *,
    allow_fixture: bool = False,
    live_promotion_enabled: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        environment="test" if allow_fixture else "development",
        collaborative_allow_test_fixture=allow_fixture,
        collaborative_live_data_enabled=live_promotion_enabled,
        collaborative_contribution_consent_version=(
            "stage-5-contribution-v1" if live_promotion_enabled else None
        ),
        collaborative_live_promotion_enabled=live_promotion_enabled,
        collaborative_artifact_path=tmp_path / "configured-collaborative",
        collaborative_fixture_path=tmp_path / "fixture.json",
    )


def test_live_build_is_fail_closed_before_external_access(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(collaborative_artifact, "get_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(sys, "argv", ["collaborative-artifact", "build"])

    with pytest.raises(SystemExit, match="2"):
        collaborative_artifact.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "unapproved_live_source"
    assert payload["error"]["message"] == "Live collaborative promotion is disabled by default"


def test_enabled_live_promotion_does_not_bypass_later_approval_slices(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, live_promotion_enabled=True)

    with pytest.raises(collaborative_artifact.CollaborativeArtifactCommandError) as caught:
        collaborative_artifact.build_live_artifact(settings, tmp_path / "artifact")

    assert caught.value.code == "unapproved_live_source"
    assert "lineage-bound build and promotion slices" in str(caught.value)


def test_fixture_build_requires_both_test_environment_and_explicit_gate(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(collaborative_artifact.CollaborativeArtifactCommandError) as caught:
        collaborative_artifact.build_fixture_artifact(
            settings,
            tmp_path / "artifact",
            fixture_path=tmp_path / "fixture.json",
            catalog_path=tmp_path / "catalog.json",
        )

    assert caught.value.code == "fixture_not_allowed"


def test_fixture_build_command_uses_explicit_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path, allow_fixture=True)
    explicit_output = tmp_path / "explicit-artifact"
    explicit_fixture = tmp_path / "explicit-fixture.json"
    explicit_catalog = tmp_path / "explicit-catalog.json"
    received: list[tuple[Path, Path, Path]] = []
    monkeypatch.setattr(collaborative_artifact, "get_settings", lambda: settings)
    monkeypatch.setattr(
        collaborative_artifact,
        "build_fixture_artifact",
        lambda _settings, output, *, fixture_path, catalog_path: (
            received.append((output, fixture_path, catalog_path)) or {"status": "valid"}
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "collaborative-artifact",
            "build",
            "--source",
            "fixture",
            "--output",
            str(explicit_output),
            "--fixture",
            str(explicit_fixture),
            "--catalog",
            str(explicit_catalog),
        ],
    )

    collaborative_artifact.main()

    assert received == [(explicit_output, explicit_fixture, explicit_catalog)]
    assert json.loads(capsys.readouterr().out) == {"status": "valid"}


def test_fixture_build_rejects_audit_to_fit_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, allow_fixture=True)
    catalog = SimpleNamespace(
        fingerprint="a" * 64,
        items=(SimpleNamespace(slug="alpha"), SimpleNamespace(slug="beta")),
    )
    monkeypatch.setattr(collaborative_artifact, "catalog_from_seed", lambda _path: catalog)
    monkeypatch.setattr(
        collaborative_artifact,
        "audit_fixture",
        lambda *_args, **_kwargs: {
            "ready_for_functional_build": True,
            "interaction_fingerprint": "b" * 64,
            "fixture": {"contract_fingerprint": "c" * 64},
        },
    )
    monkeypatch.setattr(
        collaborative_artifact,
        "load_fixture",
        lambda *_args, **_kwargs: SimpleNamespace(
            profiles=(("alpha", "beta"),),
            contract_fingerprint="c" * 64,
        ),
    )

    with pytest.raises(collaborative_artifact.CollaborativeArtifactCommandError) as caught:
        collaborative_artifact.build_fixture_artifact(
            settings,
            tmp_path / "artifact",
            fixture_path=tmp_path / "fixture.json",
            catalog_path=tmp_path / "catalog.json",
        )

    assert caught.value.code == "fixture_changed"


def test_validate_and_inspect_are_read_only_loader_calls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path, allow_fixture=True)
    explicit = tmp_path / "artifact"
    explicit_catalog = tmp_path / "catalog.json"
    received: list[tuple[Path, bool, str]] = []
    catalog_paths: list[Path] = []
    monkeypatch.setattr(collaborative_artifact, "get_settings", lambda: settings)
    monkeypatch.setattr(
        collaborative_artifact,
        "catalog_from_seed",
        lambda path: catalog_paths.append(path) or SimpleNamespace(fingerprint="a" * 64),
    )
    monkeypatch.setattr(
        collaborative_artifact,
        "inspect_collaborative_artifact",
        lambda path, *, allow_fixture, expected_catalog_fingerprint: (
            received.append((path, allow_fixture, expected_catalog_fingerprint))
            or {"status": "valid"}
        ),
    )

    for command in ("validate", "inspect"):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "collaborative-artifact",
                command,
                "--artifact",
                str(explicit),
                "--catalog",
                str(explicit_catalog),
            ],
        )
        collaborative_artifact.main()
        assert json.loads(capsys.readouterr().out) == {"status": "valid"}

    assert catalog_paths == [explicit_catalog, explicit_catalog]
    assert received == [
        (explicit, True, "a" * 64),
        (explicit, True, "a" * 64),
    ]


def test_command_rejects_missing_configured_and_explicit_path(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = SimpleNamespace(
        environment="development",
        collaborative_allow_test_fixture=False,
        collaborative_live_promotion_enabled=False,
        collaborative_artifact_path=None,
    )
    monkeypatch.setattr(collaborative_artifact, "get_settings", lambda: settings)
    monkeypatch.setattr(sys, "argv", ["collaborative-artifact", "inspect"])

    with pytest.raises(SystemExit, match="2"):
        collaborative_artifact.main()

    assert json.loads(capsys.readouterr().out) == {
        "status": "error",
        "error": {
            "code": "artifact_path_required",
            "message": ("Configure COLLABORATIVE_ARTIFACT_PATH or pass an explicit artifact path"),
        },
    }


def test_fixture_build_id_is_deterministic_and_input_sensitive() -> None:
    values = {
        "fixture_id": "stage-5-fixture-v1",
        "fixture_contract_fingerprint": "a" * 64,
        "catalog_fingerprint": "b" * 64,
        "interaction_fingerprint": "c" * 64,
    }

    first = collaborative_artifact._fixture_build_id(**values)

    assert first == collaborative_artifact._fixture_build_id(**values)
    assert first.startswith("stage5-fixture-")
    assert first != collaborative_artifact._fixture_build_id(
        **{**values, "interaction_fingerprint": "d" * 64}
    )


def _bundle_snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in sorted(root.iterdir())
    }


def test_validate_and_inspect_are_idempotent_and_do_not_repair_or_mutate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path, allow_fixture=True)
    settings.collaborative_fixture_path = FIXTURE_PATH
    artifact = tmp_path / "artifact"
    collaborative_artifact.build_fixture_artifact(
        settings,
        artifact,
        fixture_path=FIXTURE_PATH,
        catalog_path=CATALOG_PATH,
        built_at=datetime.now(UTC),
    )
    before = _bundle_snapshot(artifact)
    monkeypatch.setattr(collaborative_artifact, "get_settings", lambda: settings)

    for command in ("validate", "inspect", "validate", "inspect"):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "collaborative-artifact",
                command,
                "--artifact",
                str(artifact),
                "--catalog",
                str(CATALOG_PATH),
            ],
        )
        collaborative_artifact.main()
        assert json.loads(capsys.readouterr().out)["status"] == "valid"

    assert _bundle_snapshot(artifact) == before


def test_invalid_settings_use_the_stable_command_error_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        collaborative_artifact,
        "get_settings",
        lambda: (_ for _ in ()).throw(ValueError("settings are invalid")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["collaborative-artifact", "inspect", "--artifact", str(tmp_path / "artifact")],
    )

    with pytest.raises(SystemExit, match="2"):
        collaborative_artifact.main()

    assert json.loads(capsys.readouterr().out) == {
        "status": "error",
        "error": {
            "code": "collaborative_artifact_failed",
            "message": "settings are invalid",
        },
    }
