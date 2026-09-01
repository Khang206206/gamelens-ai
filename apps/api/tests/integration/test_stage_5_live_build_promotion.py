import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from app.commands.collaborative_artifact import build_live_artifact
from app.core.config import Settings
from app.db.models import (
    CollaborativeArtifactBuild,
    CollaborativeArtifactContributor,
    CollaborativeContributionConsent,
    CollaborativeDataRevision,
    Game,
    PreferenceType,
    UserPreference,
)
from app.db.seed import load_seed_file, seed_database
from app.db.session import create_session_factory
from app.repositories.collaborative_registry import (
    CollaborativeArtifactRegistryRepository,
    CollaborativeRegistryMutationError,
    LiveBuildRegistration,
)
from app.services.collaborative_build import CollaborativeLiveBuildService
from gamelens_recommender import inspect_collaborative_artifact
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.conftest import make_consented_user

pytestmark = pytest.mark.integration

BASE_CONSENT_VERSION = "stage-4-v1"
CONTRIBUTION_VERSION = "stage-5-contribution-v1"
BUILD_ID = "stage5-live-promotion-v1"
SUPPORTED_SLUGS = (
    "clockwork-orchard",
    "emberfall-tactics",
    "neon-drift-circuit",
    "starbound-couriers",
    "verdant-vale",
    "warden-of-glass",
)
PRUNED_SLUGS = ("harborlight", "lumen-depths")


def _seed_live_cohort(session: Session) -> tuple[list[int], int]:
    seed_database(session, load_seed_file())
    game_slugs = set(session.scalars(select(Game.slug)).all())
    assert set(SUPPORTED_SLUGS + PRUNED_SLUGS) <= game_slugs
    now = datetime.now(UTC)
    supported_users = [
        make_consented_user(
            f"live-promotion-{index}",
            consent_version=BASE_CONSENT_VERSION,
            consented_at=now - timedelta(days=10),
            expires_at=now + timedelta(days=60),
        )
        for index in range(12)
    ]
    pruned_user = make_consented_user(
        "live-promotion-pruned",
        consent_version=BASE_CONSENT_VERSION,
        consented_at=now - timedelta(days=10),
        expires_at=now + timedelta(days=60),
    )
    session.add_all([*supported_users, pruned_user])
    session.flush()
    all_users = [*supported_users, pruned_user]
    session.add_all(
        CollaborativeContributionConsent(
            user_id=user.id,
            consent_version=CONTRIBUTION_VERSION,
            granted_at=now - timedelta(days=5),
        )
        for user in all_users
    )
    session.add_all(
        UserPreference(
            user_id=user.id,
            preference_type=PreferenceType.GAME,
            value=slug,
            weight=Decimal("1"),
        )
        for user in supported_users
        for slug in SUPPORTED_SLUGS
    )
    session.add_all(
        UserPreference(
            user_id=pruned_user.id,
            preference_type=PreferenceType.GAME,
            value=slug,
            weight=Decimal("1"),
        )
        for slug in PRUNED_SLUGS
    )
    session.commit()
    return [user.id for user in supported_users], pruned_user.id


def _live_settings(settings: Settings) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=settings.database_url,
        cors_origins=["http://testserver"],
        consent_version=BASE_CONSENT_VERSION,
        collaborative_live_data_enabled=True,
        collaborative_contribution_consent_version=CONTRIBUTION_VERSION,
        collaborative_live_promotion_enabled=True,
    )


def test_live_build_registers_only_support_retained_lineage_and_blocks_second_active(
    postgres_session: Session,
    integration_settings: Settings,
    tmp_path: Path,
) -> None:
    supported_user_ids, pruned_user_id = _seed_live_cohort(postgres_session)
    settings = _live_settings(integration_settings)
    output = tmp_path / BUILD_ID

    result = build_live_artifact(
        settings,
        output,
        build_id=BUILD_ID,
        confirmation=BUILD_ID,
    )

    assert output.is_dir()
    assert result["status"] == "valid"
    assert result["source"]["kind"] == "live"  # type: ignore[index]
    assert result["matrix"]["retained_contributors"] == 12  # type: ignore[index]
    assert result["promotion"] == {
        "registered": True,
        "status": "active",
        "registered_revision": result["lifecycle"]["data_revision"],  # type: ignore[index]
        "contributor_count": 12,
    }
    serialized = json.dumps(result, sort_keys=True)
    assert "user_id" not in serialized
    assert "anonymous_token" not in serialized

    postgres_session.expire_all()
    build = postgres_session.get(CollaborativeArtifactBuild, BUILD_ID)
    assert build is not None
    assert build.status == "active"
    assert build.current_contributor_count == 12
    assert build.expected_contributor_count == 12
    registered_user_ids = set(
        postgres_session.scalars(
            select(CollaborativeArtifactContributor.user_id).where(
                CollaborativeArtifactContributor.build_id == BUILD_ID
            )
        ).all()
    )
    assert registered_user_ids == set(supported_user_ids)
    assert pruned_user_id not in registered_user_ids
    readiness = CollaborativeArtifactRegistryRepository(postgres_session).readiness(BUILD_ID)
    assert readiness is not None
    assert readiness.status == "active"

    artifact_report = inspect_collaborative_artifact(
        output,
        expected_catalog_fingerprint=build.catalog_fingerprint,
        expected_data_revision=build.registered_revision,
        expected_consent_version=CONTRIBUTION_VERSION,
    )
    assert artifact_report["build"]["id"] == BUILD_ID  # type: ignore[index]

    second_output = tmp_path / "stage5-live-promotion-v2"
    with pytest.raises(CollaborativeRegistryMutationError) as second:
        build_live_artifact(
            settings,
            second_output,
            build_id="stage5-live-promotion-v2",
            confirmation="stage5-live-promotion-v2",
        )

    assert second.value.code == "active_build_exists"
    assert not second_output.exists()


def test_registry_promotion_revision_race_rolls_back_build_and_lineage(
    postgres_engine: Engine,
    postgres_session: Session,
) -> None:
    supported_user_ids, _pruned_user_id = _seed_live_cohort(postgres_session)
    current_revision = postgres_session.scalar(select(CollaborativeDataRevision.revision))
    assert current_revision is not None and current_revision > 0
    postgres_session.rollback()
    now = datetime.now(UTC)
    registration = LiveBuildRegistration(
        build_id="stage5-live-revision-race-v1",
        registered_revision=current_revision - 1,
        contributor_user_ids=(supported_user_ids[0],),
        consent_version=CONTRIBUTION_VERSION,
        catalog_fingerprint="a" * 64,
        interaction_fingerprint="b" * 64,
        cutoff=now,
        valid_until=now + timedelta(days=30),
    )

    with pytest.raises(CollaborativeRegistryMutationError) as caught:
        CollaborativeLiveBuildService(create_session_factory(postgres_engine))._register(
            registration
        )

    assert caught.value.code == "revision_race"
    postgres_session.expire_all()
    assert postgres_session.get(CollaborativeArtifactBuild, registration.build_id) is None
    assert (
        postgres_session.scalar(
            select(CollaborativeArtifactContributor.user_id).where(
                CollaborativeArtifactContributor.build_id == registration.build_id
            )
        )
        is None
    )


def test_concurrent_registry_promotions_commit_exactly_one_active_build(
    postgres_engine: Engine,
    postgres_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supported_user_ids, _pruned_user_id = _seed_live_cohort(postgres_session)
    current_revision = postgres_session.scalar(select(CollaborativeDataRevision.revision))
    assert current_revision is not None
    postgres_session.rollback()
    now = datetime.now(UTC)
    registrations = tuple(
        LiveBuildRegistration(
            build_id=f"stage5-live-concurrent-v{index}",
            registered_revision=current_revision,
            contributor_user_ids=(supported_user_ids[index - 1],),
            consent_version=CONTRIBUTION_VERSION,
            catalog_fingerprint="a" * 64,
            interaction_fingerprint=str(index) * 64,
            cutoff=now,
            valid_until=now + timedelta(days=30),
        )
        for index in (1, 2)
    )
    preflight_barrier = threading.Barrier(2)
    original_preflight = CollaborativeArtifactRegistryRepository.assert_live_build_slot

    def synchronized_preflight(
        repository: CollaborativeArtifactRegistryRepository,
        build_id: str,
    ) -> None:
        original_preflight(repository, build_id)
        preflight_barrier.wait(timeout=5)

    monkeypatch.setattr(
        CollaborativeArtifactRegistryRepository,
        "assert_live_build_slot",
        synchronized_preflight,
    )

    def promote(registration: LiveBuildRegistration) -> str:
        try:
            CollaborativeLiveBuildService(create_session_factory(postgres_engine))._register(
                registration
            )
        except CollaborativeRegistryMutationError as error:
            return error.code
        return "active"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(promote, registrations))

    assert sorted(outcomes) == ["active", "active_build_exists"]
    postgres_session.expire_all()
    active_build_ids = list(
        postgres_session.scalars(
            select(CollaborativeArtifactBuild.build_id).where(
                CollaborativeArtifactBuild.status == "active"
            )
        ).all()
    )
    assert len(active_build_ids) == 1
    assert active_build_ids[0] in {registration.build_id for registration in registrations}
    assert (
        postgres_session.scalar(
            select(CollaborativeArtifactContributor.user_id).where(
                CollaborativeArtifactContributor.build_id == active_build_ids[0]
            )
        )
        in supported_user_ids[:2]
    )
