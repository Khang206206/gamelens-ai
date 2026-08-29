import logging
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from app.commands.collaborative_artifact import build_fixture_artifact
from app.core.config import PROJECT_ROOT, Settings
from app.main import create_app
from app.services.recommendation import (
    CollaborativeArtifactComponent,
    RecommendationService,
    create_collaborative_component,
)
from app.services.recommendation import collaborative as collaborative_module
from fastapi.testclient import TestClient
from gamelens_recommender import CollaborativeArtifactError, LoadedCollaborativeArtifact

FIXTURE_PATH = (
    PROJECT_ROOT / "data" / "fixtures" / "interactions" / "collaborative-interactions.json"
)
CATALOG_PATH = PROJECT_ROOT / "data" / "catalog" / "games.json"


def _fake_artifact(source_kind: str = "live") -> LoadedCollaborativeArtifact:
    return cast(
        LoadedCollaborativeArtifact,
        SimpleNamespace(manifest={"source": {"kind": source_kind}}),
    )


def _build_guarded_fixture(
    test_settings: Settings,
    target: Path,
) -> Path:
    fixture_settings = test_settings.model_copy(
        update={
            "collaborative_allow_test_fixture": True,
            "collaborative_artifact_path": target,
        }
    )
    build_fixture_artifact(
        fixture_settings,
        target,
        fixture_path=FIXTURE_PATH,
        catalog_path=CATALOG_PATH,
        built_at=datetime.now(UTC),
    )
    return target


def test_unconfigured_component_is_immutable_and_does_not_touch_the_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        collaborative_module,
        "load_collaborative_artifact",
        lambda *_args, **_kwargs: pytest.fail("unconfigured component must not load a bundle"),
    )

    component = create_collaborative_component(
        None,
        environment="development",
        allow_test_fixture=False,
    )

    assert component.load_state == "not_configured"
    assert component.source_kind is None
    assert component.unavailable_reason is None
    assert component.artifact is None
    with pytest.raises(FrozenInstanceError):
        component.load_state = "loaded"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("loader_code", "expected_reason"),
    [
        ("fixture_not_allowed", "fixture_not_allowed"),
        ("artifact_missing", "artifact_missing"),
        ("artifact_expired", "artifact_expired"),
        ("manifest_invalid", "artifact_corrupt"),
        ("artifact_integrity_failed", "artifact_corrupt"),
        ("artifact_schema_incompatible", "artifact_incompatible"),
        ("code_incompatible", "artifact_incompatible"),
        ("catalog_mismatch", "catalog_stale"),
        ("artifact_stale_revision", "artifact_stale"),
        ("consent_policy_incompatible", "privacy_invalid"),
        ("future_unknown_code", "artifact_incompatible"),
    ],
)
def test_loader_errors_are_normalized_without_exposing_details(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    loader_code: str,
    expected_reason: str,
) -> None:
    private_path = tmp_path / "private-collaborative-location"

    def fail_loader(*_args: object, **_kwargs: object) -> LoadedCollaborativeArtifact:
        raise CollaborativeArtifactError(loader_code, f"sensitive detail at {private_path}")

    monkeypatch.setattr(collaborative_module, "load_collaborative_artifact", fail_loader)
    caplog.set_level(logging.WARNING, logger=collaborative_module.__name__)

    component = create_collaborative_component(
        private_path,
        environment="development",
        allow_test_fixture=False,
    )

    assert component.load_state == "unavailable"
    assert component.unavailable_reason == expected_reason
    assert component.source_kind is None
    assert component.artifact is None
    assert str(private_path) not in repr(component)
    assert str(private_path) not in caplog.text


@pytest.mark.parametrize(
    ("error", "expected_reason"),
    [
        (FileNotFoundError("private missing path"), "artifact_missing"),
        (ValueError("private malformed payload"), "artifact_corrupt"),
        (RuntimeError("private construction failure"), "artifact_incompatible"),
    ],
)
def test_unexpected_loader_failures_cannot_break_required_content_construction(
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
    tmp_path: Path,
    error: Exception,
    expected_reason: str,
) -> None:
    content_service = cast(RecommendationService, object())

    def fail_loader(*_args: object, **_kwargs: object) -> LoadedCollaborativeArtifact:
        raise error

    monkeypatch.setattr(collaborative_module, "load_collaborative_artifact", fail_loader)
    settings = test_settings.model_copy(
        update={"collaborative_artifact_path": tmp_path / "configured-collaborative"}
    )

    app = create_app(settings, recommendation_service=content_service)

    assert app.state.recommendation_service is content_service
    assert app.state.collaborative_component.load_state == "unavailable"
    assert app.state.collaborative_component.unavailable_reason == expected_reason


def test_fixture_bundle_requires_both_test_environment_and_explicit_gate(
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    artifact_path = _build_guarded_fixture(test_settings, tmp_path / "fixture-artifact")

    for environment, allow_fixture in (
        ("development", True),
        ("production", True),
        ("test", False),
    ):
        rejected = create_collaborative_component(
            artifact_path,
            environment=environment,
            allow_test_fixture=allow_fixture,
        )
        assert rejected.load_state == "unavailable"
        assert rejected.unavailable_reason == "fixture_not_allowed"

    loaded = create_collaborative_component(
        artifact_path,
        environment="test",
        allow_test_fixture=True,
    )
    assert loaded.load_state == "loaded"
    assert loaded.source_kind == "fixture"
    assert loaded.unavailable_reason is None
    assert loaded.artifact is not None
    assert str(artifact_path) not in repr(loaded)


def test_app_constructs_the_component_once_and_never_hot_reloads(
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "configured-live-artifact"
    artifact = _fake_artifact()
    calls: list[tuple[Path, bool]] = []

    def load_once(path: Path, *, allow_fixture: bool) -> LoadedCollaborativeArtifact:
        calls.append((path, allow_fixture))
        return artifact

    monkeypatch.setattr(collaborative_module, "load_collaborative_artifact", load_once)
    settings = test_settings.model_copy(update={"collaborative_artifact_path": artifact_path})
    app = create_app(settings, database_health_check=lambda _engine: True)

    assert calls == [(artifact_path, False)]
    assert app.state.collaborative_component.artifact is artifact
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health").status_code == 200

    assert calls == [(artifact_path, False)]


def test_explicit_component_injection_skips_the_configured_loader(
    monkeypatch: pytest.MonkeyPatch,
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    injected = CollaborativeArtifactComponent.not_configured()
    monkeypatch.setattr(
        collaborative_module,
        "load_collaborative_artifact",
        lambda *_args, **_kwargs: pytest.fail("injected component must bypass loading"),
    )
    settings = test_settings.model_copy(
        update={"collaborative_artifact_path": tmp_path / "configured-collaborative"}
    )

    app = create_app(settings, collaborative_component=injected)

    assert app.state.collaborative_component is injected
