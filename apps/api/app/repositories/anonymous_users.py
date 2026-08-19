from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User


class AnonymousUserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_digest(self, digest: str, *, lock: bool = False) -> User | None:
        statement = select(User).where(User.anonymous_token_digest == digest)
        if lock:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def add_consented(
        self,
        *,
        digest: str,
        consent_version: str,
        consented_at: datetime,
        expires_at: datetime,
    ) -> User:
        user = User(
            anonymous_token_digest=digest,
            consent_version=consent_version,
            consented_at=consented_at,
            expires_at=expires_at,
            revoked_at=None,
        )
        self.session.add(user)
        return user
