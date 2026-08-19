from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import utc_now
from app.db.models import RecommendationEvent, User


@dataclass(frozen=True)
class RetentionCutoffs:
    events_before: datetime
    expired_before: datetime
    revoked_before: datetime | None = None


@dataclass(frozen=True)
class RetentionCounts:
    events: int
    expired_users: int
    revoked_users: int


@dataclass(frozen=True)
class RetentionResult:
    cutoffs: RetentionCutoffs
    eligible: RetentionCounts
    processed: RetentionCounts
    remaining: RetentionCounts


class RetentionService:
    """Preview and purge bounded anonymous data without exposing row content."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        batch_size: int,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not 1 <= batch_size <= 10_000:
            raise ValueError("batch_size must be between 1 and 10000")
        self.session_factory = session_factory
        self.batch_size = batch_size
        self.clock = clock

    def preview(self, cutoffs: RetentionCutoffs) -> RetentionResult:
        self._validate_cutoffs(cutoffs)
        eligible = self._counts(cutoffs)
        return RetentionResult(
            cutoffs=cutoffs,
            eligible=eligible,
            processed=RetentionCounts(0, 0, 0),
            remaining=eligible,
        )

    def purge(self, cutoffs: RetentionCutoffs) -> RetentionResult:
        self._validate_cutoffs(cutoffs)
        eligible = self._counts(cutoffs)
        events = self._delete_batches(
            RecommendationEvent,
            RecommendationEvent.generated_at <= cutoffs.events_before,
        )
        expired_users = self._delete_batches(
            User,
            User.consent_version.is_not(None),
            User.expires_at.is_not(None),
            User.expires_at <= cutoffs.expired_before,
            User.revoked_at.is_(None),
        )
        revoked_users = 0
        if cutoffs.revoked_before is not None:
            revoked_users = self._delete_batches(
                User,
                User.revoked_at.is_not(None),
                User.revoked_at <= cutoffs.revoked_before,
            )
        processed = RetentionCounts(events, expired_users, revoked_users)
        return RetentionResult(
            cutoffs=cutoffs,
            eligible=eligible,
            processed=processed,
            remaining=self._counts(cutoffs),
        )

    def _counts(self, cutoffs: RetentionCutoffs) -> RetentionCounts:
        with self.session_factory() as session:
            events = session.scalar(
                select(func.count())
                .select_from(RecommendationEvent)
                .where(RecommendationEvent.generated_at <= cutoffs.events_before)
            )
            expired = session.scalar(
                select(func.count())
                .select_from(User)
                .where(
                    User.consent_version.is_not(None),
                    User.expires_at.is_not(None),
                    User.expires_at <= cutoffs.expired_before,
                    User.revoked_at.is_(None),
                )
            )
            revoked = 0
            if cutoffs.revoked_before is not None:
                revoked = session.scalar(
                    select(func.count())
                    .select_from(User)
                    .where(
                        User.revoked_at.is_not(None),
                        User.revoked_at <= cutoffs.revoked_before,
                    )
                )
            session.rollback()
        return RetentionCounts(int(events or 0), int(expired or 0), int(revoked or 0))

    def _delete_batches(
        self,
        model: type[RecommendationEvent] | type[User],
        *filters: object,
    ) -> int:
        processed = 0
        while True:
            with self.session_factory() as session:
                ids = list(
                    session.scalars(
                        select(model.id)
                        .where(*filters)
                        .order_by(model.id)
                        .limit(self.batch_size)
                        .with_for_update(skip_locked=True)
                    ).all()
                )
                if not ids:
                    session.rollback()
                    return processed
                result = session.execute(delete(model).where(model.id.in_(ids), *filters))
                processed += int(result.rowcount or 0)
                session.commit()

    def _validate_cutoffs(self, cutoffs: RetentionCutoffs) -> None:
        now = self.clock()
        values = [cutoffs.events_before, cutoffs.expired_before]
        if cutoffs.revoked_before is not None:
            values.append(cutoffs.revoked_before)
        if any(value.tzinfo is None or value.utcoffset() is None for value in values):
            raise ValueError("retention cutoffs must be timezone-aware")
        if any(value > now for value in values):
            raise ValueError("retention cutoffs must not be in the future")


@dataclass(frozen=True)
class RevocationResult:
    created_before: datetime
    eligible: int
    processed: int
    remaining: int


class AnonymousSessionRevocationService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        batch_size: int,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not 1 <= batch_size <= 10_000:
            raise ValueError("batch_size must be between 1 and 10000")
        self.session_factory = session_factory
        self.batch_size = batch_size
        self.clock = clock

    def preview(self, created_before: datetime) -> RevocationResult:
        self._validate_cutoff(created_before)
        eligible = self._count(created_before, self.clock())
        return RevocationResult(created_before, eligible, 0, eligible)

    def revoke(self, created_before: datetime) -> RevocationResult:
        self._validate_cutoff(created_before)
        now = self.clock()
        eligible = self._count(created_before, now)
        processed = 0
        while True:
            with self.session_factory() as session:
                ids = list(
                    session.scalars(
                        select(User.id)
                        .where(*self._active_filters(created_before, now))
                        .order_by(User.id)
                        .limit(self.batch_size)
                        .with_for_update(skip_locked=True)
                    ).all()
                )
                if not ids:
                    session.rollback()
                    break
                result = session.execute(
                    update(User)
                    .where(User.id.in_(ids), *self._active_filters(created_before, now))
                    .values(revoked_at=now)
                )
                processed += int(result.rowcount or 0)
                session.commit()
        return RevocationResult(
            created_before,
            eligible,
            processed,
            self._count(created_before, now),
        )

    @staticmethod
    def _active_filters(created_before: datetime, now: datetime) -> tuple[object, ...]:
        return (
            User.consent_version.is_not(None),
            User.consented_at.is_not(None),
            User.created_at <= created_before,
            User.expires_at.is_not(None),
            User.expires_at > now,
            User.revoked_at.is_(None),
        )

    def _count(self, created_before: datetime, now: datetime) -> int:
        with self.session_factory() as session:
            count = session.scalar(
                select(func.count())
                .select_from(User)
                .where(*self._active_filters(created_before, now))
            )
            session.rollback()
        return int(count or 0)

    def _validate_cutoff(self, cutoff: datetime) -> None:
        if cutoff.tzinfo is None or cutoff.utcoffset() is None:
            raise ValueError("revocation cutoff must be timezone-aware")
        if cutoff > self.clock():
            raise ValueError("revocation cutoff must not be in the future")
