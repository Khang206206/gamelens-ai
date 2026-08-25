from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class CollaborativeContributionConsent(TimestampMixin, Base):
    """Separate, optional authority for aggregate collaborative-data contribution."""

    __tablename__ = "collaborative_contribution_consents"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(consent_version)) > 0",
            name="consent_version_non_blank",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "withdrawn_at IS NULL OR withdrawn_at >= granted_at",
            name="withdrawal_not_before_grant",
        ).ddl_if(dialect="postgresql"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    consent_version: Mapped[str] = mapped_column(String(100), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CollaborativeDataRevision(Base):
    """Single monotonic source revision used to invalidate derived collaborative data."""

    __tablename__ = "collaborative_data_revision"
    __table_args__ = (
        CheckConstraint("singleton_id = 1", name="singleton_id_is_one"),
        CheckConstraint("revision >= 0", name="revision_non_negative"),
    )

    singleton_id: Mapped[int] = mapped_column(
        SmallInteger,
        primary_key=True,
        default=1,
        server_default="1",
    )
    revision: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
