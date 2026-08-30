import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.commands.collaborative_snapshot import catalog_from_seed
from app.core.config import PROJECT_ROOT, Settings
from app.db.models import CollaborativeArtifactBuild, RecommendationEvent
from app.db.seed import load_seed_file, seed_database
from app.main import create_app
from app.repositories.collaborative_registry import CollaborativeArtifactRegistryRepository
from app.repositories.recommendation_catalog import RecommendationCatalogRepository
from app.services.recommendation import (
    CollaborativeArtifactComponent,
    CollaborativeReadiness,
    create_recommendation_service,
)
from fastapi.testclient import TestClient
from gamelens_recommender import (
    CollaborativeBuildMetadata,
    HybridRecommendationsResult,
    Stage4FallbackResult,
    build_artifact,
    build_collaborative_artifact,
    fit_collaborative_neighborhoods,
    load_collaborative_artifact,
    profile_fingerprint,
)
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

BUILD_ID = "stage5-orchestration-live-v1"
CONSENT_VERSION = "stage-5-contribution-v1"
CATALOG_PATH = PROJECT_ROOT / "data" / "catalog" / "games.json"


class _RecordingOrchestrator:
    def __init__(self, delegate) -> None:  # type: ignore[no-untyped-def]
        self.delegate = delegate
        self.readiness: list[CollaborativeReadiness] = []
        self.results = []

    def rank(self, **kwargs):  # type: ignore[no-untyped-def]
        self.readiness.append(kwargs["collaborative_readiness"])
        result = self.delegate.rank(**kwargs)
        self.results.append(result)
        return result


def _live_component(
    root: Path,
    *,
    catalog_fingerprint: str,
    now: datetime,
) -> tuple[CollaborativeArtifactComponent, str, datetime, datetime]:
    catalog = catalog_from_seed(CATALOG_PATH)
    assert catalog.fingerprint == catalog_fingerprint
    catalog_slugs = frozenset(item.slug for item in catalog.items)
    item_slugs = (
        "emberfall-tactics",
        "starbound-couriers",
        "verdant-vale",
        "neon-drift-circuit",
        "clockwork-orchard",
        "warden-of-glass",
    )
    profiles = tuple(item_slugs for _index in range(12))
    neighborhoods = fit_collaborative_neighborhoods(
        profiles,
        catalog_slugs=catalog_slugs,
    )
    interaction_fingerprint = profile_fingerprint(profiles)
    cutoff = now - timedelta(hours=1)
    valid_until = now + timedelta(days=30)
    artifact_root = build_collaborative_artifact(
        neighborhoods,
        root,
        metadata=CollaborativeBuildMetadata(
            source_kind="live",
            catalog_fingerprint=catalog_fingerprint,
            interaction_fingerprint=interaction_fingerprint,
            build_id=BUILD_ID,
            built_at=now,
            cutoff=cutoff,
            consent_version=CONSENT_VERSION,
            data_revision=7,
            valid_until=valid_until,
        ),
        revision_check=lambda revision: revision == 7,
    )
    artifact = load_collaborative_artifact(
        artifact_root,
        expected_catalog_fingerprint=catalog_fingerprint,
        now=now,
    )
    return (
        CollaborativeArtifactComponent.loaded(artifact, source_kind="live"),
        interaction_fingerprint,
        cutoff,
        valid_until,
    )


def _protected_context(
    client: TestClient,
    settings: Settings,
) -> dict[str, str]:
    consent = client.post(
        "/api/v1/anonymous-sessions",
        headers={"Origin": "http://testserver"},
        json={"consent": True, "consent_version": settings.consent_version},
    )
    assert consent.status_code == 201
    headers = {
        "Origin": "http://testserver",
        settings.csrf_header_name: consent.json()["csrf_token"],
    }
    games = client.get("/api/v1/games?page_size=30").json()["items"]
    source = next(game for game in games if game["slug"] == "emberfall-tactics")
    saved = client.put(
        "/api/v1/me/preferences",
        headers=headers,
        json={
            "selected_game_ids": [source["id"]],
            "preferred_genres": ["strategy"],
            "preferred_tags": [],
            "preferred_platforms": ["windows"],
        },
    )
    assert saved.status_code == 200
    feedback = client.put(
        f"/api/v1/me/games/{source['id']}/feedback",
        headers=headers,
        json={
            "reaction": "liked",
            "played": False,
            "wishlisted": False,
            "rating": None,
        },
    )
    assert feedback.status_code == 200
    return headers


def test_saved_handoff_uses_one_snapshot_then_observes_invalidation_and_retirement(
    postgres_session: Session,
    integration_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_database(postgres_session, load_seed_file())
    snapshot = RecommendationCatalogRepository(postgres_session).load().model_snapshot
    assert snapshot is not None
    postgres_session.rollback()
    now = datetime.now(UTC)
    content_root = build_artifact(snapshot, tmp_path / "content", built_at=now)
    component, interaction_fingerprint, cutoff, valid_until = _live_component(
        tmp_path / "collaborative",
        catalog_fingerprint=snapshot.fingerprint,
        now=now,
    )
    postgres_session.add(
        CollaborativeArtifactBuild(
            build_id=BUILD_ID,
            source_kind="live",
            status="active",
            registered_revision=7,
            invalidation_epoch=0,
            expected_contributor_count=12,
            current_contributor_count=12,
            consent_version=CONSENT_VERSION,
            catalog_fingerprint=snapshot.fingerprint,
            interaction_fingerprint=interaction_fingerprint,
            cutoff=cutoff,
            valid_until=valid_until,
            invalidated_at=None,
            retired_at=None,
        )
    )
    postgres_session.commit()
    settings = integration_settings.model_copy(
        update={
            "collaborative_live_data_enabled": True,
            "collaborative_contribution_consent_version": CONSENT_VERSION,
        }
    )
    app = create_app(
        settings,
        recommendation_service=create_recommendation_service(content_root),
        collaborative_component=component,
    )

    with TestClient(app) as client:
        headers = _protected_context(client, settings)
        recorder = _RecordingOrchestrator(app.state.hybrid_orchestrator)
        app.state.hybrid_orchestrator = recorder
        original_load = RecommendationCatalogRepository.load
        invalidated_at = datetime.now(UTC)
        invalidated_during_first_request = False

        def load_then_invalidate(repository: RecommendationCatalogRepository):
            nonlocal invalidated_during_first_request
            catalog = original_load(repository)
            if not invalidated_during_first_request:
                invalidated_during_first_request = True
                with app.state.session_factory.begin() as writer:
                    writer.execute(
                        update(CollaborativeArtifactBuild)
                        .where(CollaborativeArtifactBuild.build_id == BUILD_ID)
                        .values(
                            status="invalidated",
                            invalidation_epoch=1,
                            invalidated_at=invalidated_at,
                        )
                    )
            return catalog

        monkeypatch.setattr(RecommendationCatalogRepository, "load", load_then_invalidate)
        first = client.post(
            "/api/v1/me/recommendations",
            headers=headers,
            json={"top_k": 20},
        )
        second = client.post(
            "/api/v1/me/recommendations",
            headers=headers,
            json={"top_k": 20},
        )
        with app.state.session_factory.begin() as writer:
            writer.execute(
                update(CollaborativeArtifactBuild)
                .where(CollaborativeArtifactBuild.build_id == BUILD_ID)
                .values(
                    status="retired",
                    retired_at=datetime.now(UTC),
                )
            )
        third = client.post(
            "/api/v1/me/recommendations",
            headers=headers,
            json={"top_k": 20},
        )
        monkeypatch.setattr(
            CollaborativeArtifactRegistryRepository,
            "readiness",
            lambda repository, _build_id: repository.session.execute(
                text("SELECT missing_column FROM missing_collaborative_table")
            ),
        )
        fourth = client.post(
            "/api/v1/me/recommendations",
            headers=headers,
            json={"top_k": 20},
        )

    assert invalidated_during_first_request
    assert [first.status_code, second.status_code, third.status_code, fourth.status_code] == [
        200,
        200,
        200,
        200,
    ]
    assert [readiness.state for readiness in recorder.readiness] == [
        "ready",
        "stale",
        "stale",
        "stale",
    ]
    assert [readiness.reason for readiness in recorder.readiness] == [
        None,
        "privacy_invalid",
        "artifact_retired",
        "artifact_incompatible",
    ]
    assert type(recorder.results[0]) is HybridRecommendationsResult
    assert all(type(result) is Stage4FallbackResult for result in recorder.results[1:])
    assert [result.fallback_reason for result in recorder.results[1:]] == [
        "privacy_invalid",
        "artifact_retired",
        "artifact_incompatible",
    ]
    postgres_session.rollback()
    events = list(postgres_session.scalars(select(RecommendationEvent)).all())
    assert len(events) == 4
    assert all(event.event_schema_version == "stage-4-v1" for event in events)
    assert all(event.ranking_policy_name == "gamelens-feedback-adjustment" for event in events)
    assert "gamelens-hybrid-ranking" not in json.dumps(
        [
            {
                "context": event.request_context,
                "result": event.result_summary,
                "policy": event.ranking_policy_name,
            }
            for event in events
        ],
        sort_keys=True,
    )
    assert postgres_session.scalar(select(func.count()).select_from(RecommendationEvent)) == 4
