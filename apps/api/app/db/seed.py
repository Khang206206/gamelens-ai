import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.models import Game, Genre, Platform, Tag
from app.db.session import create_database_engine, create_session_factory

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SEED_PATH = PROJECT_ROOT / "data" / "catalog" / "games.json"


class SeedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProvenanceSeed(SeedModel):
    source: str = Field(min_length=1)
    created_at: date
    license: str = Field(min_length=1)
    limitations: str = Field(min_length=1)


class TaxonomySeed(SeedModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )


class TaxonomyCatalogSeed(SeedModel):
    genres: list[TaxonomySeed]
    tags: list[TaxonomySeed]
    platforms: list[TaxonomySeed]

    @model_validator(mode="after")
    def validate_unique_taxonomies(self) -> "TaxonomyCatalogSeed":
        for values in (self.genres, self.tags, self.platforms):
            names = [item.name.casefold() for item in values]
            slugs = [item.slug for item in values]
            if len(names) != len(set(names)) or len(slugs) != len(set(slugs)):
                raise ValueError("Taxonomy names and slugs must be unique")
        return self


class GameSeed(SeedModel):
    external_id: str | None = Field(default=None, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    slug: str = Field(
        min_length=1,
        max_length=220,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    description: str = Field(min_length=1)
    release_date: date | None = None
    developer: str | None = Field(default=None, max_length=200)
    publisher: str | None = Field(default=None, max_length=200)
    average_rating: Decimal | None = Field(
        default=None,
        ge=0,
        le=10,
        max_digits=4,
        decimal_places=2,
    )
    rating_count: int = Field(default=0, ge=0)
    popularity_score: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        max_digits=10,
        decimal_places=4,
    )
    genre_slugs: list[str] = Field(min_length=1)
    tag_slugs: list[str] = Field(default_factory=list)
    platform_slugs: list[str] = Field(min_length=1)
    cover_image_url: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_unique_taxonomy_references(self) -> "GameSeed":
        for field_name in ("genre_slugs", "tag_slugs", "platform_slugs"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicate slugs")
        return self


class SeedFile(SeedModel):
    provenance: ProvenanceSeed
    taxonomies: TaxonomyCatalogSeed
    games: list[GameSeed] = Field(min_length=25)

    @model_validator(mode="after")
    def validate_references_and_unique_games(self) -> "SeedFile":
        game_slugs = [game.slug for game in self.games]
        if len(game_slugs) != len(set(game_slugs)):
            raise ValueError("Game slugs must be unique")

        available = {
            "genre": {item.slug for item in self.taxonomies.genres},
            "tag": {item.slug for item in self.taxonomies.tags},
            "platform": {item.slug for item in self.taxonomies.platforms},
        }
        for game in self.games:
            references = (
                ("genre", game.genre_slugs),
                ("tag", game.tag_slugs),
                ("platform", game.platform_slugs),
            )
            for taxonomy_type, slugs in references:
                unknown = set(slugs) - available[taxonomy_type]
                if unknown:
                    raise ValueError(
                        f"{game.slug} references unknown {taxonomy_type} slugs: {sorted(unknown)}"
                    )
        return self


class SeedCounts(SeedModel):
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0


class SeedResult(SeedModel):
    games: SeedCounts
    taxonomies: SeedCounts


def load_seed_file(path: Path = DEFAULT_SEED_PATH) -> SeedFile:
    return SeedFile.model_validate_json(path.read_text(encoding="utf-8"))


def _upsert_taxonomy(
    session: Session,
    model: type[Genre] | type[Tag] | type[Platform],
    values: list[TaxonomySeed],
    counts: SeedCounts,
) -> dict[str, Genre | Tag | Platform]:
    existing_by_slug = {item.slug: item for item in session.scalars(select(model)).all()}
    records: dict[str, Genre | Tag | Platform] = {}
    for value in values:
        record = existing_by_slug.get(value.slug)
        if record is None:
            record = model(name=value.name, slug=value.slug)
            session.add(record)
            counts.inserted += 1
        elif record.name != value.name:
            record.name = value.name
            counts.updated += 1
        else:
            counts.unchanged += 1
        records[value.slug] = record
    session.flush()
    return records


def _game_scalar_values(game: GameSeed) -> dict[str, Any]:
    return game.model_dump(
        exclude={"genre_slugs", "tag_slugs", "platform_slugs"},
    )


def _seed_database(session: Session, seed: SeedFile) -> SeedResult:
    taxonomy_counts = SeedCounts()
    genre_by_slug = _upsert_taxonomy(
        session,
        Genre,
        seed.taxonomies.genres,
        taxonomy_counts,
    )
    tag_by_slug = _upsert_taxonomy(
        session,
        Tag,
        seed.taxonomies.tags,
        taxonomy_counts,
    )
    platform_by_slug = _upsert_taxonomy(
        session,
        Platform,
        seed.taxonomies.platforms,
        taxonomy_counts,
    )

    existing_games = session.scalars(
        select(Game).options(
            selectinload(Game.genres),
            selectinload(Game.tags),
            selectinload(Game.platforms),
        )
    ).all()
    games_by_slug = {game.slug: game for game in existing_games}
    game_counts = SeedCounts()

    for game_seed in seed.games:
        game = games_by_slug.get(game_seed.slug)
        inserted = game is None
        changed = inserted
        if game is None:
            game = Game(**_game_scalar_values(game_seed))
            session.add(game)
        else:
            for field, value in _game_scalar_values(game_seed).items():
                if getattr(game, field) != value:
                    setattr(game, field, value)
                    changed = True

        relationships = (
            ("genres", [genre_by_slug[slug] for slug in game_seed.genre_slugs]),
            ("tags", [tag_by_slug[slug] for slug in game_seed.tag_slugs]),
            ("platforms", [platform_by_slug[slug] for slug in game_seed.platform_slugs]),
        )
        associations_changed = False
        for attribute, desired in relationships:
            current = getattr(game, attribute)
            if {item.slug for item in current} != {item.slug for item in desired}:
                setattr(game, attribute, desired)
                associations_changed = True
                changed = True
        if associations_changed and not inserted:
            game.updated_at = datetime.now(UTC)

        if inserted:
            game_counts.inserted += 1
        elif changed:
            game_counts.updated += 1
        else:
            game_counts.unchanged += 1

    session.commit()
    return SeedResult(games=game_counts, taxonomies=taxonomy_counts)


def seed_database(session: Session, seed: SeedFile) -> SeedResult:
    try:
        return _seed_database(session, seed)
    except Exception:
        session.rollback()
        raise


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    seed = load_seed_file()
    engine = create_database_engine(settings.database_url)
    session = create_session_factory(engine)()
    try:
        result = seed_database(session, seed)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()
    logger.info(
        "Seed complete",
        extra={
            "games_inserted": result.games.inserted,
            "games_updated": result.games.updated,
            "games_unchanged": result.games.unchanged,
            "taxonomies_inserted": result.taxonomies.inserted,
            "taxonomies_updated": result.taxonomies.updated,
            "taxonomies_unchanged": result.taxonomies.unchanged,
        },
    )


if __name__ == "__main__":
    main()
