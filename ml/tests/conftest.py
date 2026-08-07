from collections.abc import Callable

import pytest

from gamelens_recommender import CatalogItem, TaxonomyValue, canonical_snapshot


@pytest.fixture
def item_factory() -> Callable[..., CatalogItem]:
    def make_item(
        slug: str,
        *,
        title: str | None = None,
        description: str = "A tactical adventure across a mysterious world",
        genres: tuple[str, ...] = ("strategy",),
        tags: tuple[str, ...] = ("tactical",),
        platforms: tuple[str, ...] = ("pc",),
        rating: float | None = 8.0,
        rating_count: int = 100,
        popularity: float = 50,
    ) -> CatalogItem:
        return CatalogItem(
            slug=slug,
            title=title if title is not None else slug.replace("-", " ").title(),
            description=description,
            developer="Fixture Studio",
            publisher="Fixture Works",
            average_rating=rating,
            rating_count=rating_count,
            popularity_score=popularity,
            genres=tuple(TaxonomyValue(value, value.title()) for value in genres),
            tags=tuple(TaxonomyValue(value, value.title()) for value in tags),
            platforms=tuple(TaxonomyValue(value, value.upper()) for value in platforms),
        )

    return make_item


@pytest.fixture
def snapshot(item_factory: Callable[..., CatalogItem]):
    return canonical_snapshot(
        [
            item_factory("alpha-tactics"),
            item_factory(
                "beta-kingdom",
                tags=("deckbuilding",),
                platforms=("pc", "linux"),
                popularity=80,
            ),
            item_factory(
                "gamma-drift",
                description="Fast arcade racing across neon highways",
                genres=("racing",),
                tags=("arcade",),
                platforms=("console",),
                popularity=30,
            ),
            item_factory(
                "delta-command",
                description="A tactical strategy command simulation",
                platforms=("linux",),
                popularity=60,
            ),
        ]
    )
