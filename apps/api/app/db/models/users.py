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
    text,
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
    __table_args__ = (
        CheckConstraint(
            "anonymous_token_digest ~ '^[0-9a-f]{64}$'",
            name="anonymous_token_digest_format",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "(consent_version IS NULL AND consented_at IS NULL AND expires_at IS NULL "
            "AND revoked_at IS NOT NULL) OR "
            "(consent_version IS NOT NULL AND length(btrim(consent_version)) > 0 "
            "AND consented_at IS NOT NULL AND expires_at IS NOT NULL "
            "AND expires_at > consented_at)",
            name="consent_lifecycle_valid",
        ).ddl_if(dialect="postgresql"),
        Index("ix_users_expires_at_id", "expires_at", "id"),
        Index("ix_users_revoked_at_id", "revoked_at", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    anonymous_token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    consent_version: Mapped[str | None] = mapped_column(String(100))
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    preferences: Mapped[list["UserPreference"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    interactions: Mapped[list["Interaction"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    recommendation_events: Mapped[list["RecommendationEvent"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
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
        Index(
            "uq_interactions_active_reaction",
            "user_id",
            "game_id",
            unique=True,
            postgresql_where=text(
                "superseded_at IS NULL AND interaction_type IN ('liked', 'disliked')"
            ),
            sqlite_where=text(
                "superseded_at IS NULL AND interaction_type IN ('liked', 'disliked')"
            ),
        ),
        Index(
            "uq_interactions_active_state_type",
            "user_id",
            "game_id",
            "interaction_type",
            unique=True,
            postgresql_where=text(
                "superseded_at IS NULL AND interaction_type IN ('played', 'wishlisted', 'rated')"
            ),
            sqlite_where=text(
                "superseded_at IS NULL AND interaction_type IN ('played', 'wishlisted', 'rated')"
            ),
        ),
        Index(
            "ix_interactions_user_id_active_occurred_at",
            "user_id",
            "superseded_at",
            "occurred_at",
            "id",
        ),
        CheckConstraint(
            "superseded_at IS NULL OR superseded_at >= occurred_at",
            name="superseded_not_before_occurrence",
        ),
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
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
        Index(
            "ix_recommendation_events_generated_at_id",
            "generated_at",
            "id",
        ),
        Index(
            "ix_recommendation_events_policy_generated_at",
            "ranking_policy_name",
            "ranking_policy_version",
            "generated_at",
        ),
        Index(
            "ix_recommendation_events_model_generated_at",
            "model_name",
            "model_version",
            "generated_at",
        ),
        CheckConstraint(
            "(event_schema_version = 'legacy-v1' "
            "AND data_fingerprint IS NULL "
            "AND ranking_policy_name IS NULL "
            "AND ranking_policy_version IS NULL) OR "
            "(event_schema_version = 'stage-4-v1' "
            "AND data_fingerprint ~ '^[0-9a-f]{64}$' "
            "AND ranking_policy_name IS NOT NULL "
            "AND length(btrim(ranking_policy_name)) > 0 "
            "AND ranking_policy_version IS NOT NULL "
            "AND length(btrim(ranking_policy_version)) > 0 "
            "AND result_summary IS NOT NULL)",
            name="stage_4_identity_complete",
        ).ddl_if(dialect="postgresql"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    generation_id: Mapped[str] = mapped_column(String(64), unique=True)
    event_schema_version: Mapped[str] = mapped_column(String(50))
    model_name: Mapped[str] = mapped_column(String(100))
    model_version: Mapped[str] = mapped_column(String(100))
    data_fingerprint: Mapped[str | None] = mapped_column(String(64))
    ranking_policy_name: Mapped[str | None] = mapped_column(String(100))
    ranking_policy_version: Mapped[str | None] = mapped_column(String(100))
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
