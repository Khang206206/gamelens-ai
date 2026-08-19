from gamelens_recommender import (
    ActiveGameFeedback,
    CatalogSnapshot,
    ContentRanker,
    FeedbackRanker,
    LoadedArtifact,
    UserContext,
)
from gamelens_recommender.schemas import PersonalizedRankingResult, RankingResult

from app.core.exceptions import RecommendationUnavailableError
from app.schemas.model_status import ActiveModel, ModelCapabilities, ModelStatusResponse


class ContentRecommendationService:
    def __init__(self, artifact: LoadedArtifact) -> None:
        self.artifact = artifact
        self.ranker = ContentRanker(artifact)
        self.feedback_ranker = FeedbackRanker(
            artifact,
            content_ranker=self.ranker,
        )

    @property
    def ready(self) -> bool:
        return True

    @property
    def needs_catalog(self) -> bool:
        return True

    def ensure_intrinsic_ready(self) -> None:
        """The artifact was fully validated when this service was constructed."""

    def status(
        self,
        snapshot: CatalogSnapshot | None = None,
        *,
        catalog_error: str | None = None,
    ) -> ModelStatusResponse:
        if catalog_error is not None or (
            snapshot is None or snapshot.fingerprint != self.artifact.data_fingerprint
        ):
            return ModelStatusResponse(
                status="unavailable",
                active_model=self._identity(),
                capabilities=ModelCapabilities(recommend=False, explanations=False),
                unavailable_reason=catalog_error or "catalog_stale",
            )
        return ModelStatusResponse(
            status="ready",
            active_model=self._identity(),
            capabilities=ModelCapabilities(recommend=True, explanations=True),
            feature_families=["title", "genre", "tag", "developer", "publisher", "description"],
        )

    def recommend(self, *, snapshot: CatalogSnapshot, context: UserContext) -> RankingResult:
        if snapshot.fingerprint != self.artifact.data_fingerprint:
            raise RecommendationUnavailableError(
                "The recommendation artifact no longer matches the catalog",
                code="catalog_stale",
            )
        return self.ranker.rank(context)

    def recommend_personalized(
        self,
        *,
        snapshot: CatalogSnapshot,
        context: UserContext,
        feedback: tuple[ActiveGameFeedback, ...],
    ) -> PersonalizedRankingResult:
        if snapshot.fingerprint != self.artifact.data_fingerprint:
            raise RecommendationUnavailableError(
                "The recommendation artifact no longer matches the catalog",
                code="catalog_stale",
            )
        return self.feedback_ranker.rank(context, feedback)

    def _identity(self) -> ActiveModel:
        return ActiveModel(
            name=self.artifact.model_name,
            version=self.artifact.model_version,
            artifact_schema=str(self.artifact.manifest["artifact_schema_version"]),
            data_fingerprint=self.artifact.data_fingerprint,
        )
