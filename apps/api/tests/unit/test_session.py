from unittest.mock import MagicMock, Mock

import pytest
from app.db.session import (
    EXPECTED_SCHEMA_REVISION,
    REQUIRED_SCHEMA_TABLES,
    database_is_ready,
    session_scope,
)
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session


def test_session_scope_never_auto_commits_and_always_closes() -> None:
    session = Mock(spec=Session)
    factory = Mock(return_value=session)
    dependency = session_scope(factory)

    assert next(dependency) is session
    with pytest.raises(StopIteration):
        next(dependency)

    session.commit.assert_not_called()
    session.rollback.assert_not_called()
    session.close.assert_called_once_with()


def test_session_scope_rolls_back_and_closes_on_failure() -> None:
    session = Mock(spec=Session)
    factory = Mock(return_value=session)
    dependency = session_scope(factory)
    next(dependency)

    with pytest.raises(RuntimeError, match="request failed"):
        dependency.throw(RuntimeError("request failed"))

    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()


def test_database_readiness_requires_tables_and_expected_revision() -> None:
    engine = MagicMock(spec=Engine)
    connection = engine.connect.return_value.__enter__.return_value
    connection.scalar.side_effect = [len(REQUIRED_SCHEMA_TABLES), True]

    assert database_is_ready(engine) is True
    assert connection.scalar.call_args_list[1].args[1] == {
        "expected_revision": EXPECTED_SCHEMA_REVISION
    }


def test_database_readiness_rejects_incomplete_schema() -> None:
    engine = MagicMock(spec=Engine)
    connection = engine.connect.return_value.__enter__.return_value
    connection.scalar.side_effect = [len(REQUIRED_SCHEMA_TABLES) - 1, True]

    assert database_is_ready(engine) is False


def test_database_readiness_controls_connection_errors() -> None:
    engine = MagicMock(spec=Engine)
    engine.connect.side_effect = OperationalError(
        "SELECT 1",
        {},
        RuntimeError("connection refused"),
    )

    assert database_is_ready(engine) is False
