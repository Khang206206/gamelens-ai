import logging
from typing import Protocol, cast

from gamelens_recommender import (
    ActiveGameFeedback,
    CatalogSnapshot,
    CollaborativeComponentReady,
    CollaborativeComponentUnavailable,
    CollaborativeQueryContext,
    CollaborativeScorer,
    CollaborativeScoringResult,
    FeedbackRanker,
    HybridContractError,
    HybridRanker,
    HybridRankingResult,
    LoadedCollaborativeArtifact,
    UserContext,
)
from gamelens_recommender.hybrid import CollaborativeUnavailableReason

from app.services.recommendation.readiness import CollaborativeReadiness

logger = logging.getLogger(__name__)


class HybridContentComponent(Protocol):
    """Required content boundary used by lifecycle-aware hybrid ranking."""

    @property
    def feedback_ranker(self) -> FeedbackRanker: ...

    def ensure_catalog_snapshot(self, snapshot: CatalogSnapshot) -> None: ...


class CollaborativeScoringComponent(Protocol):
    """Optional collaborative boundary isolated from required content ranking."""

    def score(self, context: CollaborativeQueryContext) -> CollaborativeScoringResult: ...


class CollaborativeScorerFactory(Protocol):
    def __call__(
        self,
        artifact: LoadedCollaborativeArtifact,
    ) -> CollaborativeScoringComponent: ...


class LifecycleAwareHybridOrchestrator:
    """Coordinate readiness, query preparation, scoring, and hybrid policy."""

    def __init__(
        self,
        content: HybridContentComponent,
        *,
        scorer_factory: CollaborativeScorerFactory = CollaborativeScorer,
    ) -> None:
        self.content = content
        self.scorer_factory = scorer_factory
        self.hybrid_ranker = HybridRanker(content.feedback_ranker)

    def rank(
        self,
        *,
        snapshot: CatalogSnapshot,
        context: UserContext,
        feedback: tuple[ActiveGameFeedback, ...],
        collaborative_readiness: CollaborativeReadiness,
    ) -> HybridRankingResult:
        self.content.ensure_catalog_snapshot(snapshot)
        if not collaborative_readiness.usable:
            return self._fallback(
                context,
                feedback,
                cast(CollaborativeUnavailableReason, collaborative_readiness.reason),
            )

        prepared = self.content.feedback_ranker.prepare_ranking_context(context, feedback)
        artifact = collaborative_readiness.artifact
        if artifact is None:
            raise ValueError("Usable collaborative readiness must contain an artifact")

        try:
            scorer = self.scorer_factory(artifact)
            scoring_result = scorer.score(prepared.collaborative_query_context)
        except Exception as error:
            self._log_optional_failure(error)
            return self._fallback(context, feedback, "artifact_incompatible")

        try:
            return self.hybrid_ranker.rank(
                context,
                feedback,
                CollaborativeComponentReady(scoring_result),
            )
        except HybridContractError as error:
            self._log_optional_failure(error)
            return self._fallback(context, feedback, "artifact_incompatible")

    def _fallback(
        self,
        context: UserContext,
        feedback: tuple[ActiveGameFeedback, ...],
        reason: CollaborativeUnavailableReason,
    ) -> HybridRankingResult:
        return self.hybrid_ranker.rank(
            context,
            feedback,
            CollaborativeComponentUnavailable(reason=reason),
        )

    @staticmethod
    def _log_optional_failure(error: Exception) -> None:
        logger.warning(
            "Collaborative scoring is unavailable for this recommendation",
            extra={
                "fallback_reason": "artifact_incompatible",
                "error_type": type(error).__name__,
            },
        )
