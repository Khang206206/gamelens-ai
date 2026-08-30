from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from types import SimpleNamespace
from typing import cast

import pytest
from app.db.models import (
    CollaborativeArtifactBuild,
    CollaborativeArtifactContributor,
    CollaborativeContributionConsent,
    User,
)
from app.db.session import create_session_factory
from app.repositories.collaborative_registry import CollaborativeArtifactRegistryRepository
from app.services.recommendation import (
    CollaborativeArtifactComponent,
    evaluate_collaborative_readiness,
)
from app.services.retention import (
    AnonymousSessionRevocationService,
    RetentionCutoffs,
    RetentionService,
)
from gamelens_recommender import LoadedCollaborativeArtifact
from sqlalchemy import Engine, func, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from tests.conftest import make_consented_user

pytestmark = pytest.mark.integration

BUILD_ID = "stage5-live-authority-v1"
CONTRIBUTION_VERSION = "stage-5-contribution-v1"
CATALOG_FINGERPRINT = "a" * 64
INTERACTION_FINGERPRINT = "b" * 64


def _register_build(
    session: Session,
    *,
    now: datetime,
    identity: str = "authority-contributor",
    expires_at: datetime | None = None,
    created_at: datetime | None = None,
    register_contributor: bool = True,
) -> tuple[User, CollaborativeContributionConsent, CollaborativeArtifactBuild]:
    user = make_consented_user(
        identity,
        consented_at=now - timedelta(days=60),
        expires_at=expires_at or now + timedelta(days=60),
    )
    if created_at is not None:
        user.created_at = created_at
    session.add(user)
    session.flush()
    consent = CollaborativeContributionConsent(
        user_id=user.id,
        consent_version=CONTRIBUTION_VERSION,
        granted_at=now - timedelta(days=30),
    )
    build = CollaborativeArtifactBuild(
        build_id=BUILD_ID,
        source_kind="live",
        status="active",
        registered_revision=7,
        invalidation_epoch=0,
        expected_contributor_count=1,
        current_contributor_count=0,
        consent_version=CONTRIBUTION_VERSION,
        catalog_fingerprint=CATALOG_FINGERPRINT,
        interaction_fingerprint=INTERACTION_FINGERPRINT,
        cutoff=now - timedelta(hours=1),
        valid_until=now + timedelta(days=30),
    )
    session.add_all([consent, build])
    session.flush()
    if register_contributor:
        session.add(CollaborativeArtifactContributor(build_id=build.build_id, user_id=user.id))
        session.flush()
    session.refresh(build)
    assert build.current_contributor_count == int(register_contributor)
    assert build.status == "active"
    return user, consent, build


def _artifact(*, valid_until: datetime) -> LoadedCollaborativeArtifact:
    manifest = {
        "source": {"kind": "live"},
        "build": {"id": BUILD_ID},
        "lifecycle": {
            "data_revision": 7,
            "consent_version": CONTRIBUTION_VERSION,
            "cutoff": (valid_until - timedelta(days=30, hours=1))
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z"),
            "valid_until": valid_until.isoformat(timespec="microseconds").replace("+00:00", "Z"),
        },
        "catalog_fingerprint": CATALOG_FINGERPRINT,
        "interaction_fingerprint": INTERACTION_FINGERPRINT,
        "matrix": {
            "retained_contributors": 1,
            "retained_positive_edges": 1,
            "retained_items": 1,
        },
        "thresholds": {
            "activation_minimum_users": 1,
            "activation_minimum_edges": 1,
            "activation_minimum_items": 1,
        },
    }
    return cast(LoadedCollaborativeArtifact, SimpleNamespace(manifest=manifest))


def _assert_invalidated(build: CollaborativeArtifactBuild, *, contributor_count: int = 1) -> None:
    assert build.status == "invalidated"
    assert build.invalidation_epoch == 1
    assert build.invalidated_at is not None
    assert build.current_contributor_count == contributor_count


def test_consent_withdrawal_is_atomic_and_reconsent_does_not_revive_build(
    postgres_session: Session,
) -> None:
    now = datetime.now(UTC)
    _user, consent, build = _register_build(postgres_session, now=now)
    postgres_session.commit()

    postgres_session.execute(
        update(CollaborativeContributionConsent)
        .where(CollaborativeContributionConsent.user_id == consent.user_id)
        .values(consent_version=CONTRIBUTION_VERSION)
    )
    postgres_session.refresh(build)
    assert build.status == "active"
    assert build.invalidation_epoch == 0

    consent = postgres_session.get(CollaborativeContributionConsent, consent.user_id)
    assert consent is not None
    consent.withdrawn_at = now
    postgres_session.flush()
    postgres_session.refresh(build)
    _assert_invalidated(build)

    postgres_session.rollback()
    build = postgres_session.get(CollaborativeArtifactBuild, BUILD_ID)
    consent = postgres_session.get(CollaborativeContributionConsent, consent.user_id)
    assert build is not None
    assert consent is not None
    assert build.status == "active"
    assert build.invalidation_epoch == 0
    assert consent.withdrawn_at is None

    consent.withdrawn_at = now
    postgres_session.commit()
    postgres_session.expire_all()
    build = postgres_session.get(CollaborativeArtifactBuild, BUILD_ID)
    assert build is not None
    _assert_invalidated(build)

    row = CollaborativeArtifactRegistryRepository(postgres_session).readiness(BUILD_ID)
    assert row is not None
    readiness = evaluate_collaborative_readiness(
        CollaborativeArtifactComponent.loaded(
            _artifact(valid_until=build.valid_until),
            source_kind="live",
        ),
        catalog_fingerprint=CATALOG_FINGERPRINT,
        current_consent_version=CONTRIBUTION_VERSION,
        now=now,
        lineage=row,
    )
    assert readiness.state == "stale"
    assert readiness.reason == "privacy_invalid"

    consent = postgres_session.get(CollaborativeContributionConsent, consent.user_id)
    assert consent is not None
    consent.granted_at = now + timedelta(seconds=1)
    consent.withdrawn_at = None
    postgres_session.commit()
    postgres_session.expire_all()
    build = postgres_session.get(CollaborativeArtifactBuild, BUILD_ID)
    assert build is not None
    _assert_invalidated(build)


@pytest.mark.parametrize("mutation", ["consent_version", "granted_at", "delete"])
def test_contribution_authority_changes_invalidate_registered_build(
    postgres_session: Session,
    mutation: str,
) -> None:
    now = datetime.now(UTC)
    _user, consent, build = _register_build(postgres_session, now=now)

    if mutation == "consent_version":
        consent.consent_version = "stage-5-contribution-v2"
    elif mutation == "granted_at":
        consent.granted_at = now - timedelta(days=1)
    else:
        postgres_session.delete(consent)
    postgres_session.flush()
    postgres_session.refresh(build)

    _assert_invalidated(build)


@pytest.mark.parametrize("mutation", ["consent_version", "consented_at", "expires_at"])
def test_personalization_authority_changes_invalidate_registered_build(
    postgres_session: Session,
    mutation: str,
) -> None:
    now = datetime.now(UTC)
    user, _consent, build = _register_build(postgres_session, now=now)

    if mutation == "consent_version":
        user.consent_version = "stage-4-v2"
    elif mutation == "consented_at":
        user.consented_at = now - timedelta(days=30)
    else:
        user.expires_at = now + timedelta(days=20)
    postgres_session.flush()
    postgres_session.refresh(build)

    _assert_invalidated(build)


@pytest.mark.parametrize(
    ("consent_version", "expires_after_days", "withdrawn_after_days"),
    [
        (None, 60, None),
        ("stage-5-contribution-v2", 60, None),
        (CONTRIBUTION_VERSION, 20, None),
        (CONTRIBUTION_VERSION, 60, 20),
    ],
)
def test_registration_rejects_missing_mismatched_or_short_lived_authority(
    postgres_session: Session,
    consent_version: str | None,
    expires_after_days: int,
    withdrawn_after_days: int | None,
) -> None:
    now = datetime.now(UTC)
    user = make_consented_user(
        f"invalid-registration-{expires_after_days}-{withdrawn_after_days}",
        consented_at=now - timedelta(days=60),
        expires_at=now + timedelta(days=expires_after_days),
    )
    postgres_session.add(user)
    postgres_session.flush()
    if consent_version is not None:
        postgres_session.add(
            CollaborativeContributionConsent(
                user_id=user.id,
                consent_version=consent_version,
                granted_at=now - timedelta(days=30),
                withdrawn_at=(
                    now + timedelta(days=withdrawn_after_days)
                    if withdrawn_after_days is not None
                    else None
                ),
            )
        )
    postgres_session.add(
        CollaborativeArtifactBuild(
            build_id=BUILD_ID,
            source_kind="live",
            status="active",
            registered_revision=7,
            invalidation_epoch=0,
            expected_contributor_count=1,
            current_contributor_count=0,
            consent_version=CONTRIBUTION_VERSION,
            catalog_fingerprint=CATALOG_FINGERPRINT,
            interaction_fingerprint=INTERACTION_FINGERPRINT,
            cutoff=now - timedelta(hours=1),
            valid_until=now + timedelta(days=30),
        )
    )
    postgres_session.flush()
    postgres_session.add(CollaborativeArtifactContributor(build_id=BUILD_ID, user_id=user.id))

    with pytest.raises(IntegrityError):
        postgres_session.flush()


def test_contributor_lineage_cannot_be_reassigned(
    postgres_session: Session,
) -> None:
    now = datetime.now(UTC)
    user, _consent, _build = _register_build(postgres_session, now=now)
    postgres_session.commit()

    with pytest.raises(DBAPIError):
        postgres_session.execute(
            update(CollaborativeArtifactContributor)
            .where(
                CollaborativeArtifactContributor.build_id == BUILD_ID,
                CollaborativeArtifactContributor.user_id == user.id,
            )
            .values(user_id=user.id)
        )
    postgres_session.rollback()

    build = postgres_session.get(CollaborativeArtifactBuild, BUILD_ID)
    assert build is not None
    assert build.status == "active"
    assert build.current_contributor_count == 1


def test_registration_and_consent_withdrawal_serialize_without_a_serving_gap(
    postgres_session: Session,
    postgres_engine: Engine,
) -> None:
    now = datetime.now(UTC)
    user, consent, _build = _register_build(
        postgres_session,
        now=now,
        identity="registration-withdrawal-race",
        register_contributor=False,
    )
    user_id = user.id
    consent_user_id = consent.user_id
    postgres_session.commit()

    factory = create_session_factory(postgres_engine)
    registration_locked = Event()
    withdrawal_attempting = Event()
    withdrawal_finished = Event()
    failures: list[Exception] = []

    def register() -> None:
        try:
            with factory() as session:
                session.add(CollaborativeArtifactContributor(build_id=BUILD_ID, user_id=user_id))
                session.flush()
                registration_locked.set()
                if not withdrawal_attempting.wait(timeout=5):
                    raise AssertionError("Consent withdrawal did not reach its commit boundary")
                withdrawal_finished.wait(timeout=1)
                session.commit()
        except Exception as error:
            failures.append(error)
            registration_locked.set()

    def withdraw() -> None:
        try:
            if not registration_locked.wait(timeout=5):
                raise AssertionError("Contributor registration did not acquire its authority lock")
            with factory() as session:
                current = session.get(CollaborativeContributionConsent, consent_user_id)
                assert current is not None
                current.withdrawn_at = now
                withdrawal_attempting.set()
                session.commit()
        except Exception as error:
            failures.append(error)
        finally:
            withdrawal_finished.set()

    registration_thread = Thread(target=register)
    withdrawal_thread = Thread(target=withdraw)
    registration_thread.start()
    withdrawal_thread.start()
    registration_thread.join(timeout=10)
    withdrawal_thread.join(timeout=10)

    assert not registration_thread.is_alive()
    assert not withdrawal_thread.is_alive()
    assert failures == []
    postgres_session.expire_all()
    build = postgres_session.get(CollaborativeArtifactBuild, BUILD_ID)
    assert build is not None
    _assert_invalidated(build)


def test_batch_revocation_invalidates_build_in_the_service_transaction(
    postgres_session: Session,
    postgres_engine: Engine,
) -> None:
    now = datetime.now(UTC)
    _register_build(
        postgres_session,
        now=now,
        identity="batch-revocation-contributor",
        created_at=now - timedelta(days=20),
    )
    postgres_session.commit()

    result = AnonymousSessionRevocationService(
        create_session_factory(postgres_engine),
        batch_size=1,
        clock=lambda: now,
    ).revoke(now - timedelta(days=10))

    assert result.processed == 1
    postgres_session.expire_all()
    build = postgres_session.get(CollaborativeArtifactBuild, BUILD_ID)
    assert build is not None
    _assert_invalidated(build)


def test_retention_cascade_invalidates_and_decrements_expired_contributor(
    postgres_session: Session,
    postgres_engine: Engine,
) -> None:
    now = datetime.now(UTC)
    retention_now = now + timedelta(days=32)
    user, _consent, _build = _register_build(
        postgres_session,
        now=now,
        identity="retention-contributor",
        expires_at=now + timedelta(days=31),
    )
    user_id = user.id
    postgres_session.commit()

    result = RetentionService(
        create_session_factory(postgres_engine),
        batch_size=1,
        clock=lambda: retention_now,
    ).purge(
        RetentionCutoffs(
            events_before=retention_now - timedelta(days=90),
            expired_before=retention_now,
        )
    )

    assert result.processed.expired_users == 1
    postgres_session.expire_all()
    build = postgres_session.get(CollaborativeArtifactBuild, BUILD_ID)
    assert build is not None
    _assert_invalidated(build, contributor_count=0)
    assert postgres_session.get(User, user_id) is None
    assert (
        postgres_session.scalar(select(func.count()).select_from(CollaborativeArtifactContributor))
        == 0
    )
