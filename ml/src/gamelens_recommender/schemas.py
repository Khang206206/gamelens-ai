from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from gamelens_recommender.config import FEATURE_CONFIG

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def normalize_text(value: str, *, required: bool = False) -> str:
    normalized = unicodedata.normalize(FEATURE_CONFIG.unicode_normalization, value)
    normalized = " ".join(normalized.replace("\r\n", "\n").replace("\r", "\n").split())
    if required and not normalized:
        raise ValueError("Required catalog text must not be blank")
    return normalized


def _finite_float(value: int | float | Decimal, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{field} must be a number")
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError(f"{field} must be finite") from error
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


@dataclass(frozen=True, order=True)
class TaxonomyValue:
    slug: str
    name: str

    def canonical(self) -> TaxonomyValue:
        slug = normalize_text(self.slug, required=True).lower()
        if SLUG_PATTERN.fullmatch(slug) is None:
            raise ValueError(f"Invalid taxonomy slug: {slug}")
        return TaxonomyValue(slug=slug, name=normalize_text(self.name, required=True))

    def to_dict(self) -> dict[str, str]:
        return {"slug": self.slug, "name": self.name}


def _canonical_taxonomy(
    values: Iterable[TaxonomyValue], *, family: str
) -> tuple[TaxonomyValue, ...]:
    canonical = [value.canonical() for value in values]
    slugs = [value.slug for value in canonical]
    if len(slugs) != len(set(slugs)):
        raise ValueError(f"Duplicate {family} slug in catalog item")
    return tuple(sorted(canonical, key=lambda value: value.slug))


@dataclass(frozen=True)
class CatalogItem:
    slug: str
    title: str
    description: str
    developer: str | None
    publisher: str | None
    average_rating: float | None
    rating_count: int
    popularity_score: float
    genres: tuple[TaxonomyValue, ...] = ()
    tags: tuple[TaxonomyValue, ...] = ()
    platforms: tuple[TaxonomyValue, ...] = ()

    def canonical(self) -> CatalogItem:
        slug = normalize_text(self.slug, required=True).lower()
        if SLUG_PATTERN.fullmatch(slug) is None:
            raise ValueError(f"Invalid game slug: {slug}")
        if type(self.rating_count) is not int:
            raise ValueError("rating_count must be an integer")
        rating_count = self.rating_count
        if rating_count < 0:
            raise ValueError("rating_count must be non-negative")
        rating = (
            None
            if self.average_rating is None
            else _finite_float(self.average_rating, field="average_rating")
        )
        if rating is not None and not 0 <= rating <= 10:
            raise ValueError("average_rating must be between 0 and 10")
        popularity = _finite_float(self.popularity_score, field="popularity_score")
        if popularity < 0:
            raise ValueError("popularity_score must be non-negative")
        return CatalogItem(
            slug=slug,
            title=normalize_text(self.title, required=True),
            description=normalize_text(self.description, required=True),
            developer=normalize_text(self.developer or "") or None,
            publisher=normalize_text(self.publisher or "") or None,
            average_rating=rating,
            rating_count=rating_count,
            popularity_score=popularity,
            genres=_canonical_taxonomy(self.genres, family="genre"),
            tags=_canonical_taxonomy(self.tags, family="tag"),
            platforms=_canonical_taxonomy(self.platforms, family="platform"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "slug": self.slug,
            "title": self.title,
            "description": self.description,
            "developer": self.developer,
            "publisher": self.publisher,
            "average_rating": self.average_rating,
            "rating_count": self.rating_count,
            "popularity_score": self.popularity_score,
            "genres": [value.to_dict() for value in self.genres],
            "tags": [value.to_dict() for value in self.tags],
            "platforms": [value.to_dict() for value in self.platforms],
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> CatalogItem:
        if type(value) is not dict:
            raise ValueError("Catalog item must be an object")

        required_keys = {
            "slug",
            "title",
            "description",
            "developer",
            "publisher",
            "average_rating",
            "rating_count",
            "popularity_score",
            "genres",
            "tags",
            "platforms",
        }
        if set(value) != required_keys:
            raise ValueError("Catalog item fields do not match the artifact schema")

        def required_string(key: str) -> str:
            raw = value[key]
            if type(raw) is not str:
                raise ValueError(f"{key} must be a string")
            return raw

        def optional_string(key: str) -> str | None:
            raw = value[key]
            if raw is None:
                return None
            if type(raw) is not str:
                raise ValueError(f"{key} must be a string or null")
            return raw

        def optional_number(key: str) -> float | None:
            raw = value[key]
            if raw is None:
                return None
            if type(raw) not in {int, float}:
                raise ValueError(f"{key} must be a number or null")
            try:
                return float(raw)
            except OverflowError as error:
                raise ValueError(f"{key} must be a finite number or null") from error

        def required_number(key: str) -> float:
            raw = value[key]
            if type(raw) not in {int, float}:
                raise ValueError(f"{key} must be a number")
            try:
                return float(raw)
            except OverflowError as error:
                raise ValueError(f"{key} must be a finite number") from error

        def taxonomy(key: str) -> tuple[TaxonomyValue, ...]:
            raw = value[key]
            if type(raw) is not list or not all(type(item) is dict for item in raw):
                raise ValueError(f"{key} must be a list of taxonomy objects")
            result: list[TaxonomyValue] = []
            for item in raw:
                if set(item) != {"slug", "name"}:
                    raise ValueError(f"{key} taxonomy fields are invalid")
                slug = item["slug"]
                name = item["name"]
                if type(slug) is not str or type(name) is not str:
                    raise ValueError(f"{key} taxonomy values must be strings")
                result.append(TaxonomyValue(slug=slug, name=name))
            return tuple(result)

        rating_count = value["rating_count"]
        if type(rating_count) is not int:
            raise ValueError("rating_count must be an integer")

        return cls(
            slug=required_string("slug"),
            title=required_string("title"),
            description=required_string("description"),
            developer=optional_string("developer"),
            publisher=optional_string("publisher"),
            average_rating=optional_number("average_rating"),
            rating_count=rating_count,
            popularity_score=required_number("popularity_score"),
            genres=taxonomy("genres"),
            tags=taxonomy("tags"),
            platforms=taxonomy("platforms"),
        ).canonical()


@dataclass(frozen=True)
class CatalogSnapshot:
    items: tuple[CatalogItem, ...]
    fingerprint: str


def canonical_snapshot(items: Iterable[CatalogItem]) -> CatalogSnapshot:
    canonical_items = tuple(
        sorted((item.canonical() for item in items), key=lambda item: item.slug)
    )
    if not canonical_items:
        raise ValueError("Catalog snapshot must contain at least one item")
    slugs = [item.slug for item in canonical_items]
    if len(slugs) != len(set(slugs)):
        raise ValueError("Catalog snapshot contains duplicate game slugs")
    body = json.dumps(
        [item.to_dict() for item in canonical_items],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return CatalogSnapshot(
        items=canonical_items,
        fingerprint=hashlib.sha256(body).hexdigest(),
    )


@dataclass(frozen=True)
class UserContext:
    selected_game_slugs: tuple[str, ...] = ()
    preferred_genres: tuple[str, ...] = ()
    preferred_tags: tuple[str, ...] = ()
    preferred_platforms: tuple[str, ...] = ()
    top_k: int = 10

    def validate(self) -> None:
        if not (self.selected_game_slugs or self.preferred_genres or self.preferred_tags):
            raise ValueError("At least one game, genre, or tag is required")
        if not 1 <= self.top_k <= 20:
            raise ValueError("top_k must be between 1 and 20")
        for values in (
            self.selected_game_slugs,
            self.preferred_genres,
            self.preferred_tags,
            self.preferred_platforms,
        ):
            if len(values) != len(set(values)):
                raise ValueError("User context values must be distinct")


@dataclass(frozen=True)
class ScoreComponent:
    name: str
    raw_units: int
    weight_units: int
    contribution_units: int


@dataclass(frozen=True)
class BaseCandidateScore:
    slug: str
    base_score_units: int
    content_score_units: int
    platform_score_units: int
    popularity_score_units: int


@dataclass(frozen=True)
class SimilarSelectedGame:
    slug: str
    title: str
    similarity_units: int


@dataclass(frozen=True)
class RecommendationEvidence:
    matching_genres: tuple[TaxonomyValue, ...]
    matching_tags: tuple[TaxonomyValue, ...]
    preferred_platforms: tuple[TaxonomyValue, ...]
    similar_selected_games: tuple[SimilarSelectedGame, ...]
    popularity_percentile_units: int


@dataclass(frozen=True)
class RankedRecommendation:
    slug: str
    rank: int
    final_score_units: int
    components: tuple[ScoreComponent, ...]
    evidence: RecommendationEvidence
    explanation_summary: str
    explanation_reasons: tuple[str, ...]


@dataclass(frozen=True)
class RankingResult:
    items: tuple[RankedRecommendation, ...]
    reason: str


FeedbackReaction = Literal["liked", "disliked"]
PositiveFeedbackSourceKind = Literal["liked", "rating"]
PersonalizedRankingReason = Literal[
    "recommendations",
    "no_content_support",
    "no_eligible_candidates",
]


def _validate_aware_datetime(value: datetime | None, *, field: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware datetime")


@dataclass(frozen=True)
class ActiveGameFeedback:
    game_slug: str
    reaction: FeedbackReaction | None = None
    reaction_occurred_at: datetime | None = None
    played: bool = False
    wishlisted: bool = False
    rating: Decimal | None = None
    rating_occurred_at: datetime | None = None

    def validate(self) -> None:
        if type(self.game_slug) is not str or SLUG_PATTERN.fullmatch(self.game_slug) is None:
            raise ValueError("Feedback game slug is invalid")
        if self.reaction not in {None, "liked", "disliked"}:
            raise ValueError("Feedback reaction is invalid")
        if type(self.played) is not bool or type(self.wishlisted) is not bool:
            raise ValueError("Feedback state flags must be booleans")
        if self.reaction is None:
            if self.reaction_occurred_at is not None:
                raise ValueError("Reaction timestamp requires an active reaction")
        else:
            _validate_aware_datetime(
                self.reaction_occurred_at,
                field="reaction_occurred_at",
            )
        if self.rating is None:
            if self.rating_occurred_at is not None:
                raise ValueError("Rating timestamp requires an active rating")
        else:
            if not isinstance(self.rating, Decimal) or not self.rating.is_finite():
                raise ValueError("Feedback rating must be a finite Decimal")
            if not Decimal("0") <= self.rating <= Decimal("10"):
                raise ValueError("Feedback rating must be between 0 and 10")
            _validate_aware_datetime(
                self.rating_occurred_at,
                field="rating_occurred_at",
            )
        if (
            self.reaction is None
            and not self.played
            and not self.wishlisted
            and self.rating is None
        ):
            raise ValueError("Feedback state must contain at least one active value")


@dataclass(frozen=True)
class PositiveFeedbackSource:
    game_slug: str
    kind: PositiveFeedbackSourceKind
    occurred_at: datetime


@dataclass(frozen=True)
class FeedbackPolicyIdentity:
    name: str
    version: str


@dataclass(frozen=True)
class PersonalizedRecommendation:
    slug: str
    rank: int
    base_score_units: int
    base_components: tuple[ScoreComponent, ...]
    base_evidence: RecommendationEvidence
    explanation_summary: str
    explanation_reasons: tuple[str, ...]
    base_weight_units: int
    base_contribution_units: int
    affinity_score_units: int
    affinity_weight_units: int
    affinity_contribution_units: int
    pre_played_score_units: int
    played_factor_units: int
    played_delta_units: int
    final_score_units: int
    adjustment_reasons: tuple[str, ...]


@dataclass(frozen=True)
class PersonalizedRankingResult:
    items: tuple[PersonalizedRecommendation, ...]
    reason: PersonalizedRankingReason
    policy: FeedbackPolicyIdentity
    positive_sources: tuple[PositiveFeedbackSource, ...]
