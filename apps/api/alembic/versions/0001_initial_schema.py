"""Create the Stage 1 relational schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("developer", sa.String(length=200), nullable=True),
        sa.Column("publisher", sa.String(length=200), nullable=True),
        sa.Column("average_rating", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("rating_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "popularity_score",
            sa.Numeric(precision=10, scale=4),
            server_default="0",
            nullable=False,
        ),
        sa.Column("cover_image_url", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "average_rating IS NULL OR (average_rating >= 0 AND average_rating <= 10)",
            name=op.f("ck_games_average_rating_range"),
        ),
        sa.CheckConstraint(
            "popularity_score >= 0",
            name=op.f("ck_games_popularity_score_non_negative"),
        ),
        sa.CheckConstraint(
            "rating_count >= 0",
            name=op.f("ck_games_rating_count_non_negative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_games")),
        sa.UniqueConstraint("slug", name=op.f("uq_games_slug")),
    )
    op.create_index("ix_games_popularity_score_id", "games", ["popularity_score", "id"])
    op.create_index("ix_games_release_date", "games", ["release_date"])
    op.create_index("ix_games_title", "games", ["title"])

    for table_name in ("genres", "tags", "platforms"):
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("slug", sa.String(length=100), nullable=False),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table_name}")),
            sa.UniqueConstraint("name", name=op.f(f"uq_{table_name}_name")),
            sa.UniqueConstraint("slug", name=op.f(f"uq_{table_name}_slug")),
        )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("anonymous_key", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("anonymous_key", name=op.f("uq_users_anonymous_key")),
    )

    association_specs = (
        ("game_genres", "genre_id", "genres"),
        ("game_tags", "tag_id", "tags"),
        ("game_platforms", "platform_id", "platforms"),
    )
    for table_name, taxonomy_column, taxonomy_table in association_specs:
        op.create_table(
            table_name,
            sa.Column("game_id", sa.Integer(), nullable=False),
            sa.Column(taxonomy_column, sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["game_id"],
                ["games.id"],
                name=op.f(f"fk_{table_name}_game_id_games"),
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                [taxonomy_column],
                [f"{taxonomy_table}.id"],
                name=op.f(f"fk_{table_name}_{taxonomy_column}_{taxonomy_table}"),
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint(
                "game_id",
                taxonomy_column,
                name=op.f(f"pk_{table_name}"),
            ),
        )
        op.create_index(f"ix_{table_name}_{taxonomy_column}", table_name, [taxonomy_column])

    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("preference_type", sa.String(length=20), nullable=False),
        sa.Column("value", sa.String(length=220), nullable=False),
        sa.Column(
            "weight",
            sa.Numeric(precision=4, scale=3),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "preference_type IN ('genre', 'tag', 'platform', 'game')",
            name=op.f("ck_user_preferences_preference_type_allowed"),
        ),
        sa.CheckConstraint(
            "weight >= -1 AND weight <= 1",
            name=op.f("ck_user_preferences_weight_range"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_preferences_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_preferences")),
        sa.UniqueConstraint(
            "user_id",
            "preference_type",
            "value",
            name=op.f("uq_user_preferences_user_id_preference_type_value"),
        ),
    )
    op.create_index(
        "ix_user_preferences_user_id_preference_type",
        "user_preferences",
        ["user_id", "preference_type"],
    )

    op.create_table(
        "interactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("interaction_type", sa.String(length=20), nullable=False),
        sa.Column("value", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "interaction_type IN ('viewed', 'liked', 'disliked', 'played', 'wishlisted', 'rated')",
            name=op.f("ck_interactions_interaction_type_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            name=op.f("fk_interactions_game_id_games"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_interactions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interactions")),
    )
    op.create_index(
        "ix_interactions_game_id_interaction_type",
        "interactions",
        ["game_id", "interaction_type"],
    )
    op.create_index(
        "ix_interactions_user_id_occurred_at",
        "interactions",
        ["user_id", "occurred_at"],
    )

    op.create_table(
        "recommendation_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "request_context",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "result_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_recommendation_events_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendation_events")),
    )
    op.create_index(
        "ix_recommendation_events_user_id_generated_at",
        "recommendation_events",
        ["user_id", "generated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_recommendation_events_user_id_generated_at",
        table_name="recommendation_events",
    )
    op.drop_table("recommendation_events")
    op.drop_index("ix_interactions_user_id_occurred_at", table_name="interactions")
    op.drop_index("ix_interactions_game_id_interaction_type", table_name="interactions")
    op.drop_table("interactions")
    op.drop_index(
        "ix_user_preferences_user_id_preference_type",
        table_name="user_preferences",
    )
    op.drop_table("user_preferences")
    for table_name, taxonomy_column in (
        ("game_platforms", "platform_id"),
        ("game_tags", "tag_id"),
        ("game_genres", "genre_id"),
    ):
        op.drop_index(f"ix_{table_name}_{taxonomy_column}", table_name=table_name)
        op.drop_table(table_name)
    op.drop_table("users")
    op.drop_table("platforms")
    op.drop_table("tags")
    op.drop_table("genres")
    op.drop_index("ix_games_title", table_name="games")
    op.drop_index("ix_games_release_date", table_name="games")
    op.drop_index("ix_games_popularity_score_id", table_name="games")
    op.drop_table("games")
