import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.commands import recommendation_artifact


def test_build_command_uses_configured_path_and_reports_catalog_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configured = tmp_path / "configured-artifact"
    received: list[Path] = []
    monkeypatch.setattr(
        recommendation_artifact,
        "get_settings",
        lambda: SimpleNamespace(model_artifact_path=configured),
    )
    monkeypatch.setattr(
        recommendation_artifact,
        "build",
        lambda path: received.append(path) or {"status": "valid"},
    )
    monkeypatch.setattr(sys, "argv", ["recommendation-artifact", "build"])

    recommendation_artifact.main()

    assert received == [configured]
    for reason, message in (
        ("catalog_stale", "empty catalog"),
        ("catalog_invalid", "invalid catalog"),
    ):
        catalog = SimpleNamespace(
            model_snapshot=None,
            model_unavailable_reason=reason,
        )
        with pytest.raises(ValueError, match=message):
            recommendation_artifact._buildable_snapshot(catalog)


def test_validate_command_explicit_path_overrides_configuration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    configured = tmp_path / "configured-artifact"
    explicit = tmp_path / "explicit-artifact"
    received: list[Path] = []
    monkeypatch.setattr(
        recommendation_artifact,
        "get_settings",
        lambda: SimpleNamespace(model_artifact_path=configured),
    )
    monkeypatch.setattr(
        recommendation_artifact,
        "inspect_artifact",
        lambda path: received.append(path) or {"status": "valid"},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["recommendation-artifact", "validate", "--artifact", str(explicit)],
    )

    recommendation_artifact.main()

    assert received == [explicit]


def test_command_rejects_missing_configured_and_explicit_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        recommendation_artifact,
        "get_settings",
        lambda: SimpleNamespace(model_artifact_path=None),
    )
    monkeypatch.setattr(sys, "argv", ["recommendation-artifact", "validate"])

    with pytest.raises(SystemExit, match="2"):
        recommendation_artifact.main()
