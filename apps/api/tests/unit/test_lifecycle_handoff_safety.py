from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.conftest import pytest_collection_modifyitems as apply_collection_guard


def test_broad_collection_skips_database_lifecycle_tests_without_explicit_opt_in() -> None:
    config = Mock()
    config.getoption.return_value = False
    ordinary = SimpleNamespace(keywords={}, add_marker=Mock())
    lifecycle = SimpleNamespace(keywords={"integration": True}, add_marker=Mock())
    apply_collection_guard(config, [ordinary, lifecycle])
    config.getoption.assert_called_once_with("--run-integration")
    ordinary.add_marker.assert_not_called()
    marker = lifecycle.add_marker.call_args.args[0]
    assert marker.name == "skip"
    assert "disposable" in marker.kwargs["reason"]


def test_lifecycle_only_collection_refuses_implicit_database_reset() -> None:
    config = Mock()
    config.getoption.return_value = False
    lifecycle = SimpleNamespace(keywords={"integration": True}, add_marker=Mock())
    with pytest.raises(pytest.UsageError, match="require --run-integration"):
        apply_collection_guard(config, [lifecycle])
    lifecycle.add_marker.assert_not_called()
