import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.core.config import Settings
from app.db.models import (
    CollaborativeContributionConsent,
    CollaborativeDataRevision,
    Game,
    Interaction,
    InteractionType,
    PreferenceType,
    RecommendationEvent,
    User,
    UserPreference,
)
from app.db.seed import load_seed_file, seed_database
from app.db.session import begin_repeatable_read
from app.repositories.collaborative_snapshot import (
    CollaborativeSnapshotError,
    CollaborativeSnapshotRepository,
    begin_collaborative_snapshot,
    verify_data_revision,
)
from app.services.collaborative_snapshot import audit_live_snapshot
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration
CONTRIBUTION_VERSION = "stage-5-contribution-v1"
BASE_CONSENT_VERSION = "stage-4-v1"


def _user(
    session: Session,
    key: str,
    *,
    now: datetime,
    contributes: bool = True,
    expired: bool = False,
    revoked: bool = False,
) -> User:
    user = User(
        anonymous_token_digest=hashlib.sha256(key.encode()).hexdigest(),
        consent_version=BASE_CONSENT_VERSION,
        consented_at=now - timedelta(days=10),
        expires_at=now - timedelta(days=1) if expired else now + timedelta(days=30),
        revoked_at=now - timedelta(hours=1) if revoked else None,
    )
    session.add(user)
    session.flush()
    if contributes:
        session.add(
            CollaborativeContributionConsent(
                user_id=user.id,
                consent_version=CONTRIBUTION_VERSION,
                granted_at=now - timedelta(days=5),
            )
        )
    return user


def _seed_and_games(session: Session) -> dict[str, Game]:
    seed_database(session, load_seed_file())
    return {game.slug: game for game in session.scalars(select(Game)).all()}


def _event(user_id: int, generation_id: str) -> RecommendationEvent:
    return RecommendationEvent(
        user_id=user_id,
        generation_id=generation_id,
        event_schema_version="stage-4-v1",
        model_name="content",
        model_version="1",
        data_fingerprint="a" * 64,
        ranking_policy_name="feedback-rerank",
        ranking_policy_version="1",
        request_context={},
        result_summary=[],
    )


def test_revision_tracks_source_tables_but_not_recommendation_events(
    postgres_session: Session,
) -> None:
    now = datetime.now(UTC)
    user = _user(postgres_session, "revision-user", now=now)
    postgres_session.commit()
    initial = postgres_session.scalar(select(CollaborativeDataRevision.revision))
    assert initial is not None and initial > 0

    postgres_session.add(_event(user.id, "stage5-revision-event"))
    postgres_session.commit()
    after_event = postgres_session.scalar(select(CollaborativeDataRevision.revision))
    assert after_event == initial

    user.expires_at = now + timedelta(days=31)
    postgres_session.commit()
    after_source_change = postgres_session.scalar(select(CollaborativeDataRevision.revision))
    assert after_source_change is not None and after_source_change > initial

    postgres_session.delete(user)
    postgres_session.commit()
    assert postgres_session.get(CollaborativeContributionConsent, user.id) is None
    after_user_delete = postgres_session.scalar(select(CollaborativeDataRevision.revision))
    assert after_user_delete is not None and after_user_delete > after_source_change


def test_extractor_fails_closed_when_revision_singleton_is_missing(
    postgres_session: Session,
) -> None:
    begin_collaborative_snapshot(postgres_session)

    with pytest.raises(CollaborativeSnapshotError) as error:
        CollaborativeSnapshotRepository(postgres_session).extract(
            personalization_consent_version=BASE_CONSENT_VERSION,
            contribution_consent_version=CONTRIBUTION_VERSION,
        )

    assert error.value.code == "revision_unavailable"
    assert "singleton" in str(error.value).lower()


def test_extractor_applies_consent_temporal_and_label_precedence(
    postgres_session: Session,
) -> None:
    games = _seed_and_games(postgres_session)
    now = datetime.now(UTC)
    eligible = _user(postgres_session, "eligible", now=now)
    noncontributing = _user(postgres_session, "noncontributing", now=now, contributes=False)
    expired = _user(postgres_session, "expired", now=now, expired=True)
    revoked = _user(postgres_session, "revoked", now=now, revoked=True)
    withdrawn = _user(postgres_session, "withdrawn", now=now)
    deleted = _user(postgres_session, "deleted", now=now)
    postgres_session.flush()
    withdrawn_consent = postgres_session.get(CollaborativeContributionConsent, withdrawn.id)
    assert withdrawn_consent is not None
    withdrawn_consent.withdrawn_at = now - timedelta(hours=1)
    deleted_id = deleted.id
    rows = [
        UserPreference(
            user_id=eligible.id,
            preference_type="game",
            value="emberfall-tactics",
            weight=Decimal("1"),
        ),
        UserPreference(
            user_id=eligible.id,
            preference_type="game",
            value="starbound-couriers",
            weight=Decimal("1"),
        ),
        UserPreference(
            user_id=eligible.id,
            preference_type=PreferenceType.GENRE,
            value="strategy",
            weight=Decimal("1"),
        ),
        Interaction(
            user_id=eligible.id,
            game_id=games["neon-drift-circuit"].id,
            interaction_type=InteractionType.LIKED,
            value=None,
            occurred_at=now - timedelta(days=1),
        ),
        Interaction(
            user_id=eligible.id,
            game_id=games["verdant-vale"].id,
            interaction_type=InteractionType.RATED,
            value=Decimal("7"),
            occurred_at=now - timedelta(days=1),
        ),
        Interaction(
            user_id=eligible.id,
            game_id=games["clockwork-orchard"].id,
            interaction_type=InteractionType.RATED,
            value=Decimal("6.5"),
            occurred_at=now - timedelta(days=1),
        ),
        Interaction(
            user_id=eligible.id,
            game_id=games["starbound-couriers"].id,
            interaction_type=InteractionType.DISLIKED,
            value=None,
            occurred_at=now - timedelta(days=1),
        ),
        Interaction(
            user_id=eligible.id,
            game_id=games["paper-kingdoms"].id,
            interaction_type=InteractionType.WISHLISTED,
            value=None,
            occurred_at=now - timedelta(days=1),
        ),
        Interaction(
            user_id=eligible.id,
            game_id=games["harborlight"].id,
            interaction_type=InteractionType.LIKED,
            value=None,
            occurred_at=now - timedelta(days=3),
            superseded_at=now - timedelta(days=2),
        ),
        Interaction(
            user_id=eligible.id,
            game_id=games["rift-runners"].id,
            interaction_type=InteractionType.LIKED,
            value=None,
            occurred_at=now + timedelta(days=1),
        ),
        Interaction(
            user_id=noncontributing.id,
            game_id=games["emberfall-tactics"].id,
            interaction_type=InteractionType.LIKED,
            value=None,
            occurred_at=now - timedelta(days=1),
        ),
        Interaction(
            user_id=eligible.id,
            game_id=games["moonroot"].id,
            interaction_type=InteractionType.VIEWED,
            value=None,
            occurred_at=now - timedelta(days=1),
        ),
        Interaction(
            user_id=eligible.id,
            game_id=games["tin-star-sheriff"].id,
            interaction_type=InteractionType.PLAYED,
            value=None,
            occurred_at=now - timedelta(days=1),
        ),
        Interaction(
            user_id=expired.id,
            game_id=games["emberfall-tactics"].id,
            interaction_type=InteractionType.LIKED,
            value=None,
            occurred_at=now - timedelta(days=1),
        ),
        Interaction(
            user_id=revoked.id,
            game_id=games["emberfall-tactics"].id,
            interaction_type=InteractionType.LIKED,
            value=None,
            occurred_at=now - timedelta(days=1),
        ),
        Interaction(
            user_id=withdrawn.id,
            game_id=games["lumen-depths"].id,
            interaction_type=InteractionType.LIKED,
            value=None,
            occurred_at=now - timedelta(days=1),
        ),
        Interaction(
            user_id=deleted.id,
            game_id=games["metro-botanist"].id,
            interaction_type=InteractionType.LIKED,
            value=None,
            occurred_at=now - timedelta(days=1),
        ),
        _event(eligible.id, "stage5-ignored-event"),
    ]
    postgres_session.add_all(rows)
    postgres_session.commit()
    postgres_session.delete(deleted)
    postgres_session.commit()
    assert postgres_session.get(User, deleted_id) is None
    assert postgres_session.get(CollaborativeContributionConsent, deleted_id) is None
    postgres_session.rollback()

    begin_collaborative_snapshot(postgres_session)
    snapshot = CollaborativeSnapshotRepository(postgres_session).extract(
        personalization_consent_version=BASE_CONSENT_VERSION,
        contribution_consent_version=CONTRIBUTION_VERSION,
    )

    assert snapshot.eligible_contributors == 1
    assert snapshot.profiles == (("emberfall-tactics", "neon-drift-circuit", "verdant-vale"),)
    assert "lumen-depths" not in snapshot.profiles[0]
    assert "metro-botanist" not in snapshot.profiles[0]
    assert snapshot.exclusion_counts["noncontributing"] >= 2
    for reason in (
        "disliked",
        "low_rating",
        "played_only",
        "viewed_only",
        "wishlisted_only",
        "superseded",
        "post_cutoff",
        "noncontributing",
        "expired",
        "revoked",
    ):
        assert snapshot.exclusion_counts[reason] >= 1


def test_repeatable_read_snapshot_and_revision_race_are_detected(
    postgres_engine: Engine,
    postgres_session: Session,
    integration_settings: Settings,
) -> None:
    games = _seed_and_games(postgres_session)
    now = datetime.now(UTC)
    user = _user(postgres_session, "concurrent", now=now)
    postgres_session.add(
        Interaction(
            user_id=user.id,
            game_id=games["emberfall-tactics"].id,
            interaction_type=InteractionType.LIKED,
            value=None,
            occurred_at=now - timedelta(days=1),
        )
    )
    postgres_session.commit()

    factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)
    reader = factory()
    writer = factory()
    verifier = factory()
    try:
        begin_collaborative_snapshot(reader)
        repository = CollaborativeSnapshotRepository(reader)
        first = repository.extract(
            personalization_consent_version=BASE_CONSENT_VERSION,
            contribution_consent_version=CONTRIBUTION_VERSION,
        )

        writer.add(
            Interaction(
                user_id=user.id,
                game_id=games["neon-drift-circuit"].id,
                interaction_type=InteractionType.LIKED,
                value=None,
                occurred_at=now,
            )
        )
        writer.commit()

        second = repository.extract(
            personalization_consent_version=BASE_CONSENT_VERSION,
            contribution_consent_version=CONTRIBUTION_VERSION,
        )
        assert second == first

        with pytest.raises(CollaborativeSnapshotError) as error:
            verify_data_revision(verifier, expected_revision=first.data_revision)
        assert error.value.code == "revision_race"

        reader.rollback()
        begin_repeatable_read(reader, read_only=True)
        with pytest.raises(CollaborativeSnapshotError) as stale_error:
            repository.extract(
                personalization_consent_version=BASE_CONSENT_VERSION,
                contribution_consent_version=CONTRIBUTION_VERSION,
            )
        assert stale_error.value.code == "extractor_transaction_invalid"

        reader.rollback()
        begin_collaborative_snapshot(reader)
        refreshed = repository.extract(
            personalization_consent_version=BASE_CONSENT_VERSION,
            contribution_consent_version=CONTRIBUTION_VERSION,
        )
        assert refreshed.profiles == (("emberfall-tactics", "neon-drift-circuit"),)
    finally:
        reader.rollback()
        writer.rollback()
        verifier.rollback()
        reader.close()
        writer.close()
        verifier.close()

    live_settings = Settings(
        _env_file=None,
        environment="test",
        cors_origins=["http://testserver"],
        database_url=integration_settings.database_url,
        collaborative_live_data_enabled=True,
        collaborative_contribution_consent_version=CONTRIBUTION_VERSION,
    )
    report = audit_live_snapshot(factory, settings=live_settings)
    serialized = json.dumps(report, sort_keys=True)
    privacy = report["privacy"]
    assert isinstance(privacy, dict)
    assert report["approved_live_training_eligibility"] is False
    assert privacy["row_level_snapshot_written"] is False
    assert '"user_id":' not in serialized


def test_mutation_after_snapshot_setup_before_extraction_is_a_revision_race(
    postgres_engine: Engine,
    postgres_session: Session,
) -> None:
    games = _seed_and_games(postgres_session)
    now = datetime.now(UTC)
    user = _user(postgres_session, "setup-window", now=now)
    postgres_session.add(
        Interaction(
            user_id=user.id,
            game_id=games["emberfall-tactics"].id,
            interaction_type=InteractionType.LIKED,
            value=None,
            occurred_at=now - timedelta(days=1),
        )
    )
    postgres_session.commit()

    factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)
    reader = factory()
    writer = factory()
    verifier = factory()
    try:
        cutoff = begin_collaborative_snapshot(reader)
        writer.add(
            Interaction(
                user_id=user.id,
                game_id=games["neon-drift-circuit"].id,
                interaction_type=InteractionType.LIKED,
                value=None,
                occurred_at=datetime.now(UTC),
            )
        )
        writer.commit()

        snapshot = CollaborativeSnapshotRepository(reader).extract(
            personalization_consent_version=BASE_CONSENT_VERSION,
            contribution_consent_version=CONTRIBUTION_VERSION,
        )

        assert snapshot.cutoff == cutoff
        assert snapshot.profiles == (("emberfall-tactics",),)
        with pytest.raises(CollaborativeSnapshotError) as error:
            verify_data_revision(verifier, expected_revision=snapshot.data_revision)
        assert error.value.code == "revision_race"
    finally:
        reader.rollback()
        writer.rollback()
        verifier.rollback()
        reader.close()
        writer.close()
        verifier.close()
