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
        model_artifact_path=tmp_path / "configured-content",
        collaborative_artifact_path=tmp_path / "configured-collaborative",
        collaborative_fixture_path=tmp_path / "fixture.json",
        database_url="postgresql+psycopg://test:test@localhost:5432/gamelens",
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


def test_enabled_live_promotion_requires_explicit_build_id_and_confirmation(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, live_promotion_enabled=True)

    with pytest.raises(collaborative_artifact.CollaborativeArtifactCommandError) as caught:
        collaborative_artifact.build_live_artifact(
            settings,
            tmp_path / "artifact",
            build_id=None,
            confirmation=None,
        )

    assert caught.value.code == "build_id_required"

    with pytest.raises(collaborative_artifact.CollaborativeArtifactCommandError) as confirmation:
        collaborative_artifact.build_live_artifact(
            settings,
            tmp_path / "artifact",
            build_id="stage5-live-v1",
            confirmation="different-build",
        )

    assert confirmation.value.code == "live_build_confirmation_required"


def test_confirmed_live_build_uses_one_disposed_database_engine(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, live_promotion_enabled=True)
    received: list[tuple[Path, object, str]] = []

    class _Engine:
        disposed = False

        def dispose(self) -> None:
            self.disposed = True

    engine = _Engine()

    class _Service:
        def __init__(self, factory: object) -> None:
            assert factory == "session-factory"

        def build(
            self,
            output: Path,
            *,
            settings: object,
            build_id: str,
        ) -> dict[str, object]:
            received.append((output, settings, build_id))
            return {"status": "valid"}

    monkeypatch.setattr(collaborative_artifact, "create_database_engine", lambda _url: engine)
    monkeypatch.setattr(
        collaborative_artifact,
        "create_session_factory",
        lambda _engine: "session-factory",
    )
    monkeypatch.setattr(collaborative_artifact, "CollaborativeLiveBuildService", _Service)

    result = collaborative_artifact.build_live_artifact(
        settings,
        tmp_path / "artifact",
        build_id="stage5-live-v1",
        confirmation="stage5-live-v1",
    )

    assert result == {"status": "valid"}
    assert received == [(tmp_path / "artifact", settings, "stage5-live-v1")]
    assert engine.disposed is True


def test_live_build_command_passes_exact_operator_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path, live_promotion_enabled=True)
    output = tmp_path / "live-artifact"
    received: list[tuple[Path, str | None, str | None]] = []
    monkeypatch.setattr(collaborative_artifact, "get_settings", lambda: settings)
    monkeypatch.setattr(
        collaborative_artifact,
        "build_live_artifact",
        lambda _settings, path, *, build_id, confirmation: (
            received.append((path, build_id, confirmation)) or {"status": "valid"}
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "collaborative-artifact",
            "build",
            "--source",
            "live",
            "--output",
            str(output),
            "--build-id",
            "stage5-live-v1",
            "--confirm-live-build",
            "stage5-live-v1",
        ],
    )

    collaborative_artifact.main()

    assert received == [(output, "stage5-live-v1", "stage5-live-v1")]
    assert json.loads(capsys.readouterr().out) == {"status": "valid"}


def test_live_build_command_confirmation_failure_is_stable_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        collaborative_artifact,
        "get_settings",
        lambda: _settings(tmp_path, live_promotion_enabled=True),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "collaborative-artifact",
            "build",
            "--build-id",
            "stage5-live-v1",
        ],
    )

    with pytest.raises(SystemExit, match="2"):
        collaborative_artifact.main()

    assert json.loads(capsys.readouterr().out) == {
        "status": "error",
        "error": {
            "code": "live_build_confirmation_required",
            "message": (
                "Live collaborative promotion requires --confirm-live-build to match --build-id"
            ),
        },
    }


def test_live_recovery_requires_exact_build_confirmation_before_database_access(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, live_promotion_enabled=True)
    monkeypatch.setattr(
        collaborative_artifact,
        "create_database_engine",
        lambda _url: pytest.fail("confirmation must fail before database access"),
    )

    with pytest.raises(collaborative_artifact.CollaborativeArtifactCommandError) as missing:
        collaborative_artifact.recover_live_artifact(
            settings,
            tmp_path / "artifact",
            build_id=None,
            confirmation=None,
        )
    with pytest.raises(collaborative_artifact.CollaborativeArtifactCommandError) as mismatch:
        collaborative_artifact.recover_live_artifact(
            settings,
            tmp_path / "artifact",
            build_id="stage5-live-v1",
            confirmation="different-build",
        )

    assert missing.value.code == "build_id_required"
    assert mismatch.value.code == "live_recovery_confirmation_required"


def test_live_recovery_command_passes_exact_artifact_and_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = _settings(tmp_path, live_promotion_enabled=True)
    artifact = tmp_path / "orphan-artifact"
    received: list[tuple[Path, str | None, str | None]] = []
    monkeypatch.setattr(collaborative_artifact, "get_settings", lambda: settings)
    monkeypatch.setattr(
        collaborative_artifact,
        "recover_live_artifact",
        lambda _settings, path, *, build_id, confirmation: (
            received.append((path, build_id, confirmation))
            or {"status": "valid", "promotion": {"recovery": "orphan_registered"}}
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "collaborative-artifact",
            "recover",
            "--artifact",
            str(artifact),
            "--build-id",
            "stage5-live-v1",
            "--confirm-live-recovery",
            "stage5-live-v1",
        ],
    )

    collaborative_artifact.main()

    assert received == [(artifact, "stage5-live-v1", "stage5-live-v1")]
    assert json.loads(capsys.readouterr().out)["promotion"]["recovery"] == ("orphan_registered")


@pytest.mark.parametrize("operation", ["invalidate", "retire"])
def test_lifecycle_mutation_requires_exact_confirmation_before_database_access(
    operation: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(
        collaborative_artifact,
        "create_database_engine",
        lambda _url: pytest.fail("confirmation must fail before database access"),
    )

    with pytest.raises(collaborative_artifact.CollaborativeArtifactCommandError) as missing:
        collaborative_artifact.mutate_live_artifact_lifecycle(
            settings,
            operation=operation,  # type: ignore[arg-type]
            build_id=None,
            confirmation=None,
        )
    with pytest.raises(collaborative_artifact.CollaborativeArtifactCommandError) as mismatch:
        collaborative_artifact.mutate_live_artifact_lifecycle(
            settings,
            operation=operation,  # type: ignore[arg-type]
            build_id="stage5-live-v1",
            confirmation="different-build",
        )

    assert missing.value.code == "build_id_required"
    assert mismatch.value.code == f"live_{operation}_confirmation_required"


def test_confirmed_lifecycle_mutation_disposes_its_database_engine(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    received: list[tuple[str, str]] = []

    class _Engine:
        disposed = False

        def dispose(self) -> None:
            self.disposed = True

    engine = _Engine()

    class _Service:
        def __init__(self, factory: object) -> None:
            assert factory == "session-factory"

        def mutate(self, *, operation: str, build_id: str) -> dict[str, object]:
            received.append((operation, build_id))
            return {"status": "ok"}

    monkeypatch.setattr(collaborative_artifact, "create_database_engine", lambda _url: engine)
    monkeypatch.setattr(
        collaborative_artifact,
        "create_session_factory",
        lambda _engine: "session-factory",
    )
    monkeypatch.setattr(collaborative_artifact, "CollaborativeLifecycleService", _Service)

    result = collaborative_artifact.mutate_live_artifact_lifecycle(
        settings,
        operation="invalidate",
        build_id="stage5-live-v1",
        confirmation="stage5-live-v1",
    )

    assert result == {"status": "ok"}
    assert received == [("invalidate", "stage5-live-v1")]
    assert engine.disposed is True


@pytest.mark.parametrize(
    ("operation", "confirmation_flag"),
    [
        ("invalidate", "--confirm-invalidation"),
        ("retire", "--confirm-retirement"),
    ],
)
def test_lifecycle_command_passes_exact_operation_build_and_confirmation(
    operation: str,
    confirmation_flag: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    received: list[tuple[str, str | None, str | None]] = []
    monkeypatch.setattr(collaborative_artifact, "get_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(
        collaborative_artifact,
        "mutate_live_artifact_lifecycle",
        lambda _settings, *, operation, build_id, confirmation: (
            received.append((operation, build_id, confirmation))
            or {"status": "ok", "operation": operation}
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "collaborative-artifact",
            operation,
            "--build-id",
            "stage5-live-v1",
            confirmation_flag,
            "stage5-live-v1",
        ],
    )

    collaborative_artifact.main()

    assert received == [(operation, "stage5-live-v1", "stage5-live-v1")]
    assert json.loads(capsys.readouterr().out) == {
        "status": "ok",
        "operation": operation,
    }


def test_retirement_preview_requires_explicit_artifact_set_before_database_access(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(
        collaborative_artifact,
        "create_database_engine",
        lambda _url: pytest.fail("artifact-set validation must precede database access"),
    )

    with pytest.raises(collaborative_artifact.CollaborativeArtifactCommandError) as caught:
        collaborative_artifact.preview_collaborative_retirement(
            settings,
            artifact_set=None,
        )

    assert caught.value.code == "artifact_set_required"


def test_retirement_preview_resolves_database_identity_and_disposes_engine(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    artifact_set = tmp_path / "artifact-set"
    received: list[tuple[Path, str, Path, Path]] = []

    class _Engine:
        disposed = False

        def dispose(self) -> None:
            self.disposed = True

    engine = _Engine()

    class _Service:
        def __init__(self, factory: object) -> None:
            assert factory == "session-factory"

        def preview(
            self,
            path: Path,
            *,
            database_fingerprint: str,
            configured_content_artifact: Path,
            configured_collaborative_artifact: Path,
        ) -> dict[str, object]:
            received.append(
                (
                    path,
                    database_fingerprint,
                    configured_content_artifact,
                    configured_collaborative_artifact,
                )
            )
            return {"status": "ok", "operation": "retirement_preview"}

    monkeypatch.setattr(collaborative_artifact, "create_database_engine", lambda _url: engine)
    monkeypatch.setattr(
        collaborative_artifact,
        "resolve_database_identity",
        lambda received_engine, _url: (
            SimpleNamespace(fingerprint="a" * 12)
            if received_engine is engine
            else pytest.fail("unexpected engine")
        ),
    )
    monkeypatch.setattr(
        collaborative_artifact,
        "create_session_factory",
        lambda _engine: "session-factory",
    )
    monkeypatch.setattr(collaborative_artifact, "CollaborativeRetirementPreviewService", _Service)

    result = collaborative_artifact.preview_collaborative_retirement(
        settings,
        artifact_set=artifact_set,
    )

    assert result == {"status": "ok", "operation": "retirement_preview"}
    assert received == [
        (
            artifact_set,
            "a" * 12,
            settings.model_artifact_path,
            settings.collaborative_artifact_path,
        )
    ]
    assert engine.disposed is True


def test_retirement_preview_command_passes_exact_artifact_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifact_set = tmp_path / "artifact-set"
    received: list[Path | None] = []
    monkeypatch.setattr(collaborative_artifact, "get_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(
        collaborative_artifact,
        "preview_collaborative_retirement",
        lambda _settings, *, artifact_set: (
            received.append(artifact_set) or {"status": "ok", "operation": "retirement_preview"}
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "collaborative-artifact",
            "retirement-preview",
            "--artifact-set",
            str(artifact_set),
        ],
    )

    collaborative_artifact.main()

    assert received == [artifact_set]
    assert json.loads(capsys.readouterr().out) == {
        "status": "ok",
        "operation": "retirement_preview",
    }


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
