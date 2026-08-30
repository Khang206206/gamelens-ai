from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from app.core.config import Settings
from app.db.models import CollaborativeArtifactBuild
from app.db.seed import load_seed_file, seed_database
from app.main import create_app
from app.repositories.recommendation_catalog import RecommendationCatalogRepository
from app.services.recommendation import (
    CollaborativeArtifactComponent,
    create_recommendation_service,
)
from fastapi.testclient import TestClient
from gamelens_recommender import LoadedCollaborativeArtifact, build_artifact
from sqlalchemy import select, update
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

BUILD_ID = "stage5-status-snapshot-v1"
CONSENT_VERSION = "stage-5-contribution-v1"
INTERACTION_FINGERPRINT = "b" * 64


def _live_component(
    *,
    catalog_fingerprint: str,
    cutoff: datetime,
    valid_until: datetime,
) -> CollaborativeArtifactComponent:
    manifest = {
        "source": {"kind": "live"},
        "build": {"id": BUILD_ID},
        "lifecycle": {
            "data_revision": 7,
            "consent_version": CONSENT_VERSION,
            "cutoff": cutoff.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "valid_until": valid_until.isoformat(timespec="microseconds").replace("+00:00", "Z"),
        },
        "catalog_fingerprint": catalog_fingerprint,
        "interaction_fingerprint": INTERACTION_FINGERPRINT,
        "matrix": {
            "retained_contributors": 12,
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
    return CollaborativeArtifactComponent.loaded(artifact, source_kind="live")


def test_content_and_collaborative_status_share_one_repeatable_read_snapshot(
    postgres_session: Session,
    integration_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=1)
    valid_until = now + timedelta(days=30)
    seed_database(postgres_session, load_seed_file())
    snapshot = RecommendationCatalogRepository(postgres_session).load().model_snapshot
    assert snapshot is not None
    postgres_session.rollback()
    content_artifact = build_artifact(snapshot, tmp_path / "status-content-v1")
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
            interaction_fingerprint=INTERACTION_FINGERPRINT,
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
        recommendation_service=create_recommendation_service(content_artifact),
        collaborative_component=_live_component(
            catalog_fingerprint=snapshot.fingerprint,
            cutoff=cutoff,
            valid_until=valid_until,
        ),
    )
    original_load = RecommendationCatalogRepository.load
    invalidated = False

    def load_then_invalidate(
        repository: RecommendationCatalogRepository,
    ) -> object:
        nonlocal invalidated
        catalog = original_load(repository)
        if not invalidated:
            invalidated = True
            with app.state.session_factory.begin() as writer:
                writer.execute(
                    update(CollaborativeArtifactBuild)
                    .where(CollaborativeArtifactBuild.build_id == BUILD_ID)
                    .values(
                        status="invalidated",
                        invalidation_epoch=1,
                        invalidated_at=datetime.now(UTC),
                    )
                )
        return catalog

    monkeypatch.setattr(RecommendationCatalogRepository, "load", load_then_invalidate)

    with TestClient(app) as client:
        response = client.get("/api/v1/models/status")

    postgres_session.expire_all()
    persisted_status = postgres_session.scalar(
        select(CollaborativeArtifactBuild.status).where(
            CollaborativeArtifactBuild.build_id == BUILD_ID
        )
    )
    assert invalidated
    assert persisted_status == "invalidated"
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["components"] == {
        "content": {"status": "ready", "reason": None},
        "collaborative": {"status": "ready", "reason": None, "source_kind": "live"},
    }
