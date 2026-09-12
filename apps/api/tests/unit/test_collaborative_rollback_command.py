import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from app.commands import collaborative_artifact as command
from app.services import collaborative_rollback
from app.services.collaborative_rollback import CollaborativeRollbackError
from sqlalchemy.exc import SQLAlchemyError

from tests.unit.test_collaborative_artifact_command import _settings


def test_rollback_requires_explicit_path_before_database_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    engine_factory = Mock(side_effect=AssertionError("Database must not be accessed"))
    monkeypatch.setattr(command, "create_database_engine", engine_factory)
    monkeypatch.setattr(command, "get_settings", lambda: _settings(tmp_path))
    monkeypatch.setattr(sys, "argv", ["artifact", "rollback-check"])
    with pytest.raises(SystemExit) as error:
        command.main()
    assert error.value.code == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "artifact_path_required"
    engine_factory.assert_not_called()


@pytest.mark.parametrize("failure", [None, "candidate", "database"])
def test_rollback_dispatch_disposes_engine_and_emits_safe_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str | None,
) -> None:
    settings = _settings(tmp_path)  # Read-only checking needs no live-promotion opt-in.
    engine = Mock()
    factory = Mock()
    service = Mock()
    result = {"status": "ok", "operation": "rollback_check"}
    service.check.return_value = result
    if failure == "candidate":
        service.check.side_effect = CollaborativeRollbackError(
            "rollback_candidate_not_ready", "Rollback candidate is not ready: privacy_invalid"
        )
    elif failure == "database":
        service.check.side_effect = SQLAlchemyError("private database connection details")
    monkeypatch.setattr(command, "get_settings", lambda: settings)
    monkeypatch.setattr(command, "create_database_engine", lambda _url: engine)
    monkeypatch.setattr(command, "create_session_factory", lambda _engine: factory)
    constructor = Mock(return_value=service)
    monkeypatch.setattr(command, "CollaborativeRollbackService", constructor)
    path = tmp_path / "candidate"
    monkeypatch.setattr(sys, "argv", ["artifact", "rollback-check", "--artifact", str(path)])
    if failure:
        with pytest.raises(SystemExit) as error:
            command.main()
        assert error.value.code == 2
    else:
        command.main()
    output = capsys.readouterr().out
    payload = json.loads(output)
    if failure:
        assert payload["error"]["code"] == (
            "rollback_candidate_not_ready"
            if failure == "candidate"
            else "rollback_database_unavailable"
        )
    else:
        assert payload == result
    assert "private database connection details" not in output
    constructor.assert_called_once_with(factory)
    service.check.assert_called_once_with(path, settings=settings)
    engine.dispose.assert_called_once_with()


@pytest.mark.parametrize(
    "reason", [None, "privacy_invalid", "artifact_retired", "artifact_stale", "artifact_expired"]
)
def test_rollback_service_checks_read_only_and_never_changes_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reason: str | None
) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "marker").write_bytes(b"unchanged")
    settings = _settings(tmp_path)
    configured = settings.collaborative_artifact_path
    session = MagicMock()
    session.__enter__.return_value = session
    begin = Mock()
    artifact = SimpleNamespace(manifest={"build": {"id": "unit-rollback"}})
    component = Mock()
    resolver = Mock()
    resolver.resolve.return_value = SimpleNamespace(
        state="stale" if reason else "ready", reason=reason
    )
    monkeypatch.setattr(
        collaborative_rollback, "load_collaborative_artifact", Mock(return_value=artifact)
    )
    monkeypatch.setattr(
        collaborative_rollback,
        "CollaborativeArtifactComponent",
        Mock(loaded=Mock(return_value=component)),
    )
    monkeypatch.setattr(collaborative_rollback, "begin_repeatable_read", begin)
    monkeypatch.setattr(
        collaborative_rollback,
        "RecommendationCatalogRepository",
        Mock(
            return_value=Mock(
                load=Mock(
                    return_value=SimpleNamespace(
                        model_snapshot=SimpleNamespace(fingerprint="a" * 64)
                    )
                )
            )
        ),
    )
    monkeypatch.setattr(
        collaborative_rollback, "CollaborativeReadinessResolver", Mock(return_value=resolver)
    )
    service = collaborative_rollback.CollaborativeRollbackService(lambda: session)
    for _ in range(2):
        if reason:
            with pytest.raises(CollaborativeRollbackError) as caught:
                service.check(candidate, settings=settings)
            assert caught.value.code == "rollback_candidate_not_ready"
            assert str(caught.value) == f"Rollback candidate is not ready: {reason}"
        else:
            report = service.check(candidate, settings=settings)
            assert report["configuration_changed"] is False
            assert report["requires_manual_configuration_and_restart"] is True
    begin.assert_called_with(session, read_only=True)
    assert begin.call_count == 2
    assert session.rollback.call_count == 2
    assert session.__exit__.call_count == 2
    session.commit.assert_not_called()
    assert settings.collaborative_artifact_path == configured
    assert list(candidate.iterdir()) == [candidate / "marker"]
    assert (candidate / "marker").read_bytes() == b"unchanged"
