from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Literal, cast

import pytest
from app.core.config import Settings
from app.db.base import Base
from app.db.seed import load_seed_file, seed_database
from app.main import create_app
from app.repositories.collaborative_registry import CollaborativeArtifactRegistryRepository
from app.repositories.recommendation_catalog import RecommendationCatalogRepository
from app.services.recommendation import (
    CollaborativeArtifactComponent,
    CollaborativeReadinessRow,
    create_recommendation_service,
)
from fastapi.testclient import TestClient
from gamelens_recommender import LoadedCollaborativeArtifact, build_artifact
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BUILD_ID = "stage5-status-live-v1"
CONSENT_VERSION = "stage-5-contribution-v1"
INTERACTION_FINGERPRINT = "b" * 64
CUTOFF = datetime(2026, 8, 29, 11, tzinfo=UTC)
VALID_UNTIL = datetime(2099, 9, 29, 12, tzinfo=UTC)


@contextmanager
def _ready_client(settings: Settings, artifact_root: Path) -> Generator[TestClient]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        seed_database(session, load_seed_file())
        snapshot = RecommendationCatalogRepository(session).load().model_snapshot
    assert snapshot is not None
    artifact = build_artifact(snapshot, artifact_root / "status-content-v1")
    app = create_app(
        settings,
        database_engine=engine,
        database_health_check=lambda _engine: True,
        recommendation_service=create_recommendation_service(artifact),
    )
    with TestClient(app) as client:
        yield client


def _loaded_component(
    source_kind: Literal["fixture", "live"],
    *,
    catalog_fingerprint: str,
    contributor_count: int = 12,
) -> CollaborativeArtifactComponent:
    manifest = {
        "source": {"kind": source_kind},
        "build": {"id": BUILD_ID},
        "lifecycle": {
            "data_revision": 7 if source_kind == "live" else None,
            "consent_version": CONSENT_VERSION if source_kind == "live" else None,
            "cutoff": (
                CUTOFF.isoformat(timespec="microseconds").replace("+00:00", "Z")
                if source_kind == "live"
                else None
            ),
            "valid_until": VALID_UNTIL.isoformat(timespec="microseconds").replace("+00:00", "Z"),
        },
        "catalog_fingerprint": catalog_fingerprint,
        "interaction_fingerprint": INTERACTION_FINGERPRINT,
        "matrix": {
            "retained_contributors": contributor_count,
            "retained_positive_edges": 36,
            "retained_items": 6,
        },
        "thresholds": {
            "activation_minimum_users": 10,
            "activation_minimum_edges": 20,
            "activation_minimum_items": 5,
        },
    }
    artifact = cast(LoadedCollaborativeArtifact, SimpleNamespace(manifest=manifest))
    return CollaborativeArtifactComponent.loaded(artifact, source_kind=source_kind)


def _lineage(catalog_fingerprint: str) -> CollaborativeReadinessRow:
    return CollaborativeReadinessRow(
        build_id=BUILD_ID,
        source_kind="live",
        status="active",
        registered_revision=7,
        invalidation_epoch=0,
        contributor_count=12,
        consent_version=CONSENT_VERSION,
        catalog_fingerprint=catalog_fingerprint,
        interaction_fingerprint=INTERACTION_FINGERPRINT,
        cutoff=CUTOFF,
        valid_until=VALID_UNTIL,
    )


def _expected_content_status(client: TestClient) -> dict[str, object]:
    with client.app.state.session_factory() as session:
        catalog = RecommendationCatalogRepository(session).load()
    status = client.app.state.recommendation_service.status(
        catalog.model_snapshot,
        catalog_error=catalog.model_unavailable_reason,
    )
    return status.model_dump(mode="json", exclude_unset=True)


@pytest.mark.parametrize(
    ("case", "expected_collaborative"),
    [
        (
            "not_configured",
            {"status": "not_configured", "reason": "not_configured", "source_kind": None},
        ),
        (
            "unavailable",
            {"status": "unavailable", "reason": "artifact_missing", "source_kind": None},
        ),
        (
            "fixture_only",
            {"status": "fixture_only", "reason": None, "source_kind": "fixture"},
        ),
        (
            "insufficient_data",
            {
                "status": "insufficient_data",
                "reason": "insufficient_data",
                "source_kind": "fixture",
            },
        ),
        (
            "stale",
            {"status": "stale", "reason": "catalog_stale", "source_kind": "fixture"},
        ),
        (
            "ready",
            {"status": "ready", "reason": None, "source_kind": "live"},
        ),
    ],
)
def test_status_serializes_every_collaborative_state_without_changing_content(
    test_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    expected_collaborative: dict[str, object],
) -> None:
    settings = test_settings.model_copy(
        update={
            "collaborative_live_data_enabled": True,
            "collaborative_contribution_consent_version": CONSENT_VERSION,
        }
    )
    with _ready_client(settings, tmp_path / case) as client:
        fingerprint = client.app.state.recommendation_service.artifact.data_fingerprint
        if case == "not_configured":
            component = CollaborativeArtifactComponent.not_configured()
        elif case == "unavailable":
            component = CollaborativeArtifactComponent.unavailable("artifact_missing")
        elif case == "fixture_only":
            component = _loaded_component("fixture", catalog_fingerprint=fingerprint)
        elif case == "insufficient_data":
            component = _loaded_component(
                "fixture",
                catalog_fingerprint=fingerprint,
                contributor_count=9,
            )
        elif case == "stale":
            component = _loaded_component("fixture", catalog_fingerprint="f" * 64)
        else:
            component = _loaded_component("live", catalog_fingerprint=fingerprint)
        client.app.state.collaborative_component = component

        if case == "ready":
            monkeypatch.setattr(
                CollaborativeArtifactRegistryRepository,
                "readiness",
                lambda _repository, build_id: (
                    _lineage(fingerprint) if build_id == BUILD_ID else None
                ),
            )
        else:
            monkeypatch.setattr(
                CollaborativeArtifactRegistryRepository,
                "readiness",
                lambda _repository, _build_id: pytest.fail(
                    "non-live component status must not query lifecycle state"
                ),
            )

        expected_content = _expected_content_status(client)
        response = client.get("/api/v1/models/status")

    assert response.status_code == 200
    assert response.json() == {
        **expected_content,
        "components": {
            "content": {"status": "ready", "reason": None},
            "collaborative": expected_collaborative,
        },
    }


def test_collaborative_failure_cannot_turn_content_ready_into_an_outage(
    test_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = test_settings.model_copy(
        update={
            "collaborative_live_data_enabled": True,
            "collaborative_contribution_consent_version": CONSENT_VERSION,
        }
    )
    with _ready_client(settings, tmp_path) as client:
        fingerprint = client.app.state.recommendation_service.artifact.data_fingerprint
        client.app.state.collaborative_component = _loaded_component(
            "live", catalog_fingerprint=fingerprint
        )
        monkeypatch.setattr(
            CollaborativeArtifactRegistryRepository,
            "readiness",
            lambda _repository, _build_id: (_ for _ in ()).throw(RuntimeError("optional failure")),
        )

        response = client.get("/api/v1/models/status")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["capabilities"] == {"recommend": True, "explanations": True}
    assert response.json()["components"]["collaborative"] == {
        "status": "stale",
        "reason": "artifact_incompatible",
        "source_kind": "live",
    }


def test_stateless_recommendation_does_not_query_collaborative_lifecycle(
    test_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = test_settings.model_copy(
        update={
            "collaborative_live_data_enabled": True,
            "collaborative_contribution_consent_version": CONSENT_VERSION,
        }
    )
    with _ready_client(settings, tmp_path) as client:
        fingerprint = client.app.state.recommendation_service.artifact.data_fingerprint
        client.app.state.collaborative_component = _loaded_component(
            "live", catalog_fingerprint=fingerprint
        )
        monkeypatch.setattr(
            CollaborativeArtifactRegistryRepository,
            "readiness",
            lambda _repository, _build_id: pytest.fail(
                "stateless recommendation must not query lifecycle state"
            ),
        )

        response = client.post(
            "/api/v1/recommendations",
            json={"preferred_genres": ["strategy"], "top_k": 3},
        )

    assert response.status_code == 200
    assert response.json()["items"]


def test_openapi_exposes_only_the_additive_bounded_component_contract(
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    with _ready_client(test_settings, tmp_path) as client:
        schema = client.get("/openapi.json").json()

    model_status = schema["components"]["schemas"]["ModelStatusResponse"]
    components = schema["components"]["schemas"]["ModelComponentsStatus"]
    collaborative = schema["components"]["schemas"]["CollaborativeComponentStatus"]
    assert model_status["required"] == ["status", "active_model", "capabilities"]
    assert model_status["properties"]["components"]["anyOf"][0]["$ref"].endswith(
        "/ModelComponentsStatus"
    )
    assert components["required"] == ["content", "collaborative"]
    assert collaborative["required"] == ["status", "reason", "source_kind"]
    assert collaborative["properties"]["status"]["enum"] == [
        "not_configured",
        "fixture_only",
        "insufficient_data",
        "unavailable",
        "stale",
        "ready",
    ]
    assert collaborative["properties"]["reason"]["anyOf"][0]["enum"] == [
        "not_configured",
        "fixture_not_allowed",
        "insufficient_data",
        "artifact_missing",
        "artifact_corrupt",
        "artifact_incompatible",
        "artifact_stale",
        "privacy_invalid",
        "artifact_expired",
        "catalog_stale",
        "artifact_retired",
    ]
