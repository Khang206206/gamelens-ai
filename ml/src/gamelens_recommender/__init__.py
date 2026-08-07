"""Deterministic artifact-backed recommendation primitives."""

from gamelens_recommender.artifacts import ArtifactError, LoadedArtifact, load_artifact
from gamelens_recommender.ranking import ContentRanker, InsufficientContextError
from gamelens_recommender.schemas import (
    CatalogItem,
    CatalogSnapshot,
    TaxonomyValue,
    UserContext,
    canonical_snapshot,
)
from gamelens_recommender.training import build_artifact

__all__ = [
    "ArtifactError",
    "CatalogItem",
    "CatalogSnapshot",
    "ContentRanker",
    "InsufficientContextError",
    "LoadedArtifact",
    "TaxonomyValue",
    "UserContext",
    "build_artifact",
    "canonical_snapshot",
    "load_artifact",
]

__version__ = "0.1.0"
