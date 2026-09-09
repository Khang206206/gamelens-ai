import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.core.config import Settings
from app.db.base import Base
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
from app.repositories import collaborative_snapshot as snapshot_repository
from app.repositories.collaborative_snapshot import (
    CollaborativeSnapshotError,
    CollaborativeSnapshotRepository,
    begin_collaborative_snapshot,
    verify_data_revision,
)
from app.services.collaborative_snapshot import audit_live_snapshot
from sqlalchemy import Engine, func, select
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
    assert snapshot.profile_user_ids == (eligible.id,)
    assert snapshot.profile_authority_valid_until == (eligible.expires_at,)
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


@pytest.mark.parametrize(
    "mutation", ["interaction", "preference", "withdrawal", "revocation", "deletion", "catalog"]
)
def test_repeatable_read_snapshot_and_revision_race_are_detected(
    postgres_engine: Engine,
    postgres_session: Session,
    integration_settings: Settings,
    mutation: str,
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

        if mutation == "interaction":
            writer.add(
                Interaction(
                    user_id=user.id,
                    game_id=games["neon-drift-circuit"].id,
                    interaction_type=InteractionType.LIKED,
                    occurred_at=now,
                )
            )
        elif mutation == "preference":
            writer.add(
                UserPreference(
                    user_id=user.id,
                    preference_type=PreferenceType.GAME,
                    value="neon-drift-circuit",
                    weight=Decimal("1"),
                )
            )
        elif mutation == "withdrawal":
            writer.get(CollaborativeContributionConsent, user.id).withdrawn_at = now
        elif mutation == "revocation":
            writer.get(User, user.id).revoked_at = now
        elif mutation == "deletion":
            writer.delete(writer.get(User, user.id))
        else:
            writer.get(Game, games["emberfall-tactics"].id).description = "Changed catalog"
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
        if mutation in {"interaction", "preference"}:
            assert refreshed.profiles == (("emberfall-tactics", "neon-drift-circuit"),)
        elif mutation == "catalog":
            assert refreshed.profiles == first.profiles
            assert refreshed.catalog_fingerprint != first.catalog_fingerprint
        else:
            assert refreshed.profiles == ()
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


@pytest.mark.parametrize(
    ("field", "offset", "eligible", "reason"),
    [
        ("consented_at", -1, True, None),
        ("consented_at", 0, True, None),
        ("consented_at", 1, False, "base_consent_mismatch"),
        ("granted_at", -1, True, None),
        ("granted_at", 0, True, None),
        ("granted_at", 1, False, "noncontributing"),
        ("expires_at", -1, False, "expired"),
        ("expires_at", 0, False, "expired"),
        ("expires_at", 1, True, None),
        ("revoked_at", -1, False, "revoked"),
        ("revoked_at", 0, False, "revoked"),
        ("revoked_at", 1, True, None),
        ("withdrawn_at", -1, False, "noncontributing"),
        ("withdrawn_at", 0, False, "noncontributing"),
        ("withdrawn_at", 1, True, None),
        ("base_version", 0, False, "base_consent_mismatch"),
        ("contribution_version", 0, False, "noncontributing"),
        ("missing_contribution", 0, False, "noncontributing"),
        ("cleared_consent", 0, False, "base_consent_mismatch"),
    ],
)
def test_authority_exact_as_of_boundaries(
    postgres_session: Session, field: str, offset: int, eligible: bool, reason: str | None
) -> None:
    games = _seed_and_games(postgres_session)
    cutoff = postgres_session.scalar(select(func.clock_timestamp())) - timedelta(days=1)
    user = _user(postgres_session, "boundary", now=cutoff)
    consent = postgres_session.get(CollaborativeContributionConsent, user.id)
    boundary = cutoff + timedelta(microseconds=offset)
    if field == "base_version":
        user.consent_version = "outdated"
    elif field == "contribution_version":
        consent.consent_version = "outdated"
    elif field == "missing_contribution":
        postgres_session.delete(consent)
    elif field == "cleared_consent":
        user.consent_version = user.consented_at = user.expires_at = None
        user.revoked_at = cutoff
    else:
        target = consent if field in {"granted_at", "withdrawn_at"} else user
        setattr(target, field, boundary)
    postgres_session.add(
        Interaction(
            user_id=user.id,
            game_id=games["emberfall-tactics"].id,
            interaction_type=InteractionType.LIKED,
            occurred_at=cutoff,
        )
    )
    postgres_session.commit()
    begin_collaborative_snapshot(postgres_session, cutoff=cutoff)
    snapshot = CollaborativeSnapshotRepository(postgres_session).extract(
        personalization_consent_version=BASE_CONSENT_VERSION,
        contribution_consent_version=CONTRIBUTION_VERSION,
    )
    assert snapshot.cutoff == cutoff
    assert snapshot.profiles == ((("emberfall-tactics",),) if eligible else ())
    assert snapshot.eligible_contributors == int(eligible)
    if eligible:
        horizon = (
            boundary
            if field in {"expires_at", "revoked_at", "withdrawn_at"}
            else cutoff + timedelta(days=30)
        )
        assert snapshot.profile_authority_valid_until == (horizon,)
        assert snapshot.profile_user_ids == (user.id,)
    else:
        assert snapshot.exclusion_counts[reason] == 1
        assert snapshot.profile_authority_valid_until == ()


@pytest.mark.parametrize("offset", [-1, 0, 1])
@pytest.mark.parametrize("field", ["occurred_at", "superseded_at", "created_at", "updated_at"])
def test_label_exact_as_of_boundaries(postgres_session: Session, field: str, offset: int) -> None:
    games = _seed_and_games(postgres_session)
    cutoff = postgres_session.scalar(select(func.clock_timestamp())) - timedelta(days=1)
    user = _user(postgres_session, "label-boundary", now=cutoff)
    boundary = cutoff + timedelta(microseconds=offset)
    if field in {"created_at", "updated_at"}:
        row = UserPreference(
            user_id=user.id,
            preference_type=PreferenceType.GAME,
            value="emberfall-tactics",
            weight=Decimal("0.001"),
            created_at=cutoff - timedelta(days=1),
            updated_at=cutoff - timedelta(days=1),
        )
    else:
        row = Interaction(
            user_id=user.id,
            game_id=games["emberfall-tactics"].id,
            interaction_type=InteractionType.LIKED,
            occurred_at=cutoff - timedelta(days=1),
        )
    setattr(row, field, boundary)
    postgres_session.add(row)
    postgres_session.commit()
    begin_collaborative_snapshot(postgres_session, cutoff=cutoff)
    snapshot = CollaborativeSnapshotRepository(postgres_session).extract(
        personalization_consent_version=BASE_CONSENT_VERSION,
        contribution_consent_version=CONTRIBUTION_VERSION,
    )
    positive = offset > 0 if field == "superseded_at" else offset <= 0
    assert snapshot.profiles == ((("emberfall-tactics",),) if positive else ((),))
    expected = {"base_consent_mismatch": 0, "expired": 0, "revoked": 0, "noncontributing": 0}
    if not positive and field in {"occurred_at", "superseded_at"}:
        expected["post_cutoff" if field == "occurred_at" else "superseded"] = 1
    assert snapshot.exclusion_counts == expected


@pytest.mark.parametrize(
    ("rating", "saved", "reaction", "positive", "reason"),
    [
        ("6.99", None, None, False, "low_rating"),
        ("7.00", None, None, True, None),
        ("7.01", None, None, True, None),
        ("0", None, None, False, "low_rating"),
        ("10", "1", "liked", True, None),
        ("10", "1", "disliked", False, "disliked"),
        ("0", "0.001", None, True, None),
        (None, "0", None, False, None),
        (None, "-1", None, False, None),
    ],
)
def test_rating_preference_and_duplicate_source_matrix(
    postgres_session: Session,
    rating: str | None,
    saved: str | None,
    reaction: str | None,
    positive: bool,
    reason: str | None,
) -> None:
    games = _seed_and_games(postgres_session)
    now = postgres_session.scalar(select(func.clock_timestamp()))
    user = _user(postgres_session, "signals", now=now)
    if saved is not None:
        postgres_session.add(
            UserPreference(
                user_id=user.id,
                preference_type=PreferenceType.GAME,
                value="emberfall-tactics",
                weight=Decimal(saved),
            )
        )
    for kind, value in [("rated", rating), (reaction, None)]:
        if kind is None or (kind == "rated" and value is None):
            continue
        postgres_session.add(
            Interaction(
                user_id=user.id,
                game_id=games["emberfall-tactics"].id,
                interaction_type=kind,
                value=Decimal(value) if value is not None else None,
                occurred_at=now,
            )
        )
    postgres_session.add(
        UserPreference(
            user_id=user.id,
            preference_type=PreferenceType.GAME,
            value="unknown-game",
            weight=Decimal("1"),
        )
    )
    postgres_session.commit()
    begin_collaborative_snapshot(postgres_session)
    snapshot = CollaborativeSnapshotRepository(postgres_session).extract(
        personalization_consent_version=BASE_CONSENT_VERSION,
        contribution_consent_version=CONTRIBUTION_VERSION,
    )
    assert snapshot.profiles == ((("emberfall-tactics",),) if positive else ((),))
    expected = {
        "base_consent_mismatch": 0,
        "expired": 0,
        "revoked": 0,
        "noncontributing": 0,
        "unknown_game": 1,
    }
    if reason:
        expected[reason] = 1
    assert snapshot.exclusion_counts == expected


def _database_rows(engine: Engine) -> dict[str, list[dict]]:
    # Compare all application columns, including timestamps/revisions/registry, not just counts.
    with engine.connect() as connection:
        return {
            table.name: [
                dict(row)
                for row in connection.execute(
                    select(table).order_by(*table.primary_key.columns)
                ).mappings()
            ]
            for table in Base.metadata.sorted_tables
        }


@pytest.mark.parametrize("cohort", ["empty", "positive", "catalog_missing"])
def test_audit_is_aggregate_only_and_preserves_all_database_rows(
    postgres_engine: Engine,
    postgres_session: Session,
    integration_settings: Settings,
    cohort: str,
) -> None:
    if cohort != "catalog_missing":
        _seed_and_games(postgres_session)
    now = postgres_session.scalar(select(func.clock_timestamp()))
    user = _user(postgres_session, "private-audit-marker", now=now)
    postgres_session.add(_event(user.id, "private-event-marker"))
    if cohort == "positive":
        postgres_session.add(
            UserPreference(
                user_id=user.id,
                preference_type=PreferenceType.GAME,
                value="emberfall-tactics",
                weight=Decimal("1"),
            )
        )
    postgres_session.commit()
    before = _database_rows(postgres_engine)
    settings = Settings(
        _env_file=None,
        environment="test",
        cors_origins=["http://testserver"],
        database_url=integration_settings.database_url,
        collaborative_live_data_enabled=True,
        collaborative_contribution_consent_version=CONTRIBUTION_VERSION,
    )
    factory = sessionmaker(bind=postgres_engine)
    if cohort == "catalog_missing":
        with pytest.raises(CollaborativeSnapshotError) as error:
            audit_live_snapshot(factory, settings=settings)
        assert error.value.code == "catalog_mismatch"
    else:
        report = audit_live_snapshot(factory, settings=settings)
        assert report["status"] == "insufficient_data"
        assert report["ready_for_functional_build"] is False
        assert report["approved_live_training_eligibility"] is False
        assert report["candidate_profiles"]["positive_edges"] == int(cohort == "positive")
        assert report["privacy"] == {
            "aggregate_only": True,
            "user_identifiers_emitted": False,
            "row_level_snapshot_written": False,
            "cohort_mapping_written": False,
        }
        serialized = json.dumps(report)
        for private in (
            user.anonymous_token_digest,
            "private-event-marker",
            '"user_id"',
            '"profile_user_ids"',
            '"profiles"',
            '"expires_at"',
        ):
            assert private not in serialized
    assert _database_rows(postgres_engine) == before


@pytest.mark.parametrize("limit_name", ["MAX_PROFILES", "MAX_POSITIVE_EDGES", "MAX_SOURCE_ROWS"])
def test_extraction_limits_fail_closed_without_mutation(
    postgres_engine: Engine,
    postgres_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    limit_name: str,
) -> None:
    games = _seed_and_games(postgres_session)
    now = postgres_session.scalar(select(func.clock_timestamp()))
    user = _user(postgres_session, "bounded", now=now)
    postgres_session.add(
        UserPreference(
            user_id=user.id,
            preference_type=PreferenceType.GAME,
            value="emberfall-tactics",
            weight=Decimal("1"),
        )
    )
    postgres_session.add(
        Interaction(
            user_id=user.id,
            game_id=games["emberfall-tactics"].id,
            interaction_type=InteractionType.VIEWED,
            occurred_at=now,
        )
    )
    postgres_session.commit()
    before = _database_rows(postgres_engine)
    monkeypatch.setattr(snapshot_repository, limit_name, 0)
    begin_collaborative_snapshot(postgres_session)
    with pytest.raises(CollaborativeSnapshotError) as error:
        CollaborativeSnapshotRepository(postgres_session).extract(
            personalization_consent_version=BASE_CONSENT_VERSION,
            contribution_consent_version=CONTRIBUTION_VERSION,
        )
    assert error.value.code == "snapshot_limit_exceeded"
    postgres_session.rollback()
    assert _database_rows(postgres_engine) == before


def test_database_time_cutoff_is_pinned_and_transaction_rejects_writes(
    postgres_engine: Engine, postgres_session: Session
) -> None:
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    with postgres_engine.connect() as clock:
        before = clock.scalar(select(func.clock_timestamp()))
        cutoff = begin_collaborative_snapshot(postgres_session)
        after = clock.scalar(select(func.clock_timestamp()))
    assert before <= cutoff <= after
    assert postgres_session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
    assert postgres_session.scalar(text("SHOW transaction_read_only")) == "on"
    # A real write attempt proves the database enforces the read-only transaction.
    with pytest.raises(DBAPIError) as error:
        postgres_session.execute(text("UPDATE collaborative_data_revision SET revision = revision"))
    assert error.value.orig.sqlstate == "25006"


@pytest.mark.parametrize("kind", ["naive", "future"])
def test_invalid_recovery_cutoff_fails_closed(postgres_session: Session, kind: str) -> None:
    cutoff = datetime(2020, 1, 1) if kind == "naive" else datetime(9999, 1, 1, tzinfo=UTC)
    with pytest.raises(CollaborativeSnapshotError) as error:
        begin_collaborative_snapshot(postgres_session, cutoff=cutoff)
    assert error.value.code == "snapshot_cutoff_invalid"
    with pytest.raises(CollaborativeSnapshotError) as extraction_error:
        CollaborativeSnapshotRepository(postgres_session).extract(
            personalization_consent_version=BASE_CONSENT_VERSION,
            contribution_consent_version=CONTRIBUTION_VERSION,
        )
    assert extraction_error.value.code == "extractor_transaction_invalid"
