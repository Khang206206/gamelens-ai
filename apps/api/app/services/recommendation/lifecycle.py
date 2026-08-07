from pathlib import Path

from gamelens_recommender import ArtifactError, load_artifact

from app.services.recommendation.base import RecommendationService
from app.services.recommendation.content import ContentRecommendationService
from app.services.recommendation.not_configured import NotConfiguredRecommendationService
from app.services.recommendation.unavailable import UnavailableRecommendationService


def create_recommendation_service(path: Path | None) -> RecommendationService:
    if path is None:
        return NotConfiguredRecommendationService()
    try:
        return ContentRecommendationService(load_artifact(path))
    except ArtifactError as error:
        return UnavailableRecommendationService(error.code)
    except (OSError, ValueError):
        return UnavailableRecommendationService("model_construction_failed")
