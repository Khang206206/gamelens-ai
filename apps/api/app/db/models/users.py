from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SQLAlchemyEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class PreferenceType(StrEnum):
    GENRE = "genre"
    TAG = "tag"
    PLATFORM = "platform"
    GAME = "game"


class InteractionType(StrEnum):
    VIEWED = "viewed"
    LIKED = "liked"
    DISLIKED = "disliked"
    PLAYED = "played"
    WISHLISTED = "wishlisted"
    RATED = "rated"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    anonymous_key: Mapped[str] = mapped_column(String(100), unique=True)
    preferences: Mapped[list["UserPreference"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    interactions: Mapped[list["Interaction"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    recommendation_events: Mapped[list["RecommendationEvent"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserPreference(TimestampMixin, Base):
    __tablename__ = "user_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "preference_type", "value"),
        CheckConstraint(
            "preference_type IN ('genre', 'tag', 'platform', 'game')",
            name="preference_type_allowed",
        ),
        CheckConstraint("weight >= -1 AND weight <= 1", name="weight_range"),
        Index("ix_user_preferences_user_id_preference_type", "user_id", "preference_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    preference_type: Mapped[PreferenceType] = mapped_column(
        SQLAlchemyEnum(
            PreferenceType,
            native_enum=False,
            create_constraint=False,
            values_callable=lambda enum_type: [item.value for item in enum_type],
            length=20,
        )
    )
    value: Mapped[str] = mapped_column(String(220))
    weight: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=1, server_default="1")
    user: Mapped[User] = relationship(back_populates="preferences")


class Interaction(Base):
    __tablename__ = "interactions"
    __table_args__ = (
        CheckConstraint(
            "interaction_type IN ('viewed', 'liked', 'disliked', 'played', 'wishlisted', 'rated')",
            name="interaction_type_allowed",
        ),
        CheckConstraint(
            "(interaction_type = 'rated' AND value IS NOT NULL "
            "AND value >= 0 AND value <= 10) "
            "OR (interaction_type <> 'rated' AND value IS NULL)",
            name="interaction_value_matches_type",
        ),
        Index("ix_interactions_user_id_occurred_at", "user_id", "occurred_at"),
        Index("ix_interactions_game_id_interaction_type", "game_id", "interaction_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="RESTRICT"),
        nullable=False,
    )
    interaction_type: Mapped[InteractionType] = mapped_column(
        SQLAlchemyEnum(
            InteractionType,
            native_enum=False,
            create_constraint=False,
            values_callable=lambda enum_type: [item.value for item in enum_type],
            length=20,
        )
    )
    value: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    user: Mapped[User] = relationship(back_populates="interactions")


class RecommendationEvent(Base):
    __tablename__ = "recommendation_events"
    __table_args__ = (
        CheckConstraint(
            "jsonb_typeof(request_context) = 'object'",
            name="request_context_object",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "result_summary IS NULL OR jsonb_typeof(result_summary) = 'array'",
            name="result_summary_array",
        ).ddl_if(dialect="postgresql"),
        Index(
            "ix_recommendation_events_user_id_generated_at",
            "user_id",
            "generated_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_name: Mapped[str] = mapped_column(String(100))
    model_version: Mapped[str] = mapped_column(String(100))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    request_context: Mapped[dict[str, Any]] = mapped_column(
        JSON_TYPE,
        default=dict,
        server_default="{}",
    )
    result_summary: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON_TYPE)
    user: Mapped[User] = relationship(back_populates="recommendation_events")
