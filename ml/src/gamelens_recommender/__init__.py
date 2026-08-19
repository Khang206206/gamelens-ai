"""Deterministic artifact-backed recommendation primitives."""

from gamelens_recommender.artifacts import ArtifactError, LoadedArtifact, load_artifact
from gamelens_recommender.feedback import (
    FEEDBACK_POLICY_CONFIG,
    FeedbackPolicyConfig,
    FeedbackRanker,
)
from gamelens_recommender.ranking import ContentRanker, InsufficientContextError
from gamelens_recommender.schemas import (
    ActiveGameFeedback,
    BaseCandidateScore,
    CatalogItem,
    CatalogSnapshot,
    FeedbackPolicyIdentity,
    PersonalizedRankingResult,
    PersonalizedRecommendation,
    PositiveFeedbackSource,
    TaxonomyValue,
    UserContext,
    canonical_snapshot,
)
from gamelens_recommender.training import build_artifact

__all__ = [
    "ActiveGameFeedback",
    "ArtifactError",
    "BaseCandidateScore",
    "CatalogItem",
    "CatalogSnapshot",
    "ContentRanker",
    "FEEDBACK_POLICY_CONFIG",
    "FeedbackPolicyConfig",
    "FeedbackPolicyIdentity",
    "FeedbackRanker",
    "InsufficientContextError",
    "LoadedArtifact",
    "PersonalizedRankingResult",
    "PersonalizedRecommendation",
    "PositiveFeedbackSource",
    "TaxonomyValue",
    "UserContext",
    "build_artifact",
    "canonical_snapshot",
    "load_artifact",
]

__version__ = "0.1.0"
