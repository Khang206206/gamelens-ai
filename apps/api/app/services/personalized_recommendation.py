from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC

from gamelens_recommender import (
    ActiveGameFeedback,
    InsufficientContextError,
    Stage4FallbackResult,
    UserContext,
)
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import (
    RecommendationGenerationOutcomeUnknownError,
    RecommendationValidationError,
    SavedPreferencesStaleError,
)
from app.core.security import SessionCredential, utc_now
from app.db.models import InteractionType, PreferenceType
from app.db.session import begin_repeatable_read
from app.repositories.interactions import InteractionRepository
from app.repositories.preferences import PreferenceRepository
from app.repositories.recommendation_catalog import RecommendationCatalogRepository
from app.repositories.recommendation_events import RecommendationEventRepository
from app.schemas.personalized_recommendations import (
    RecommendationEventContext,
    Stage5PersonalizedRecommendationResponse,
)
from app.schemas.recommendations import RecommendationModelIdentity
from app.services.anonymous_identity import AnonymousIdentityService
from app.services.recommendation.base import RecommendationService
from app.services.recommendation.collaborative import CollaborativeArtifactComponent
from app.services.recommendation.decision import PersonalizedRankingDecisionService
from app.services.recommendation.hybrid import HybridRankingOrchestrator
from app.services.recommendation.projection import project_stage_5_decision


class PersonalizedRecommendationService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        recommendation_service: RecommendationService,
        collaborative_component: CollaborativeArtifactComponent,
        hybrid_orchestrator: HybridRankingOrchestrator | None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.recommendation_service = recommendation_service
        self.collaborative_component = collaborative_component
        self.hybrid_orchestrator = hybrid_orchestrator

    def recommend(
        self,
        credential: SessionCredential | None,
        *,
        top_k: int,
    ) -> Stage5PersonalizedRecommendationResponse:
        self.recommendation_service.ensure_intrinsic_ready()
        begin_repeatable_read(self.session, read_only=False)
        user = AnonymousIdentityService(self.session, self.settings).resolve_active_for_update(
            credential
        )
        user.updated_at = utc_now()
        catalog = RecommendationCatalogRepository(self.session).load()
        if catalog.model_snapshot is None:
            from app.core.exceptions import RecommendationUnavailableError

            raise RecommendationUnavailableError(
                "The recommendation catalog is unavailable",
                code=catalog.model_unavailable_reason or "catalog_stale",
            )
        preference_rows = PreferenceRepository(self.session).list_for_user(user.id)
        values: dict[str, list[str]] = {kind.value: [] for kind in PreferenceType}
        for row in preference_rows:
            kind = (
                row.preference_type.value
                if isinstance(row.preference_type, PreferenceType)
                else str(row.preference_type)
            )
            values[kind].append(row.value)
        game_ids_by_slug = {game.slug: game.id for game in catalog.games_by_id.values()}
        stale = [slug for slug in values[PreferenceType.GAME.value] if slug not in game_ids_by_slug]
        stale += [
            slug for slug in values[PreferenceType.GENRE.value] if slug not in catalog.genre_slugs
        ]
        stale += [
            slug for slug in values[PreferenceType.TAG.value] if slug not in catalog.tag_slugs
        ]
        stale += [
            slug
            for slug in values[PreferenceType.PLATFORM.value]
            if slug not in catalog.platform_slugs
        ]
        if stale:
            raise SavedPreferencesStaleError(
                "Saved preferences no longer match the catalog",
                details={"references": sorted(stale)[:26]},
            )
        if not (
            values[PreferenceType.GAME.value]
            or values[PreferenceType.GENRE.value]
            or values[PreferenceType.TAG.value]
        ):
            raise RecommendationValidationError(
                "Saved preferences do not contain a content signal",
                code="saved_preferences_required",
            )
        feedback_groups = InteractionRepository(self.session).aggregated_current(user.id)
        feedback: list[ActiveGameFeedback] = []
        canonical_state: list[dict[str, object]] = []
        for game, rows in feedback_groups:
            by_type = {row.interaction_type: row for row in rows}
            reaction_row = next(
                (
                    row
                    for row in rows
                    if row.interaction_type in {InteractionType.LIKED, InteractionType.DISLIKED}
                ),
                None,
            )
            rating_row = by_type.get(InteractionType.RATED)
            feedback.append(
                ActiveGameFeedback(
                    game_slug=game.slug,
                    reaction=(reaction_row.interaction_type.value if reaction_row else None),
                    reaction_occurred_at=(
                        reaction_row.occurred_at.replace(tzinfo=UTC)
                        if reaction_row and reaction_row.occurred_at.tzinfo is None
                        else reaction_row.occurred_at
                        if reaction_row
                        else None
                    ),
                    played=InteractionType.PLAYED in by_type,
                    wishlisted=InteractionType.WISHLISTED in by_type,
                    rating=rating_row.value if rating_row else None,
                    rating_occurred_at=(
                        rating_row.occurred_at.replace(tzinfo=UTC)
                        if rating_row and rating_row.occurred_at.tzinfo is None
                        else rating_row.occurred_at
                        if rating_row
                        else None
                    ),
                )
            )
            canonical_state.append(
                {
                    "slug": game.slug,
                    "reaction": reaction_row.interaction_type.value if reaction_row else None,
                    "played": InteractionType.PLAYED in by_type,
                    "wishlisted": InteractionType.WISHLISTED in by_type,
                    "rating": str(rating_row.value) if rating_row else None,
                }
            )
        context = UserContext(
            selected_game_slugs=tuple(sorted(values[PreferenceType.GAME.value])),
            preferred_genres=tuple(sorted(values[PreferenceType.GENRE.value])),
            preferred_tags=tuple(sorted(values[PreferenceType.TAG.value])),
            preferred_platforms=tuple(sorted(values[PreferenceType.PLATFORM.value])),
            top_k=top_k,
        )
        self.session.flush()
        if self.hybrid_orchestrator is None:
            raise RuntimeError("Ready content service did not expose hybrid orchestration")
        try:
            decision = PersonalizedRankingDecisionService(
                self.session,
                self.recommendation_service,
                self.collaborative_component,
                self.hybrid_orchestrator,
                current_consent_version=(self.settings.collaborative_contribution_consent_version),
            ).decide(
                snapshot=catalog.model_snapshot,
                context=context,
                feedback=tuple(feedback),
            )
        except InsufficientContextError as error:
            raise RecommendationValidationError(
                str(error),
                code="effective_context_required",
            ) from error
        status = self.recommendation_service.status(catalog.model_snapshot)
        active = status.active_model
        if active is None or active.data_fingerprint is None:
            raise RuntimeError("Ready recommendation service did not expose model identity")
        generation_id = uuid.uuid4().hex
        disliked_slugs = sorted(
            value["slug"] for value in canonical_state if value["reaction"] == "disliked"
        )
        played_slugs = sorted(value["slug"] for value in canonical_state if value["played"])
        decision_positive_sources = (
            decision.result.stage_4_result.positive_sources
            if type(decision.result) is Stage4FallbackResult
            else decision.result.positive_sources
        )
        source_state = [
            {"slug": source.game_slug, "kind": source.kind} for source in decision_positive_sources
        ]
        effective_state = {
            "disliked": disliked_slugs,
            "played": played_slugs,
            "positive_sources": source_state,
        }
        state_body = json.dumps(effective_state, sort_keys=True, separators=(",", ":"))
        state_fingerprint = hashlib.sha256(state_body.encode("utf-8")).hexdigest()
        projection = project_stage_5_decision(
            decision,
            generation_id=generation_id,
            content_model=RecommendationModelIdentity(
                name=active.name,
                version=active.version,
                data_fingerprint=active.data_fingerprint,
            ),
            games_by_slug=catalog.games_by_slug,
            event_context=RecommendationEventContext(
                top_k=top_k,
                selected_game_slugs=[
                    slug for slug in context.selected_game_slugs if slug not in disliked_slugs
                ],
                preferred_genres=list(context.preferred_genres),
                preferred_tags=list(context.preferred_tags),
                preferred_platforms=list(context.preferred_platforms),
                positive_source_slugs=[source.game_slug for source in decision_positive_sources],
                disliked_count=len(disliked_slugs),
                played_count=len(played_slugs),
                positive_source_count=len(decision_positive_sources),
                effective_state_fingerprint=state_fingerprint,
            ),
        )
        RecommendationEventRepository(self.session).add_stage_5(
            generation_id=generation_id,
            user_id=user.id,
            identity=projection.event_identity,
            context=projection.event_context,
            result=list(projection.event_result),
        )
        self.session.flush()
        try:
            self.session.commit()
        except DBAPIError as error:
            raise RecommendationGenerationOutcomeUnknownError(
                "The generation commit outcome could not be confirmed",
                details={"generation_id": generation_id},
            ) from error
        return projection.response
