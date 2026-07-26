from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


def _slug_format_constraint() -> CheckConstraint:
    return CheckConstraint(
        "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'",
        name="slug_format",
    ).ddl_if(dialect="postgresql")


game_genres = Table(
    "game_genres",
    Base.metadata,
    Column("game_id", ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_game_genres_genre_id", "genre_id"),
)

game_tags = Table(
    "game_tags",
    Base.metadata,
    Column("game_id", ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_game_tags_tag_id", "tag_id"),
)

game_platforms = Table(
    "game_platforms",
    Base.metadata,
    Column("game_id", ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
    Column("platform_id", ForeignKey("platforms.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_game_platforms_platform_id", "platform_id"),
)


class Game(TimestampMixin, Base):
    __tablename__ = "games"
    __table_args__ = (
        _slug_format_constraint(),
        CheckConstraint("rating_count >= 0", name="rating_count_non_negative"),
        CheckConstraint(
            "average_rating IS NULL OR (average_rating >= 0 AND average_rating <= 10)",
            name="average_rating_range",
        ),
        CheckConstraint("popularity_score >= 0", name="popularity_score_non_negative"),
        Index("ix_games_title", "title"),
        Index("ix_games_release_date", "release_date"),
        Index("ix_games_popularity_score_id", "popularity_score", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(220), unique=True)
    description: Mapped[str] = mapped_column(Text)
    release_date: Mapped[date | None] = mapped_column(Date)
    developer: Mapped[str | None] = mapped_column(String(200))
    publisher: Mapped[str | None] = mapped_column(String(200))
    average_rating: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    rating_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    popularity_score: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        default=Decimal("0"),
        server_default="0",
    )
    cover_image_url: Mapped[str | None] = mapped_column(String(1000))

    genres: Mapped[list["Genre"]] = relationship(
        secondary=game_genres,
        back_populates="games",
        order_by="Genre.name",
    )
    tags: Mapped[list["Tag"]] = relationship(
        secondary=game_tags,
        back_populates="games",
        order_by="Tag.name",
    )
    platforms: Mapped[list["Platform"]] = relationship(
        secondary=game_platforms,
        back_populates="games",
        order_by="Platform.name",
    )


class Genre(Base):
    __tablename__ = "genres"
    __table_args__ = (_slug_format_constraint(),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    games: Mapped[list[Game]] = relationship(
        secondary=game_genres,
        back_populates="genres",
    )


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (_slug_format_constraint(),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    games: Mapped[list[Game]] = relationship(
        secondary=game_tags,
        back_populates="tags",
    )


class Platform(Base):
    __tablename__ = "platforms"
    __table_args__ = (_slug_format_constraint(),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    games: Mapped[list[Game]] = relationship(
        secondary=game_platforms,
        back_populates="platforms",
    )
