from dataclasses import dataclass

from gamelens_recommender import (
    ActiveGameFeedback,
    CatalogSnapshot,
    HybridRankingResult,
    PersonalizedRankingResult,
    Stage4FallbackResult,
    UserContext,
    validate_hybrid_ranking_result,
)
from sqlalchemy.orm import Session

from app.services.recommendation.base import RecommendationService
from app.services.recommendation.collaborative import CollaborativeArtifactComponent
from app.services.recommendation.hybrid import HybridRankingOrchestrator
from app.services.recommendation.readiness import CollaborativeReadiness
from app.services.recommendation.readiness_resolution import CollaborativeReadinessResolver


@dataclass(frozen=True, slots=True)
class PersonalizedRankingDecision:
    """Internal Phase 5 handoff kept separate from public response/event mapping."""

    result: HybridRankingResult
    collaborative_readiness: CollaborativeReadiness
    legacy_stage_4_result: PersonalizedRankingResult

    def __post_init__(self) -> None:
        validate_hybrid_ranking_result(self.result)
        if type(self.legacy_stage_4_result) is not PersonalizedRankingResult:
            raise ValueError("Legacy Stage 4 ranking payload is invalid")
        if (
            type(self.result) is Stage4FallbackResult
            and self.result.stage_4_result is not self.legacy_stage_4_result
        ):
            raise ValueError("Fallback decision must preserve its exact Stage 4 payload")


class PersonalizedRankingDecisionService:
    """Resolve lifecycle state and produce one internal ranking decision."""

    def __init__(
        self,
        session: Session,
        recommendation_service: RecommendationService,
        collaborative_component: CollaborativeArtifactComponent,
        hybrid_orchestrator: HybridRankingOrchestrator,
        *,
        current_consent_version: str | None,
    ) -> None:
        self.session = session
        self.recommendation_service = recommendation_service
        self.collaborative_component = collaborative_component
        self.hybrid_orchestrator = hybrid_orchestrator
        self.current_consent_version = current_consent_version

    def decide(
        self,
        *,
        snapshot: CatalogSnapshot,
        context: UserContext,
        feedback: tuple[ActiveGameFeedback, ...],
    ) -> PersonalizedRankingDecision:
        readiness = CollaborativeReadinessResolver(
            self.session,
            self.collaborative_component,
            current_consent_version=self.current_consent_version,
        ).resolve(catalog_fingerprint=snapshot.fingerprint)
        result = self.hybrid_orchestrator.rank(
            snapshot=snapshot,
            context=context,
            feedback=feedback,
            collaborative_readiness=readiness,
        )
        validate_hybrid_ranking_result(result)
        legacy_result = (
            result.stage_4_result
            if type(result) is Stage4FallbackResult
            else self.recommendation_service.recommend_personalized(
                snapshot=snapshot,
                context=context,
                feedback=feedback,
            )
        )
        return PersonalizedRankingDecision(
            result=result,
            collaborative_readiness=readiness,
            legacy_stage_4_result=legacy_result,
        )
