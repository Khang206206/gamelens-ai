from gamelens_recommender import ActiveGameFeedback, CatalogSnapshot, UserContext
from gamelens_recommender.schemas import PersonalizedRankingResult, RankingResult

from app.core.exceptions import RecommendationUnavailableError
from app.schemas.model_status import ModelCapabilities, ModelStatusResponse


class NotConfiguredRecommendationService:
    @property
    def ready(self) -> bool:
        return False

    @property
    def needs_catalog(self) -> bool:
        return False

    def ensure_intrinsic_ready(self) -> None:
        raise RecommendationUnavailableError(
            "No recommendation model is configured",
            code="model_not_configured",
        )

    def status(
        self,
        snapshot: CatalogSnapshot | None = None,
        *,
        catalog_error: str | None = None,
    ) -> ModelStatusResponse:
        return ModelStatusResponse(
            status="not_configured",
            active_model=None,
            capabilities=ModelCapabilities(recommend=False, explanations=False),
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
