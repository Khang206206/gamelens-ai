import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.commands import collaborative_artifact


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        environment="development",
        database_url="postgresql+psycopg://test:test@localhost:5432/gamelens",
        model_artifact_path=tmp_path / "content",
        collaborative_artifact_path=tmp_path / "configured",
    )


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"artifact_set": None}, "recovery_target_required"),
        ({"target": None}, "recovery_target_required"),
        ({"execute": True}, "recovery_confirmation_required"),
        ({"confirmation": "exact"}, "recovery_execution_required"),
        ({"execute": True, "confirmation": "exact"}, "recovery_writers_not_stopped"),
        (
            {"execute": True, "confirmation": "exact", "writers_stopped": True},
            "development_database_protected",
        ),
    ],
)
def test_recovery_requires_explicit_safe_inputs_before_database_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changes: dict, code: str
) -> None:
    arguments = {
        "artifact_set": tmp_path,
        "target": tmp_path / "candidate",
        "kind": "build",
        **changes,
    }
    monkeypatch.setattr(
        collaborative_artifact,
        "create_database_engine",
        lambda _url: pytest.fail("unexpected database access"),
    )

    with pytest.raises(collaborative_artifact.CollaborativeArtifactCommandError) as caught:
        collaborative_artifact.recover_collaborative_files(_settings(tmp_path), **arguments)

    assert caught.value.code == code


@pytest.mark.parametrize("identity_failure", [False, True])
def test_recovery_preview_resolves_database_identity_and_always_disposes_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, identity_failure: bool
) -> None:
    settings = _settings(tmp_path)
    engine = Mock()
    service = Mock()
    service.recover.return_value = {"status": "ok", "operation": "recovery_preview"}
    resolver = Mock(
        side_effect=RuntimeError("database unavailable") if identity_failure else None,
        return_value=SimpleNamespace(fingerprint="a" * 12),
    )
    monkeypatch.setattr(collaborative_artifact, "create_database_engine", lambda _url: engine)
    monkeypatch.setattr(collaborative_artifact, "create_session_factory", lambda _engine: "factory")
    monkeypatch.setattr(collaborative_artifact, "resolve_database_identity", resolver)
    monkeypatch.setattr(
        collaborative_artifact, "CollaborativeArtifactRecoveryService", lambda _factory: service
    )
    arguments = {"artifact_set": tmp_path, "target": tmp_path / "candidate", "kind": "build"}

    if identity_failure:
        with pytest.raises(collaborative_artifact.CollaborativeArtifactCommandError) as caught:
            collaborative_artifact.recover_collaborative_files(settings, **arguments)
        assert caught.value.code == "recovery_database_identity_failed"
        service.recover.assert_not_called()
    else:
        result = collaborative_artifact.recover_collaborative_files(settings, **arguments)
        assert result["operation"] == "recovery_preview"
        service.recover.assert_called_once_with(
            tmp_path,
            target=tmp_path / "candidate",
            kind="build",
            database_fingerprint="a" * 12,
            configured_content_artifact=settings.model_artifact_path,
            configured_collaborative_artifact=settings.collaborative_artifact_path,
            confirmation=None,
            writers_stopped=False,
        )
    resolver.assert_called_once_with(engine, settings.database_url)
    engine.dispose.assert_called_once_with()


@pytest.mark.parametrize("execute", [False, True])
def test_recover_files_cli_preserves_explicit_preview_and_execution_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    execute: bool,
) -> None:
    settings = _settings(tmp_path)
    operation = "recovery_cleanup" if execute else "recovery_preview"
    recover = Mock(return_value={"status": "ok", "operation": operation})
    target = tmp_path / "candidate"
    confirmation = "RECOVER COLLABORATIVE exact"
    argv = [
        "collaborative-artifact",
        "recover-files",
        "--artifact-set",
        str(tmp_path),
        "--target",
        str(target),
        "--kind",
        "build",
    ]
    if execute:
        argv.extend(["--execute", "--writers-stopped", "--confirm-recovery", confirmation])
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(collaborative_artifact, "get_settings", lambda: settings)
    monkeypatch.setattr(collaborative_artifact, "recover_collaborative_files", recover)

    collaborative_artifact.main()

    recover.assert_called_once_with(
        settings,
        artifact_set=tmp_path,
        target=target,
        kind="build",
        execute=execute,
        confirmation=confirmation if execute else None,
        writers_stopped=execute,
    )
    assert json.loads(capsys.readouterr().out) == {"status": "ok", "operation": operation}
