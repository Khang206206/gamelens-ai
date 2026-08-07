from gamelens_recommender import InsufficientContextError, UserContext

from app.core.exceptions import RecommendationUnavailableError, RecommendationValidationError
from app.repositories.recommendation_catalog import RecommendationCatalogSnapshot
from app.schemas.recommendations import (
    EvidenceValue,
    RecommendationEvidenceResponse,
    RecommendationExplanationResponse,
    RecommendationItemResponse,
    RecommendationModelIdentity,
    RecommendationRequest,
    RecommendationResponse,
    ScoreComponentResponse,
    SimilarSelectedGameResponse,
)
from app.services.recommendation.base import RecommendationService

SCORE_SCALE = 1_000_000


def _score(units: int) -> float:
    return units / SCORE_SCALE


class RecommendationApplicationService:
    def __init__(
        self,
        catalog: RecommendationCatalogSnapshot,
        recommendation_service: RecommendationService,
    ) -> None:
        self.catalog = catalog
        self.recommendation_service = recommendation_service

    def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        model_snapshot = self.catalog.model_snapshot
        if model_snapshot is None:
            code = self.catalog.model_unavailable_reason or "catalog_stale"
            raise RecommendationUnavailableError(
                (
                    "The recommendation catalog is invalid"
                    if code == "catalog_invalid"
                    else "The recommendation artifact no longer matches the catalog"
                ),
                code=code,
            )
        unknown_ids = [
            value for value in request.selected_game_ids if value not in self.catalog.games_by_id
        ]
        if unknown_ids:
            raise RecommendationValidationError(
                "One or more selected games do not exist",
                code="unknown_game",
                details={"selected_game_ids": unknown_ids},
            )
        self._validate_taxonomy("genre", request.preferred_genres, self.catalog.genre_slugs)
        self._validate_taxonomy("tag", request.preferred_tags, self.catalog.tag_slugs)
        self._validate_taxonomy(
            "platform", request.preferred_platforms, self.catalog.platform_slugs
        )
        context = UserContext(
            selected_game_slugs=tuple(
                self.catalog.games_by_id[value].slug for value in request.selected_game_ids
            ),
            preferred_genres=tuple(request.preferred_genres),
            preferred_tags=tuple(request.preferred_tags),
            preferred_platforms=tuple(request.preferred_platforms),
            top_k=request.top_k,
        )
        try:
            result = self.recommendation_service.recommend(
                snapshot=model_snapshot,
                context=context,
            )
        except InsufficientContextError as error:
            raise RecommendationValidationError(str(error), code="insufficient_context") from error
        status = self.recommendation_service.status(model_snapshot)
        active = status.active_model
        if active is None or active.data_fingerprint is None:
            raise RuntimeError("Ready recommendation service did not expose model identity")
        items: list[RecommendationItemResponse] = []
        for recommendation in result.items:
            items.append(
                RecommendationItemResponse(
                    rank=recommendation.rank,
                    ranking_score=_score(recommendation.final_score_units),
                    game=self.catalog.games_by_slug[recommendation.slug],
                    components=[
                        ScoreComponentResponse(
                            name=component.name,
                            raw_score=_score(component.raw_units),
                            weight=_score(component.weight_units),
                            contribution=_score(component.contribution_units),
                        )
                        for component in recommendation.components
                    ],
                    evidence=RecommendationEvidenceResponse(
                        matching_genres=[
                            EvidenceValue(slug=value.slug, name=value.name)
                            for value in recommendation.evidence.matching_genres
                        ],
                        matching_tags=[
                            EvidenceValue(slug=value.slug, name=value.name)
                            for value in recommendation.evidence.matching_tags
                        ],
                        preferred_platforms=[
                            EvidenceValue(slug=value.slug, name=value.name)
                            for value in recommendation.evidence.preferred_platforms
                        ],
                        similar_selected_games=[
                            SimilarSelectedGameResponse(
                                slug=value.slug,
                                title=value.title,
                                similarity_score=_score(value.similarity_units),
                            )
                            for value in recommendation.evidence.similar_selected_games
                        ],
                        popularity_score=_score(
                            recommendation.evidence.popularity_percentile_units
                        ),
                    ),
                    explanation=RecommendationExplanationResponse(
                        summary=recommendation.explanation_summary,
                        reasons=list(recommendation.explanation_reasons),
                    ),
                )
            )
        return RecommendationResponse(
            model=RecommendationModelIdentity(
                name=active.name,
                version=active.version,
                data_fingerprint=active.data_fingerprint,
            ),
            response_reason=result.reason,
            requested_top_k=request.top_k,
            items=items,
        )

    @staticmethod
    def _validate_taxonomy(family: str, requested: list[str], known: frozenset[str]) -> None:
        unknown = [value for value in requested if value not in known]
        if unknown:
            raise RecommendationValidationError(
                f"One or more selected {family} values do not exist",
                code=f"unknown_{family}",
                details={f"preferred_{family}s": unknown},
            )
