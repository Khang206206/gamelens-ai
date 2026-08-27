from collections.abc import Callable
from pathlib import Path
from types import MappingProxyType

import numpy as np
import pytest

from gamelens_recommender import (
    CatalogItem,
    LoadedCollaborativeArtifact,
    TaxonomyValue,
    canonical_snapshot,
)


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


@pytest.fixture
def hand_authored_collaborative_artifact() -> LoadedCollaborativeArtifact:
    """Immutable CSR fixture authored independently of the collaborative trainer."""

    def immutable(values: list[int], dtype: np.dtype[object]) -> np.ndarray:
        payload = np.asarray(values, dtype=dtype).tobytes()
        return np.frombuffer(payload, dtype=dtype)

    item_slugs = (
        "alpha-source",
        "beta-candidate",
        "gamma-empty",
        "omega-candidate",
        "zeta-source",
    )
    manifest = MappingProxyType(
        {
            "build": MappingProxyType({"id": "phase-3a-hand-authored-neighborhood"}),
            "catalog_fingerprint": "a" * 64,
            "interaction_fingerprint": "b" * 64,
            "model": MappingProxyType({"name": "gamelens-item-item-cosine", "version": "1.0.0"}),
        }
    )
    return LoadedCollaborativeArtifact(
        root=Path("phase-3a-hand-authored-neighborhood"),
        manifest=manifest,
        item_slugs=item_slugs,
        item_support=immutable([4, 3, 2, 3, 4], np.dtype("int64")),
        neighbor_indices=immutable([1, 3, 4, 0, 4, 0, 4, 0, 1, 3], np.dtype("int32")),
        neighbor_indptr=immutable([0, 3, 5, 5, 7, 10], np.dtype("int32")),
        similarity_units=immutable(
            [
                577_350,
                866_025,
                500_000,
                577_350,
                577_350,
                866_025,
                577_350,
                500_000,
                577_350,
                577_350,
            ],
            np.dtype("int32"),
        ),
        pair_support=immutable([2, 3, 2, 2, 2, 3, 2, 2, 2, 2], np.dtype("int64")),
        slug_to_index=MappingProxyType({slug: index for index, slug in enumerate(item_slugs)}),
    )
