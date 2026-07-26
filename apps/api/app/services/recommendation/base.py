from typing import Protocol

from app.schemas.model_status import ModelStatusResponse


class RecommendationService(Protocol):
    @property
    def ready(self) -> bool: ...

    def status(self) -> ModelStatusResponse: ...

    def recommend(self, *, context: dict[str, object], top_k: int) -> list[object]: ...
