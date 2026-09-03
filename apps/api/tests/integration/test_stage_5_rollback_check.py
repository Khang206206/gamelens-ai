from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.commands.collaborative_artifact import build_live_artifact, check_collaborative_rollback
from app.commands.collaborative_snapshot import catalog_from_seed
from app.core.config import Settings
from app.db.models import CollaborativeArtifactBuild, Game
from app.db.seed import DEFAULT_SEED_PATH
from app.services.collaborative_rollback import CollaborativeRollbackError
from gamelens_recommender import CollaborativeArtifactError, collaborative_artifacts
from gamelens_recommender.collaborative_artifacts import (
    CollaborativeBuildMetadata,
    build_collaborative_artifact,
)
from gamelens_recommender.collaborative_training import fit_collaborative_neighborhoods
from gamelens_recommender.interaction_snapshot import profile_fingerprint
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.integration.test_stage_5_lifecycle_handoff import _database_snapshot
from tests.integration.test_stage_5_live_build_promotion import (
    SUPPORTED_SLUGS,
    _live_settings,
    _seed_live_cohort,
)
from tests.integration.test_stage_5_retirement_preview import _filesystem_snapshot

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "condition", ["unregistered", "catalog", "consent", "count", "corrupt", "linked", "expired"]
)
def test_rollback_refuses_unusable_candidate_without_mutating_state(
    postgres_session: Session,
    integration_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    condition: str,
) -> None:
    _seed_live_cohort(postgres_session)
    settings = _live_settings(integration_settings)
    path = tmp_path / "candidate"
    build_id = "rollback-refusal"
    if condition == "expired":
        now = datetime.now(UTC)
        built_at = now - timedelta(days=40)
        cutoff = built_at - timedelta(hours=1)
        profiles = tuple(SUPPORTED_SLUGS for _ in range(12))
        catalog = catalog_from_seed(DEFAULT_SEED_PATH)
        fingerprint = profile_fingerprint(profiles)
        original_loader = collaborative_artifacts.load_collaborative_artifact

        def load_at_build_time(*args: object, **kwargs: object):
            return original_loader(*args, **{**kwargs, "now": built_at})

        # Simulate a bundle built in the past, then check it at real database time.
        with monkeypatch.context() as build_clock:
            build_clock.setattr(
                collaborative_artifacts, "load_collaborative_artifact", load_at_build_time
            )
            build_collaborative_artifact(
                fit_collaborative_neighborhoods(profiles, catalog_slugs=frozenset(SUPPORTED_SLUGS)),
                path,
                metadata=CollaborativeBuildMetadata(
                    source_kind="live",
                    build_id=build_id,
                    catalog_fingerprint=catalog.fingerprint,
                    interaction_fingerprint=fingerprint,
                    built_at=built_at,
                    cutoff=cutoff,
                    data_revision=7,
                    consent_version=settings.collaborative_contribution_consent_version,
                    valid_until=now - timedelta(days=10),
                ),
                revision_check=lambda revision: revision == 7,
            )
        postgres_session.add(
            CollaborativeArtifactBuild(
                build_id=build_id,
                source_kind="live",
                status="active",
                registered_revision=7,
                expected_contributor_count=12,
                current_contributor_count=12,
                consent_version=settings.collaborative_contribution_consent_version,
                catalog_fingerprint=catalog.fingerprint,
                interaction_fingerprint=fingerprint,
                cutoff=cutoff,
                valid_until=now - timedelta(days=10),
                created_at=built_at,
            )
        )
        postgres_session.commit()
    else:
        build_live_artifact(settings, path, build_id=build_id, confirmation=build_id)
        row = postgres_session.get(CollaborativeArtifactBuild, build_id)
        assert row is not None
        if condition == "unregistered":
            postgres_session.delete(row)
        elif condition == "catalog":
            game = postgres_session.scalar(select(Game).where(Game.slug == SUPPORTED_SLUGS[0]))
            assert game is not None
            game.title = "Changed catalog title"
        elif condition == "consent":
            settings = settings.model_copy(
                update={"collaborative_contribution_consent_version": "new-consent-version"}
            )
        elif condition == "count":
            row.current_contributor_count = 11
        elif condition == "corrupt":
            (path / "manifest.json").write_text("{}")
        elif condition == "linked":
            alias = tmp_path / "alias"
            alias.symlink_to(path, target_is_directory=True)
            path = alias
        postgres_session.commit()
    before_db = _database_snapshot(postgres_session)
    before_files = _filesystem_snapshot(tmp_path)
    for _ in range(2):
        with pytest.raises((CollaborativeRollbackError, CollaborativeArtifactError)) as caught:
            check_collaborative_rollback(settings, artifact=path)
        if condition in {"unregistered", "catalog", "consent", "count", "expired"}:
            assert caught.value.code == "rollback_candidate_not_ready"
        if condition == "expired":
            assert "artifact_expired" in str(caught.value)
        if condition == "linked":
            assert caught.value.code == "rollback_path_invalid"
    assert _database_snapshot(postgres_session) == before_db
    assert _filesystem_snapshot(tmp_path) == before_files
