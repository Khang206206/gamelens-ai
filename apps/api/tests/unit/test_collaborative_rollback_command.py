import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from app.commands import collaborative_artifact as command
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
