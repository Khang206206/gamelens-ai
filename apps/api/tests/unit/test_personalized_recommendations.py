import json
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.commands.collaborative_artifact import build_fixture_artifact
from app.core.config import PROJECT_ROOT, Settings
from app.db.base import Base
from app.db.models import Game, Interaction, RecommendationEvent, User, UserPreference
from app.db.seed import load_seed_file, seed_database
from app.main import create_app
from app.repositories.recommendation_catalog import RecommendationCatalogRepository
from app.schemas.personalized_recommendations import RecommendationEventContext
from app.services import feedback as feedback_services
from app.services import personalized_recommendation as personalized_services
from app.services import preferences as preference_services
from app.services.anonymous_identity import AnonymousIdentityService
from app.services.recommendation import (
    CollaborativeReadiness,
    create_recommendation_service,
)
from fastapi.testclient import TestClient
from gamelens_recommender import (
    HYBRID_FALLBACK_REASONS,
    ActiveGameFeedback,
    CatalogSnapshot,
    HybridRecommendationsResult,
    Stage4FallbackResult,
    UserContext,
    build_artifact,
)
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ALLOWED_ORIGIN = "http://testserver"
CATALOG_PATH = PROJECT_ROOT / "data" / "catalog" / "games.json"
COLLABORATIVE_FIXTURE_PATH = (
    PROJECT_ROOT / "data" / "fixtures" / "interactions" / "collaborative-interactions.json"
)


class _FallbackOrchestrator:
    def __init__(self, content, reason: str) -> None:  # type: ignore[no-untyped-def]
        self.content = content
        self.reason = reason
        self.readiness: list[CollaborativeReadiness] = []
        self.result: Stage4FallbackResult | None = None

    def rank(
        self,
        *,
        snapshot: CatalogSnapshot,
        context: UserContext,
        feedback: tuple[ActiveGameFeedback, ...],
        collaborative_readiness: CollaborativeReadiness,
    ) -> Stage4FallbackResult:
        self.readiness.append(collaborative_readiness)
        stage_4_result = self.content.recommend_personalized(
            snapshot=snapshot,
            context=context,
            feedback=feedback,
        )
        result = Stage4FallbackResult(
            mode="stage_4_fallback",
            fallback_reason=self.reason,  # type: ignore[arg-type]
            stage_4_result=stage_4_result,
        )
        result.validate()
        self.result = result
        return result


class _RecordingOrchestrator:
    def __init__(self, content, delegate) -> None:  # type: ignore[no-untyped-def]
        self.content = content
        self.delegate = delegate
        self.result = None
        self.legacy_result = None

    def rank(
        self,
        *,
        snapshot: CatalogSnapshot,
        context: UserContext,
        feedback: tuple[ActiveGameFeedback, ...],
        collaborative_readiness: CollaborativeReadiness,
    ):
        self.legacy_result = self.content.recommend_personalized(
            snapshot=snapshot,
            context=context,
            feedback=feedback,
        )
        self.result = self.delegate.rank(
            snapshot=snapshot,
            context=context,
            feedback=feedback,
            collaborative_readiness=collaborative_readiness,
        )
        return self.result


class _FailingOrchestrator:
    def rank(self, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("phase 5 ranking decision failed")


class SqliteAnonymousIdentityService(AnonymousIdentityService):
    def __init__(self, session, settings) -> None:  # type: ignore[no-untyped-def]
        super().__init__(
            session,
            settings,
            clock=lambda: datetime.now(UTC).replace(tzinfo=None),
        )


def _repair_sqlite_partial_indexes(engine) -> None:  # type: ignore[no-untyped-def]
    with engine.begin() as connection:
        connection.execute(text("DROP INDEX uq_interactions_active_reaction"))
        connection.execute(text("DROP INDEX uq_interactions_active_state_type"))
        connection.execute(
            text(
                """
                CREATE UNIQUE INDEX uq_interactions_active_reaction
                ON interactions (user_id, game_id)
                WHERE superseded_at IS NULL
                  AND interaction_type IN ('liked', 'disliked')
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE UNIQUE INDEX uq_interactions_active_state_type
                ON interactions (user_id, game_id, interaction_type)
                WHERE superseded_at IS NULL
                  AND interaction_type IN ('played', 'wishlisted', 'rated')
                """
            )
        )


@contextmanager
def ready_personalized_client(
    settings: Settings,
    artifact_root: Path,
) -> Generator[tuple[TestClient, sessionmaker]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    _repair_sqlite_partial_indexes(engine)
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
        yield client, factory


@pytest.fixture
def personalized_client(
    test_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, sessionmaker]]:
    monkeypatch.setattr(
        personalized_services,
        "AnonymousIdentityService",
        SqliteAnonymousIdentityService,
    )
    monkeypatch.setattr(
        preference_services,
        "AnonymousIdentityService",
        SqliteAnonymousIdentityService,
    )
    monkeypatch.setattr(
        feedback_services,
        "AnonymousIdentityService",
        SqliteAnonymousIdentityService,
    )
    with ready_personalized_client(test_settings, tmp_path) as value:
        yield value


def _consent(client: TestClient, settings: Settings) -> str:
    response = client.post(
        "/api/v1/anonymous-sessions",
        headers={"Origin": ALLOWED_ORIGIN},
        json={"consent": True, "consent_version": settings.consent_version},
    )
    assert response.status_code == 201
    return response.json()["csrf_token"]


def _headers(settings: Settings, csrf: str) -> dict[str, str]:
    return {"Origin": ALLOWED_ORIGIN, settings.csrf_header_name: csrf}


def _save_context(
    client: TestClient,
    settings: Settings,
    csrf: str,
    *,
    game_ids: list[int] | None = None,
    genres: list[str] | None = None,
) -> None:
    response = client.put(
        "/api/v1/me/preferences",
        headers=_headers(settings, csrf),
        json={
            "selected_game_ids": game_ids or [],
            "preferred_genres": genres or [],
            "preferred_tags": [],
            "preferred_platforms": ["linux"],
        },
    )
    assert response.status_code == 200, response.text


def _table_counts(factory: sessionmaker) -> dict[str, int]:
    with factory() as session:
        return {
            "users": session.scalar(select(func.count()).select_from(User)) or 0,
            "preferences": session.scalar(select(func.count()).select_from(UserPreference)) or 0,
            "interactions": session.scalar(select(func.count()).select_from(Interaction)) or 0,
            "events": session.scalar(select(func.count()).select_from(RecommendationEvent)) or 0,
        }


def _dbapi_failure(statement: str) -> DBAPIError:
    return DBAPIError(
        statement,
        None,
        OSError("simulated lost database connection"),
        connection_invalidated=True,
    )


def test_personalized_success_commits_one_correlated_bounded_event(
    personalized_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, factory = personalized_client
    csrf = _consent(client, test_settings)
    _save_context(client, test_settings, csrf, genres=["strategy"])

    response = client.post(
        "/api/v1/me/recommendations",
        headers=_headers(test_settings, csrf),
        json={"top_k": 5},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert len(body["generation_id"]) == 32
    assert body["model_name"] == "gamelens-content-tfidf"
    assert body["model_version"] == "1.0.0"
    assert len(body["data_fingerprint"]) == 64
    assert body["policy"] == {
        "name": "gamelens-feedback-adjustment",
        "version": "1.0.0",
    }
    assert body["requested_top_k"] == 5
    assert body["response_reason"] in {
        "recommendations",
        "no_content_support",
        "no_eligible_candidates",
    }
    assert 0 <= len(body["items"]) <= 5
    for item in body["items"]:
        assert item["base_contribution"] + item["feedback_affinity_contribution"] == (
            pytest.approx(item["pre_played_score"], abs=0.000001)
        )
        assert item["pre_played_score"] + item["played_delta"] == pytest.approx(
            item["ranking_score"], abs=0.000001
        )

    with factory() as session:
        events = list(session.scalars(select(RecommendationEvent)).all())
    assert len(events) == 1
    event = events[0]
    assert event.generation_id == body["generation_id"]
    assert event.event_schema_version == "stage-4-v1"
    assert event.model_name == body["model_name"]
    assert event.model_version == body["model_version"]
    assert event.data_fingerprint == body["data_fingerprint"]
    assert event.ranking_policy_name == body["policy"]["name"]
    assert event.ranking_policy_version == body["policy"]["version"]
    assert set(event.request_context) == {
        "top_k",
        "selected_game_slugs",
        "preferred_genres",
        "preferred_tags",
        "preferred_platforms",
        "positive_source_slugs",
        "disliked_count",
        "played_count",
        "positive_source_count",
        "effective_state_fingerprint",
    }
    assert event.request_context["top_k"] == 5
    assert event.request_context["preferred_genres"] == ["strategy"]
    assert event.request_context["disliked_count"] == 0
    assert event.request_context["played_count"] == 0
    assert event.request_context["positive_source_count"] == 0
    assert len(event.request_context["effective_state_fingerprint"]) == 64
    assert len(event.result_summary or []) == len(body["items"])
    for event_item, response_item in zip(event.result_summary or [], body["items"], strict=True):
        assert set(event_item) == {
            "slug",
            "rank",
            "base_units",
            "final_units",
            "affinity_units",
            "played_delta_units",
        }
        assert event_item["slug"] == response_item["game"]["slug"]
        assert event_item["rank"] == response_item["rank"]
        assert event_item["base_units"] / 1_000_000 == pytest.approx(
            response_item["base_ranking_score"], abs=0.000001
        )
        assert event_item["final_units"] / 1_000_000 == pytest.approx(
            response_item["ranking_score"], abs=0.000001
        )


def test_personalized_event_records_only_canonical_effective_feedback_state(
    personalized_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, factory = personalized_client
    csrf = _consent(client, test_settings)
    games = client.get("/api/v1/games?sort=title&page_size=3").json()["items"]
    _save_context(
        client,
        test_settings,
        csrf,
        game_ids=[game["id"] for game in games],
        genres=["strategy"],
    )
    feedback_payloads = [
        {"reaction": "liked", "played": False, "wishlisted": False, "rating": None},
        {"reaction": "disliked", "played": False, "wishlisted": False, "rating": None},
        {"reaction": None, "played": True, "wishlisted": False, "rating": None},
    ]
    for game, payload in zip(games, feedback_payloads, strict=True):
        response = client.put(
            f"/api/v1/me/games/{game['id']}/feedback",
            headers=_headers(test_settings, csrf),
            json=payload,
        )
        assert response.status_code == 200

    response = client.post(
        "/api/v1/me/recommendations",
        headers=_headers(test_settings, csrf),
        json={"top_k": 5},
    )

    assert response.status_code == 200
    with factory() as session:
        event = session.scalar(select(RecommendationEvent))
    assert event is not None
    context = event.request_context
    assert context["selected_game_slugs"] == sorted([games[0]["slug"], games[2]["slug"]])
    assert context["positive_source_slugs"] == [games[0]["slug"]]
    assert context["disliked_count"] == 1
    assert context["played_count"] == 1
    assert context["positive_source_count"] == 1
    assert len(context["effective_state_fingerprint"]) == 64
    serialized_event = json.dumps(
        {"context": event.request_context, "result": event.result_summary},
        sort_keys=True,
    )
    for forbidden in ("user_id", "token", "csrf", "consent", "explanation"):
        assert forbidden not in serialized_event.lower()


def test_event_context_schema_forbids_extra_or_noncanonical_payloads() -> None:
    baseline = {
        "top_k": 5,
        "selected_game_slugs": ["valid-game"],
        "preferred_genres": ["strategy"],
        "preferred_tags": [],
        "preferred_platforms": [],
        "positive_source_slugs": [],
        "disliked_count": 0,
        "played_count": 0,
        "positive_source_count": 0,
        "effective_state_fingerprint": "a" * 64,
    }

    with pytest.raises(ValidationError):
        RecommendationEventContext.model_validate({**baseline, "session_token": "secret"})
    with pytest.raises(ValidationError):
        RecommendationEventContext.model_validate(
            {**baseline, "selected_game_slugs": ["Not Canonical"]}
        )


def test_event_context_counts_cover_the_full_supported_catalog() -> None:
    baseline = {
        "top_k": 5,
        "selected_game_slugs": [],
        "preferred_genres": [],
        "preferred_tags": [],
        "preferred_platforms": [],
        "positive_source_slugs": [],
        "disliked_count": 1_001,
        "played_count": 100_000,
        "positive_source_count": 0,
        "effective_state_fingerprint": "a" * 64,
    }

    context = RecommendationEventContext.model_validate(baseline)

    assert context.disliked_count == 1_001
    assert context.played_count == 100_000
    with pytest.raises(ValidationError):
        RecommendationEventContext.model_validate({**baseline, "played_count": 100_001})


def test_event_flush_failure_is_known_precommit_failure_with_zero_event(
    personalized_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, factory = personalized_client
    csrf = _consent(client, test_settings)
    _save_context(client, test_settings, csrf, genres=["strategy"])
    original_flush = OrmSession.flush

    def fail_event_flush(self, objects=None) -> None:  # type: ignore[no-untyped-def]
        if any(isinstance(item, RecommendationEvent) for item in self.new):
            raise _dbapi_failure("INSERT recommendation_events")
        original_flush(self, objects)

    monkeypatch.setattr(OrmSession, "flush", fail_event_flush)
    response = client.post(
        "/api/v1/me/recommendations",
        headers=_headers(test_settings, csrf),
        json={"top_k": 5},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert "generation_id" not in response.text
    assert response.headers["cache-control"] == "no-store"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(RecommendationEvent)) == 0


def test_event_commit_failure_reports_ambiguous_generation_without_200(
    personalized_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, factory = personalized_client
    csrf = _consent(client, test_settings)
    _save_context(client, test_settings, csrf, genres=["strategy"])

    def fail_commit(_self) -> None:  # type: ignore[no-untyped-def]
        raise _dbapi_failure("COMMIT")

    monkeypatch.setattr(OrmSession, "commit", fail_commit)
    response = client.post(
        "/api/v1/me/recommendations",
        headers=_headers(test_settings, csrf),
        json={"top_k": 5},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "generation_outcome_unknown"
    generation_id = response.json()["error"]["details"]["generation_id"]
    assert len(generation_id) == 32
    assert response.headers["cache-control"] == "no-store"
    with factory() as session:
        matching_events = session.scalar(
            select(func.count())
            .select_from(RecommendationEvent)
            .where(RecommendationEvent.generation_id == generation_id)
        )
    assert matching_events in {0, 1}


def test_personalized_requires_protected_saved_context_and_records_zero_event_on_4xx(
    personalized_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, factory = personalized_client
    csrf = _consent(client, test_settings)

    cases = [
        ({"Origin": ALLOWED_ORIGIN}, {"top_k": 5}, 403, "csrf_validation_failed"),
        ({test_settings.csrf_header_name: csrf}, {"top_k": 5}, 403, "origin_not_allowed"),
        (_headers(test_settings, csrf), {"top_k": 0}, 422, "validation_error"),
        (_headers(test_settings, csrf), {"top_k": 21}, 422, "validation_error"),
        (
            _headers(test_settings, csrf),
            {"top_k": 5, "unexpected": True},
            422,
            "validation_error",
        ),
        (
            _headers(test_settings, csrf),
            {"top_k": 5},
            422,
            "saved_preferences_required",
        ),
    ]
    for headers, payload, status, code in cases:
        response = client.post(
            "/api/v1/me/recommendations",
            headers=headers,
            json=payload,
        )
        assert response.status_code == status
        assert response.json()["error"]["code"] == code
        assert response.headers["cache-control"] == "no-store"
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(RecommendationEvent)) == 0


def test_disliked_only_saved_game_returns_controlled_error_and_zero_event(
    personalized_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, factory = personalized_client
    csrf = _consent(client, test_settings)
    game_id = client.get("/api/v1/games?sort=title&page_size=1").json()["items"][0]["id"]
    _save_context(client, test_settings, csrf, game_ids=[game_id])
    feedback = client.put(
        f"/api/v1/me/games/{game_id}/feedback",
        headers=_headers(test_settings, csrf),
        json={"reaction": "disliked", "played": False, "wishlisted": False, "rating": None},
    )
    assert feedback.status_code == 200

    response = client.post(
        "/api/v1/me/recommendations",
        headers=_headers(test_settings, csrf),
        json={"top_k": 5},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "effective_context_required"
    assert response.headers["cache-control"] == "no-store"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(RecommendationEvent)) == 0


def test_stale_saved_context_returns_conflict_and_zero_event(
    personalized_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, factory = personalized_client
    csrf = _consent(client, test_settings)
    _save_context(client, test_settings, csrf, genres=["strategy"])
    with factory.begin() as session:
        preference = session.scalar(select(UserPreference))
        assert preference is not None
        preference.value = "removed-genre"

    response = client.post(
        "/api/v1/me/recommendations",
        headers=_headers(test_settings, csrf),
        json={"top_k": 5},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "saved_preferences_stale"
    assert response.headers["cache-control"] == "no-store"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(RecommendationEvent)) == 0


def test_stateless_recommendation_ignores_valid_cookie_and_never_writes(
    personalized_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, factory = personalized_client
    csrf = _consent(client, test_settings)
    _save_context(client, test_settings, csrf, genres=["rpg"])
    before = _table_counts(factory)

    response = client.post(
        "/api/v1/recommendations",
        json={"preferred_genres": ["strategy"], "top_k": 3},
    )

    assert response.status_code == 200
    assert response.json()["items"]
    assert "set-cookie" not in response.headers
    assert _table_counts(factory) == before


@pytest.mark.parametrize("reason", HYBRID_FALLBACK_REASONS)
def test_every_phase5_fallback_maps_the_exact_stage4_decision_and_event(
    personalized_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
    reason: str,
) -> None:
    client, factory = personalized_client
    csrf = _consent(client, test_settings)
    _save_context(client, test_settings, csrf, genres=["strategy"])
    orchestrator = _FallbackOrchestrator(
        client.app.state.recommendation_service,
        reason,
    )
    client.app.state.hybrid_orchestrator = orchestrator

    response = client.post(
        "/api/v1/me/recommendations",
        headers=_headers(test_settings, csrf),
        json={"top_k": 5},
    )

    assert response.status_code == 200
    assert orchestrator.result is not None
    assert len(orchestrator.readiness) == 1
    expected = orchestrator.result.stage_4_result
    body = response.json()
    assert body["policy"] == {
        "name": expected.policy.name,
        "version": expected.policy.version,
    }
    assert body["response_reason"] == expected.reason
    assert [item["game"]["slug"] for item in body["items"]] == [
        item.slug for item in expected.items
    ]
    assert [item["rank"] for item in body["items"]] == [item.rank for item in expected.items]
    assert [round(item["ranking_score"] * 1_000_000) for item in body["items"]] == [
        item.final_score_units for item in expected.items
    ]
    with factory() as session:
        event = session.scalar(select(RecommendationEvent))
    assert event is not None
    assert event.event_schema_version == "stage-4-v1"
    assert event.ranking_policy_name == expected.policy.name
    assert event.ranking_policy_version == expected.policy.version
    assert [item["slug"] for item in event.result_summary or []] == [
        item.slug for item in expected.items
    ]


def test_ready_hybrid_decision_stays_internal_until_phase6_mapping(
    test_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        personalized_services,
        "AnonymousIdentityService",
        SqliteAnonymousIdentityService,
    )
    monkeypatch.setattr(
        preference_services,
        "AnonymousIdentityService",
        SqliteAnonymousIdentityService,
    )
    monkeypatch.setattr(
        feedback_services,
        "AnonymousIdentityService",
        SqliteAnonymousIdentityService,
    )
    collaborative_root = tmp_path / "collaborative"
    settings = test_settings.model_copy(
        update={
            "collaborative_artifact_path": collaborative_root,
            "collaborative_allow_test_fixture": True,
        }
    )
    build_fixture_artifact(
        settings,
        collaborative_root,
        fixture_path=COLLABORATIVE_FIXTURE_PATH,
        catalog_path=CATALOG_PATH,
        built_at=datetime.now(UTC),
    )

    with ready_personalized_client(settings, tmp_path / "hybrid-content") as value:
        client, factory = value
        csrf = _consent(client, settings)
        games = client.get("/api/v1/games?page_size=30").json()["items"]
        source = next(game for game in games if game["slug"] == "emberfall-tactics")
        _save_context(
            client,
            settings,
            csrf,
            game_ids=[source["id"]],
            genres=["strategy"],
        )
        feedback_response = client.put(
            f"/api/v1/me/games/{source['id']}/feedback",
            headers=_headers(settings, csrf),
            json={
                "reaction": "liked",
                "played": False,
                "wishlisted": False,
                "rating": None,
            },
        )
        assert feedback_response.status_code == 200
        loaded_component = client.app.state.collaborative_component
        loaded_orchestrator = client.app.state.hybrid_orchestrator
        orchestrator = _RecordingOrchestrator(
            client.app.state.recommendation_service,
            loaded_orchestrator,
        )
        client.app.state.hybrid_orchestrator = orchestrator

        response = client.post(
            "/api/v1/me/recommendations",
            headers=_headers(settings, csrf),
            json={"top_k": 20},
        )

        assert response.status_code == 200
        assert type(orchestrator.result) is HybridRecommendationsResult
        assert orchestrator.legacy_result is not None
        assert client.app.state.collaborative_component is loaded_component
        body = response.json()
        assert body["policy"] == {
            "name": orchestrator.legacy_result.policy.name,
            "version": orchestrator.legacy_result.policy.version,
        }
        assert [item["game"]["slug"] for item in body["items"]] == [
            item.slug for item in orchestrator.legacy_result.items
        ]
        assert [item["game"]["slug"] for item in body["items"]] != [
            item.slug for item in orchestrator.result.items
        ]
        with factory() as session:
            event = session.scalar(select(RecommendationEvent))
        assert event is not None
        assert event.event_schema_version == "stage-4-v1"
        assert event.ranking_policy_name == orchestrator.legacy_result.policy.name
        assert "gamelens-hybrid-ranking" not in json.dumps(
            {
                "context": event.request_context,
                "result": event.result_summary,
                "policy": event.ranking_policy_name,
            },
            sort_keys=True,
        )


def test_ranking_decision_failure_commits_no_partial_event(
    personalized_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, factory = personalized_client
    csrf = _consent(client, test_settings)
    _save_context(client, test_settings, csrf, genres=["strategy"])
    client.app.state.hybrid_orchestrator = _FailingOrchestrator()

    response = client.post(
        "/api/v1/me/recommendations",
        headers=_headers(test_settings, csrf),
        json={"top_k": 5},
    )

    assert response.status_code == 500
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(RecommendationEvent)) == 0


def test_personalized_catalog_stale_keeps_content_error_and_commits_zero_event(
    personalized_client: tuple[TestClient, sessionmaker],
    test_settings: Settings,
) -> None:
    client, factory = personalized_client
    csrf = _consent(client, test_settings)
    _save_context(client, test_settings, csrf, genres=["strategy"])
    with factory.begin() as session:
        game = session.scalar(select(Game).order_by(Game.id))
        assert game is not None
        game.description = f"{game.description} changed"

    response = client.post(
        "/api/v1/me/recommendations",
        headers=_headers(test_settings, csrf),
        json={"top_k": 5},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "catalog_stale"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(RecommendationEvent)) == 0


def test_personalized_openapi_contract_is_exact(
    personalized_client: tuple[TestClient, sessionmaker],
) -> None:
    client, _factory = personalized_client
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/me/recommendations"]["post"]
    request_schema = schema["components"]["schemas"]["PersonalizedRecommendationRequest"]
    feedback_schema = schema["components"]["schemas"]["FeedbackResource"]

    assert operation["requestBody"]["required"] is True
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/PersonalizedRecommendationResponse"
    )
    assert {"200", "401", "403", "409", "422", "500", "503"} <= set(operation["responses"])
    assert request_schema["additionalProperties"] is False
    assert request_schema["properties"]["top_k"] == {
        "default": 10,
        "maximum": 20.0,
        "minimum": 1.0,
        "title": "Top K",
        "type": "integer",
    }
    assert "number" in str(feedback_schema["properties"]["rating"])
    assert "string" not in str(feedback_schema["properties"]["rating"])
