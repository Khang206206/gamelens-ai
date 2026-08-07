from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
from app.core.config import Settings
from app.db.base import Base
from app.db.models import Game
from app.db.seed import load_seed_file, seed_database
from app.main import create_app
from app.repositories.recommendation_catalog import RecommendationCatalogRepository
from app.services.recommendation import create_recommendation_service
from app.services.recommendation.not_configured import NotConfiguredRecommendationService
from fastapi.testclient import TestClient
from gamelens_recommender import build_artifact
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@contextmanager
def ready_client(settings: Settings, artifact_root: Path) -> Generator[TestClient]:
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
    artifact = build_artifact(snapshot, artifact_root / "content-v1")
    app = create_app(
        settings,
        database_engine=engine,
        database_health_check=lambda _engine: True,
        recommendation_service=create_recommendation_service(artifact),
    )
    with TestClient(app) as client:
        yield client


@pytest.fixture
def recommendation_client(test_settings: Settings, tmp_path: Path) -> Generator[TestClient]:
    with ready_client(test_settings, tmp_path) as client:
        yield client


def test_ready_status_and_recommendation_contract(
    recommendation_client: TestClient,
) -> None:
    status = recommendation_client.get("/api/v1/models/status")
    catalog = recommendation_client.get(
        "/api/v1/games", params={"genre": "strategy", "page_size": 100}
    ).json()
    selected = catalog["items"][0]
    response = recommendation_client.post(
        "/api/v1/recommendations",
        json={
            "selected_game_ids": [selected["id"]],
            "preferred_genres": ["strategy"],
            "preferred_platforms": ["linux"],
            "top_k": 5,
        },
    )

    assert status.status_code == 200
    assert status.json()["status"] == "ready"
    assert status.json()["capabilities"] == {"recommend": True, "explanations": True}
    assert response.status_code == 200
    body = response.json()
    assert body["response_reason"] == "recommendations"
    assert 1 <= len(body["items"]) <= 5
    assert [item["rank"] for item in body["items"]] == list(range(1, len(body["items"]) + 1))
    assert all(item["game"]["id"] != selected["id"] for item in body["items"])
    for item in body["items"]:
        assert sum(component["contribution"] for component in item["components"]) == pytest.approx(
            item["ranking_score"], abs=0.000001
        )
        assert item["explanation"]["reasons"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"preferred_platforms": ["linux"]},
        {"preferred_genres": ["strategy", "strategy"]},
        {"preferred_genres": ["Invalid Slug"]},
        {"preferred_genres": ["strategy"], "top_k": 0},
        {"preferred_genres": ["strategy"], "top_k": 21},
        {"preferred_genres": ["strategy"], "unexpected": True},
    ],
)
def test_request_bounds_use_standard_error_envelope(
    recommendation_client: TestClient, payload: dict[str, object]
) -> None:
    response = recommendation_client.post("/api/v1/recommendations", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_unknown_references_are_controlled(recommendation_client: TestClient) -> None:
    unknown_game = recommendation_client.post(
        "/api/v1/recommendations", json={"selected_game_ids": [2_147_483_647]}
    )
    unknown_genre = recommendation_client.post(
        "/api/v1/recommendations", json={"preferred_genres": ["not-real"]}
    )
    assert unknown_game.status_code == 422
    assert unknown_game.json()["error"]["code"] == "unknown_game"
    assert unknown_genre.status_code == 422
    assert unknown_genre.json()["error"]["code"] == "unknown_genre"


def test_unconfigured_model_returns_503_before_loading_catalog(
    recommendation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recommendation_client.app.state.recommendation_service = NotConfiguredRecommendationService()
    monkeypatch.setattr(
        RecommendationCatalogRepository,
        "load",
        lambda _repository: pytest.fail("unconfigured service must not query the catalog"),
    )
    response = recommendation_client.post(
        "/api/v1/recommendations", json={"preferred_genres": ["not-in-the-database"]}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_not_configured"


def test_corrupt_artifact_is_safe_and_fails_before_loading_catalog(
    recommendation_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    corrupt_artifact = tmp_path / "private-model-location"
    corrupt_artifact.mkdir()
    (corrupt_artifact / "manifest.json").write_text("not-json", encoding="utf-8")
    service = create_recommendation_service(corrupt_artifact)
    recommendation_client.app.state.recommendation_service = service
    monkeypatch.setattr(
        RecommendationCatalogRepository,
        "load",
        lambda _repository: pytest.fail("intrinsically unavailable service must not query catalog"),
    )

    status = service.status()
    response = recommendation_client.post(
        "/api/v1/recommendations", json={"preferred_genres": ["not-in-the-database"]}
    )

    assert status.status == "unavailable"
    assert status.unavailable_reason == "manifest_invalid"
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "manifest_invalid"
    assert str(corrupt_artifact) not in response.text


def test_catalog_change_makes_loaded_artifact_stale(
    recommendation_client: TestClient,
) -> None:
    with recommendation_client.app.state.session_factory.begin() as session:
        game = session.scalar(select(Game).order_by(Game.id))
        assert game is not None
        game.description = f"{game.description} changed"

    status = recommendation_client.get("/api/v1/models/status")
    response = recommendation_client.post(
        "/api/v1/recommendations", json={"preferred_genres": ["strategy"]}
    )
    assert status.json()["status"] == "unavailable"
    assert status.json()["unavailable_reason"] == "catalog_stale"
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "catalog_stale"


def test_empty_catalog_is_controlled_catalog_stale(
    recommendation_client: TestClient,
) -> None:
    with recommendation_client.app.state.session_factory.begin() as session:
        for game in session.scalars(select(Game)).all():
            session.delete(game)

    status = recommendation_client.get("/api/v1/models/status")
    response = recommendation_client.post(
        "/api/v1/recommendations", json={"preferred_genres": ["strategy"]}
    )

    assert status.status_code == 200
    assert status.json()["status"] == "unavailable"
    assert status.json()["unavailable_reason"] == "catalog_stale"
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "catalog_stale"


def test_invalid_catalog_is_controlled_catalog_invalid(
    recommendation_client: TestClient,
) -> None:
    with recommendation_client.app.state.session_factory.begin() as session:
        game = session.scalar(select(Game).order_by(Game.id))
        assert game is not None
        game.title = "   "

    status = recommendation_client.get("/api/v1/models/status")
    response = recommendation_client.post(
        "/api/v1/recommendations", json={"preferred_genres": ["strategy"]}
    )

    assert status.status_code == 200
    assert status.json()["status"] == "unavailable"
    assert status.json()["unavailable_reason"] == "catalog_invalid"
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "catalog_invalid"


def test_malformed_json_and_wrong_content_type_use_error_envelope(
    recommendation_client: TestClient,
) -> None:
    malformed = recommendation_client.post(
        "/api/v1/recommendations",
        content='{"preferred_genres": [}',
        headers={"Content-Type": "application/json"},
    )
    wrong_content_type = recommendation_client.post(
        "/api/v1/recommendations",
        content='{"preferred_genres": ["strategy"]}',
        headers={"Content-Type": "text/plain"},
    )

    for response in (malformed, wrong_content_type):
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


def test_openapi_contains_recommendation_contract(
    recommendation_client: TestClient,
) -> None:
    schema = recommendation_client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/recommendations"]["post"]
    request_schema = schema["components"]["schemas"]["RecommendationRequest"]

    assert operation["requestBody"]["required"] is True
    assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/RecommendationRequest"
    )
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/RecommendationResponse"
    )
    assert {"200", "422", "500", "503"} <= set(operation["responses"])
    assert request_schema["additionalProperties"] is False
    assert request_schema["properties"]["top_k"] == {
        "default": 10,
        "maximum": 20.0,
        "minimum": 1.0,
        "title": "Top K",
        "type": "integer",
    }


def test_recommendation_post_cors_preflight(recommendation_client: TestClient) -> None:
    allowed = recommendation_client.options(
        "/api/v1/recommendations",
        headers={
            "Origin": "http://testserver",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    rejected = recommendation_client.options(
        "/api/v1/recommendations",
        headers={
            "Origin": "https://unknown.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://testserver"
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers
