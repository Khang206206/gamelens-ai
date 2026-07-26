from app.schemas.model_status import ModelCapabilities, ModelStatusResponse


class NotConfiguredRecommendationService:
    @property
    def ready(self) -> bool:
        return False

    def status(self) -> ModelStatusResponse:
        return ModelStatusResponse(
            status="not_configured",
            active_model=None,
            capabilities=ModelCapabilities(recommend=False, explanations=False),
        )

    def recommend(self, *, context: dict[str, object], top_k: int) -> list[object]:
        raise RuntimeError("No recommendation model is configured")
