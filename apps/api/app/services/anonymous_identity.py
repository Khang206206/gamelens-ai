from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import (
    AnonymousSessionRequiredError,
    ConsentVersionOutdatedError,
    CsrfValidationError,
)
from app.core.security import (
    SessionCredential,
    csrf_matches,
    csrf_token,
    generate_session_token,
    session_token_digest,
    utc_now,
)
from app.db.models import User
from app.db.session import begin_read_committed, begin_repeatable_read
from app.repositories.anonymous_users import AnonymousUserRepository
from app.schemas.anonymous_sessions import AnonymousSessionResponse

TOKEN_COLLISION_RETRIES = 3


@dataclass(frozen=True)
class SessionMutationResult:
    response: AnonymousSessionResponse
    status_code: int
    raw_token_to_set: str | None
    now: datetime


class AnonymousIdentityService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        *,
        clock: Callable[[], datetime] = utc_now,
        token_factory: Callable[[], str] = generate_session_token,
    ) -> None:
        self.session = session
        self.settings = settings
        self.clock = clock
        self.token_factory = token_factory
        self.users = AnonymousUserRepository(session)

    def bootstrap(self, credential: SessionCredential | None) -> AnonymousSessionResponse:
        if credential is None:
            raise AnonymousSessionRequiredError()
        begin_repeatable_read(self.session, read_only=True)
        user = self.users.find_by_digest(credential.digest)
        now = self.clock()
        self._require_unexpired(user, now, clear=True)
        assert user is not None
        response = self._response(user, credential.raw_token)
        self.session.rollback()
        return response

    def create_or_reconsent(
        self,
        *,
        requested_consent_version: str,
        credential: SessionCredential | None,
        csrf_candidate: str | None,
    ) -> SessionMutationResult:
        if requested_consent_version != self.settings.consent_version:
            raise ConsentVersionOutdatedError(
                "The submitted consent version is no longer current",
                details={"current_consent_version": self.settings.consent_version},
            )
        now = self.clock()
        if credential is None:
            return self._create(requested_consent_version, now)

        begin_read_committed(self.session)
        user = self.users.find_by_digest(credential.digest, lock=True)
        self._require_unexpired(user, now, clear=True)
        if not csrf_matches(
            self.settings.anonymous_session_secret,
            credential.raw_token,
            csrf_candidate,
        ):
            self.session.rollback()
            raise CsrfValidationError("The CSRF token is missing or invalid")
        assert user is not None
        if user.consent_version == self.settings.consent_version:
            response = self._response(user, credential.raw_token)
            self.session.rollback()
            return SessionMutationResult(response, 200, None, now)

        user.consent_version = self.settings.consent_version
        user.consented_at = now
        user.expires_at = now + timedelta(seconds=self.settings.anonymous_session_ttl_seconds)
        self.session.commit()
        return SessionMutationResult(
            self._response(user, credential.raw_token),
            200,
            credential.raw_token,
            now,
        )

    def delete(
        self,
        credential: SessionCredential | None,
        *,
        csrf_candidate: str | None,
    ) -> None:
        if credential is None:
            raise AnonymousSessionRequiredError()
        begin_read_committed(self.session)
        user = self.users.find_by_digest(credential.digest, lock=True)
        now = self.clock()
        self._require_unexpired(user, now, clear=True)
        if not csrf_matches(
            self.settings.anonymous_session_secret,
            credential.raw_token,
            csrf_candidate,
        ):
            self.session.rollback()
            raise CsrfValidationError("The CSRF token is missing or invalid")
        assert user is not None
        self.session.delete(user)
        self.session.commit()

    def resolve_active_for_update(self, credential: SessionCredential | None) -> User:
        if credential is None:
            raise AnonymousSessionRequiredError()
        user = self.users.find_by_digest(credential.digest, lock=True)
        now = self.clock()
        self._require_unexpired(user, now, clear=True)
        assert user is not None
        if user.consent_version != self.settings.consent_version:
            raise ConsentVersionOutdatedError(
                "The anonymous session consent version is outdated",
                details={"current_consent_version": self.settings.consent_version},
            )
        return user

    def resolve_active(self, credential: SessionCredential | None) -> User:
        if credential is None:
            raise AnonymousSessionRequiredError()
        user = self.users.find_by_digest(credential.digest)
        now = self.clock()
        self._require_unexpired(user, now, clear=True)
        assert user is not None
        if user.consent_version != self.settings.consent_version:
            raise ConsentVersionOutdatedError(
                "The anonymous session consent version is outdated",
                details={"current_consent_version": self.settings.consent_version},
            )
        return user

    def _create(self, consent_version: str, now: datetime) -> SessionMutationResult:
        expires_at = now + timedelta(seconds=self.settings.anonymous_session_ttl_seconds)
        for _attempt in range(TOKEN_COLLISION_RETRIES):
            raw_token = self.token_factory()
            digest = session_token_digest(self.settings.anonymous_session_secret, raw_token)
            begin_read_committed(self.session)
            user = self.users.add_consented(
                digest=digest,
                consent_version=consent_version,
                consented_at=now,
                expires_at=expires_at,
            )
            try:
                self.session.commit()
            except IntegrityError:
                self.session.rollback()
                continue
            return SessionMutationResult(
                self._response(user, raw_token),
                201,
                raw_token,
                now,
            )
        raise RuntimeError("Unable to allocate a unique anonymous session credential")

    def _response(self, user: User, raw_token: str) -> AnonymousSessionResponse:
        if user.consent_version is None or user.consented_at is None or user.expires_at is None:
            raise AnonymousSessionRequiredError(clear=True)
        return AnonymousSessionResponse(
            status=(
                "active"
                if user.consent_version == self.settings.consent_version
                else "consent_outdated"
            ),
            consent_version=user.consent_version,
            current_consent_version=self.settings.consent_version,
            consented_at=user.consented_at,
            expires_at=user.expires_at,
            csrf_token=csrf_token(self.settings.anonymous_session_secret, raw_token),
        )

    @staticmethod
    def _require_unexpired(user: User | None, now: datetime, *, clear: bool) -> None:
        if (
            user is None
            or user.revoked_at is not None
            or user.expires_at is None
            or user.expires_at <= now
        ):
            raise AnonymousSessionRequiredError(clear=clear)
