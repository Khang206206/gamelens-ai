import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.commands import collaborative_artifact


def _settings(tmp_path: Path, *, allow_fixture: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        environment="test" if allow_fixture else "development",
        collaborative_allow_test_fixture=allow_fixture,
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
    assert payload["error"]["code"] == "unapproved_live_source"


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
) -> None:
    settings = SimpleNamespace(
        environment="development",
        collaborative_allow_test_fixture=False,
        collaborative_artifact_path=None,
    )
    monkeypatch.setattr(collaborative_artifact, "get_settings", lambda: settings)
    monkeypatch.setattr(sys, "argv", ["collaborative-artifact", "inspect"])

    with pytest.raises(SystemExit, match="2"):
        collaborative_artifact.main()


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
