from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC

from gamelens_recommender import ActiveGameFeedback, InsufficientContextError, UserContext
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
    PersonalizationPolicyIdentity,
    PersonalizedRecommendationItem,
    PersonalizedRecommendationResponse,
    PositiveFeedbackSourceResponse,
    RecommendationEventContext,
    RecommendationEventResultItem,
)
from app.schemas.recommendations import (
    EvidenceValue,
    RecommendationEvidenceResponse,
    RecommendationExplanationResponse,
    ScoreComponentResponse,
    SimilarSelectedGameResponse,
)
from app.services.anonymous_identity import AnonymousIdentityService
from app.services.recommendation.base import RecommendationService

SCORE_SCALE = 1_000_000


def _score(units: int) -> float:
    return units / SCORE_SCALE


class PersonalizedRecommendationService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        recommendation_service: RecommendationService,
    ) -> None:
        self.session = session
        self.settings = settings
        self.recommendation_service = recommendation_service

    def recommend(
        self,
        credential: SessionCredential | None,
        *,
        top_k: int,
    ) -> PersonalizedRecommendationResponse:
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
        try:
            result = self.recommendation_service.recommend_personalized(
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
        source_state = [
            {"slug": source.game_slug, "kind": source.kind} for source in result.positive_sources
        ]
        effective_state = {
            "disliked": disliked_slugs,
            "played": played_slugs,
            "positive_sources": source_state,
        }
        state_body = json.dumps(effective_state, sort_keys=True, separators=(",", ":"))
        state_fingerprint = hashlib.sha256(state_body.encode("utf-8")).hexdigest()
        response_items: list[PersonalizedRecommendationItem] = []
        event_items: list[RecommendationEventResultItem] = []
        for item in result.items:
            evidence = item.base_evidence
            response_items.append(
                PersonalizedRecommendationItem(
                    rank=item.rank,
                    game=catalog.games_by_slug[item.slug],
                    base_ranking_score=_score(item.base_score_units),
                    base_components=[
                        ScoreComponentResponse(
                            name=component.name,
                            raw_score=_score(component.raw_units),
                            weight=_score(component.weight_units),
                            contribution=_score(component.contribution_units),
                        )
                        for component in item.base_components
                    ],
                    base_weight=_score(item.base_weight_units),
                    base_contribution=_score(item.base_contribution_units),
                    feedback_affinity_score=_score(item.affinity_score_units),
                    feedback_affinity_weight=_score(item.affinity_weight_units),
                    feedback_affinity_contribution=_score(item.affinity_contribution_units),
                    pre_played_score=_score(item.pre_played_score_units),
                    played_factor=_score(item.played_factor_units),
                    played_delta=_score(item.played_delta_units),
                    ranking_score=_score(item.final_score_units),
                    adjustment_reasons=list(item.adjustment_reasons),
                    evidence=RecommendationEvidenceResponse(
                        matching_genres=[
                            EvidenceValue(slug=v.slug, name=v.name)
                            for v in evidence.matching_genres
                        ],
                        matching_tags=[
                            EvidenceValue(slug=v.slug, name=v.name) for v in evidence.matching_tags
                        ],
                        preferred_platforms=[
                            EvidenceValue(slug=v.slug, name=v.name)
                            for v in evidence.preferred_platforms
                        ],
                        similar_selected_games=[
                            SimilarSelectedGameResponse(
                                slug=v.slug,
                                title=v.title,
                                similarity_score=_score(v.similarity_units),
                            )
                            for v in evidence.similar_selected_games
                        ],
                        popularity_score=_score(evidence.popularity_percentile_units),
                    ),
                    explanation=RecommendationExplanationResponse(
                        summary=item.explanation_summary,
                        reasons=list(item.explanation_reasons),
                    ),
                )
            )
            event_items.append(
                RecommendationEventResultItem(
                    slug=item.slug,
                    rank=item.rank,
                    base_units=item.base_score_units,
                    final_units=item.final_score_units,
                    affinity_units=item.affinity_contribution_units,
                    played_delta_units=item.played_delta_units,
                )
            )
        response = PersonalizedRecommendationResponse(
            generation_id=generation_id,
            model_name=active.name,
            model_version=active.version,
            data_fingerprint=active.data_fingerprint,
            policy=PersonalizationPolicyIdentity(
                name=result.policy.name,
                version=result.policy.version,
            ),
            response_reason=result.reason,
            requested_top_k=top_k,
            positive_feedback_sources=[
                PositiveFeedbackSourceResponse(game_slug=source.game_slug, kind=source.kind)
                for source in result.positive_sources
            ],
            items=response_items,
        )
        RecommendationEventRepository(self.session).add_stage_4(
            generation_id=generation_id,
            user_id=user.id,
            model_name=active.name,
            model_version=active.version,
            data_fingerprint=active.data_fingerprint,
            policy_name=result.policy.name,
            policy_version=result.policy.version,
            context=RecommendationEventContext(
                top_k=top_k,
                selected_game_slugs=[
                    slug for slug in context.selected_game_slugs if slug not in disliked_slugs
                ],
                preferred_genres=list(context.preferred_genres),
                preferred_tags=list(context.preferred_tags),
                preferred_platforms=list(context.preferred_platforms),
                positive_source_slugs=[s.game_slug for s in result.positive_sources],
                disliked_count=len(disliked_slugs),
                played_count=len(played_slugs),
                positive_source_count=len(result.positive_sources),
                effective_state_fingerprint=state_fingerprint,
            ),
            result=event_items,
        )
        self.session.flush()
        try:
            self.session.commit()
        except DBAPIError as error:
            raise RecommendationGenerationOutcomeUnknownError(
                "The generation commit outcome could not be confirmed",
                details={"generation_id": generation_id},
            ) from error
        return response
