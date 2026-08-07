from typing import Protocol

from gamelens_recommender import CatalogSnapshot, UserContext
from gamelens_recommender.schemas import RankingResult

from app.schemas.model_status import ModelStatusResponse


class RecommendationService(Protocol):
    @property
    def ready(self) -> bool: ...

    @property
    def needs_catalog(self) -> bool: ...

    def ensure_intrinsic_ready(self) -> None: ...

    def status(
        self,
        snapshot: CatalogSnapshot | None = None,
        *,
        catalog_error: str | None = None,
    ) -> ModelStatusResponse: ...

    def recommend(self, *, snapshot: CatalogSnapshot, context: UserContext) -> RankingResult: ...
