from gamelens_recommender import ActiveGameFeedback, CatalogSnapshot, UserContext
from gamelens_recommender.schemas import PersonalizedRankingResult, RankingResult

from app.core.exceptions import RecommendationUnavailableError
from app.schemas.model_status import ModelCapabilities, ModelStatusResponse


class UnavailableRecommendationService:
    def __init__(self, reason: str) -> None:
        self.reason = reason

    @property
    def ready(self) -> bool:
        return False

    @property
    def needs_catalog(self) -> bool:
        return False

    def ensure_intrinsic_ready(self) -> None:
        raise RecommendationUnavailableError(
            "The recommendation model is unavailable",
            code=self.reason,
        )

    def status(
        self,
        snapshot: CatalogSnapshot | None = None,
        *,
        catalog_error: str | None = None,
    ) -> ModelStatusResponse:
        return ModelStatusResponse(
            status="unavailable",
            active_model=None,
            capabilities=ModelCapabilities(recommend=False, explanations=False),
            unavailable_reason=self.reason,
        )

    def recommend(self, *, snapshot: CatalogSnapshot, context: UserContext) -> RankingResult:
        self.ensure_intrinsic_ready()
        raise AssertionError("unreachable")

    def recommend_personalized(
        self,
        *,
        snapshot: CatalogSnapshot,
        context: UserContext,
        feedback: tuple[ActiveGameFeedback, ...],
    ) -> PersonalizedRankingResult:
        self.ensure_intrinsic_ready()
        raise AssertionError("unreachable")
