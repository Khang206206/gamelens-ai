from datetime import UTC, datetime, timedelta

import pytest
from app.commands.operator_safety import (
    database_identity,
    parse_utc,
    resolved_database_identity,
    validate_test_execution_configuration,
)
from app.db.base import Base
from app.db.models import RecommendationEvent, User
from app.services.retention import (
    AnonymousSessionRevocationService,
    RetentionCutoffs,
    RetentionService,
)
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

NOW = datetime(2026, 8, 12, 12, tzinfo=UTC)


@pytest.fixture
def retention_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _user(
    digest: str,
    *,
    expires_at: datetime | None,
    revoked_at: datetime | None = None,
) -> User:
    consented_at = None if expires_at is None else NOW - timedelta(days=200)
    return User(
        anonymous_token_digest=digest,
        consent_version=None if expires_at is None else "stage-4-v1",
        consented_at=consented_at,
        expires_at=expires_at,
        revoked_at=revoked_at,
    )


def _event(user_id: int, generation: str, generated_at: datetime) -> RecommendationEvent:
    return RecommendationEvent(
        user_id=user_id,
        generation_id=generation,
        event_schema_version="stage-4-v1",
        model_name="content-recommender",
        model_version="1.0.0",
        data_fingerprint="a" * 64,
        ranking_policy_name="gamelens-feedback-adjustment",
        ranking_policy_version="1.0.0",
        generated_at=generated_at,
        request_context={"top_k": 1},
        result_summary=[],
    )


def test_retention_preview_is_read_only_and_purge_is_bounded_and_idempotent(
    retention_factory: sessionmaker[Session],
) -> None:
    with retention_factory.begin() as session:
        active = _user("a" * 64, expires_at=NOW + timedelta(days=1))
        expired = _user("b" * 64, expires_at=NOW - timedelta(seconds=1))
        revoked = _user(
            "c" * 64,
            expires_at=None,
            revoked_at=NOW - timedelta(days=10),
        )
        session.add_all([active, expired, revoked])
        session.flush()
        session.add_all(
            [
                _event(active.id, "old", NOW - timedelta(days=91)),
                _event(active.id, "new", NOW - timedelta(days=89)),
            ]
        )

    cutoffs = RetentionCutoffs(
        events_before=NOW - timedelta(days=90),
        expired_before=NOW,
        revoked_before=NOW - timedelta(days=5),
    )
    service = RetentionService(retention_factory, batch_size=1, clock=lambda: NOW)

    preview = service.preview(cutoffs)

    assert preview.eligible.events == 1
    assert preview.eligible.expired_users == 1
    assert preview.eligible.revoked_users == 1
    assert preview.processed.events == 0
    with retention_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 3
        assert session.scalar(select(func.count()).select_from(RecommendationEvent)) == 2

    executed = service.purge(cutoffs)
    repeated = service.purge(cutoffs)

    assert executed.processed.events == 1
    assert executed.processed.expired_users == 1
    assert executed.processed.revoked_users == 1
    assert executed.remaining.events == 0
    assert repeated.processed.events == 0
    assert repeated.processed.expired_users == 0
    assert repeated.processed.revoked_users == 0
    with retention_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1
        assert session.scalar(select(func.count()).select_from(RecommendationEvent)) == 1


def test_default_retention_excludes_revoked_and_legacy_rows(
    retention_factory: sessionmaker[Session],
) -> None:
    with retention_factory.begin() as session:
        session.add(
            _user(
                "d" * 64,
                expires_at=None,
                revoked_at=NOW - timedelta(days=500),
            )
        )
    service = RetentionService(retention_factory, batch_size=10, clock=lambda: NOW)
    cutoffs = RetentionCutoffs(NOW - timedelta(days=90), NOW)

    result = service.purge(cutoffs)

    assert result.eligible.revoked_users == 0
    with retention_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1


def test_revocation_uses_identity_creation_cohort_across_reconsent(
    retention_factory: sessionmaker[Session],
) -> None:
    with retention_factory.begin() as session:
        older = _user("e" * 64, expires_at=NOW + timedelta(days=20))
        older.created_at = NOW - timedelta(days=20)
        older.consented_at = NOW - timedelta(days=1)
        newer = _user("f" * 64, expires_at=NOW + timedelta(days=20))
        newer.created_at = NOW - timedelta(days=1)
        newer.consented_at = NOW - timedelta(hours=12)
        session.add_all([older, newer])
    service = AnonymousSessionRevocationService(
        retention_factory,
        batch_size=1,
        clock=lambda: NOW,
    )
    created_before = NOW - timedelta(days=10)

    preview = service.preview(created_before)
    result = service.revoke(created_before)

    assert preview.created_before == created_before
    assert preview.eligible == 1
    assert result.processed == 1
    assert result.remaining == 0
    with retention_factory() as session:
        rows = list(session.scalars(select(User).order_by(User.id)))
        assert rows[0].revoked_at.replace(tzinfo=UTC) == NOW
        assert rows[1].revoked_at is None


@pytest.mark.parametrize(
    "cutoffs",
    [
        RetentionCutoffs(datetime(2026, 1, 1), NOW),
        RetentionCutoffs(NOW + timedelta(seconds=1), NOW),
    ],
)
def test_retention_rejects_naive_or_future_cutoffs(
    retention_factory: sessionmaker[Session],
    cutoffs: RetentionCutoffs,
) -> None:
    service = RetentionService(retention_factory, batch_size=10, clock=lambda: NOW)

    with pytest.raises(ValueError):
        service.preview(cutoffs)


def test_operator_timestamp_and_database_identity_exclude_credentials() -> None:
    parsed = parse_utc("2026-08-12T19:00:00+07:00")
    authority, fingerprint = database_identity(
        "postgresql+psycopg://operator:super-secret@db.internal:5433/gamelens"
    )

    assert parsed == NOW
    assert authority == "db.internal:5433/gamelens"
    assert len(fingerprint) == 12
    assert "operator" not in authority
    assert "super-secret" not in authority

    resolved = resolved_database_identity(
        "postgresql+psycopg://operator:super-secret@db.internal:5433/gamelens",
        server_address="10.0.0.8",
        server_port=5433,
        database="gamelens",
        schema="public",
    )
    assert resolved.authority == "10.0.0.8:5433/gamelens/public"
    assert len(resolved.fingerprint) == 12
    assert "operator" not in resolved.authority
    assert "super-secret" not in resolved.authority


@pytest.mark.parametrize("value", ["2026-08-12T12:00:00", "not-a-time"])
def test_operator_timestamp_requires_an_explicit_offset(value: str) -> None:
    with pytest.raises(ValueError):
        parse_utc(value)


def test_resolved_database_identity_rejects_database_mismatch() -> None:
    with pytest.raises(RuntimeError, match="does not match DATABASE_URL"):
        resolved_database_identity(
            "postgresql+psycopg://operator:secret@localhost:5432/gamelens",
            server_address="127.0.0.1",
            server_port=5432,
            database="postgres",
            schema="public",
        )


def test_test_operator_execution_requires_the_full_disposable_guard() -> None:
    guarded_url = "postgresql+psycopg://test:test@test-db:5432/gamelens_test"
    validate_test_execution_configuration(
        guarded_url,
        settings_environment="test",
        process_environment="test",
        allow_test_reset="true",
    )

    with pytest.raises(RuntimeError, match="Refusing unsafe test operator action"):
        validate_test_execution_configuration(
            guarded_url,
            settings_environment="test",
            process_environment="development",
            allow_test_reset="true",
        )
    with pytest.raises(RuntimeError, match="must end with '_test'"):
        validate_test_execution_configuration(
            "postgresql+psycopg://test:test@localhost:5432/gamelens",
            settings_environment="test",
            process_environment="test",
            allow_test_reset="true",
        )
