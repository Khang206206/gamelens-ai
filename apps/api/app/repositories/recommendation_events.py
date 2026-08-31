import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import RecommendationEvent
from app.schemas.personalized_recommendations import (
    RecommendationEventContext,
    RecommendationEventResultItem,
)
from app.schemas.recommendation_events import (
    Stage5RecommendationEventContext,
    Stage5RecommendationEventIdentity,
    Stage5RecommendationEventResultItem,
)

MAX_EVENT_CONTEXT_BYTES = 8_192
MAX_EVENT_RESULT_BYTES = 32_768


def _validated_json(value: Any, *, maximum_bytes: int) -> Any:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    if len(encoded) > maximum_bytes:
        raise ValueError("Recommendation event payload exceeds its byte limit")
    return value


class RecommendationEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_stage_4(
        self,
        *,
        generation_id: str,
        user_id: int,
        model_name: str,
        model_version: str,
        data_fingerprint: str,
        policy_name: str,
        policy_version: str,
        context: RecommendationEventContext,
        result: list[RecommendationEventResultItem],
    ) -> RecommendationEvent:
        if len(result) > 20:
            raise ValueError("Recommendation event result exceeds top-K limit")
        event = RecommendationEvent(
            generation_id=generation_id,
            event_schema_version="stage-4-v1",
            user_id=user_id,
            model_name=model_name,
            model_version=model_version,
            data_fingerprint=data_fingerprint,
            ranking_policy_name=policy_name,
            ranking_policy_version=policy_version,
            request_context=_validated_json(
                context.model_dump(mode="json"),
                maximum_bytes=MAX_EVENT_CONTEXT_BYTES,
            ),
            result_summary=_validated_json(
                [item.model_dump(mode="json") for item in result],
                maximum_bytes=MAX_EVENT_RESULT_BYTES,
            ),
        )
        self.session.add(event)
        return event

    def add_stage_5(
        self,
        *,
        generation_id: str,
        user_id: int,
        identity: Stage5RecommendationEventIdentity,
        context: Stage5RecommendationEventContext,
        result: list[Stage5RecommendationEventResultItem],
    ) -> RecommendationEvent:
        if len(result) > 20:
            raise ValueError("Recommendation event result exceeds top-K limit")
        if identity.ranking_mode == "hybrid" and not result:
            raise ValueError("Hybrid recommendation event result must not be empty")
        if identity.ranking_mode != context.ranking_mode:
            raise ValueError("Recommendation event identity and context modes differ")
        if identity.fallback_reason != context.fallback_reason:
            raise ValueError("Recommendation event identity and fallback reasons differ")
        if len(result) > context.top_k:
            raise ValueError("Recommendation event result exceeds requested top-K")
        if [item.rank for item in result] != list(range(1, len(result) + 1)):
            raise ValueError("Recommendation event ranks must be contiguous and server ordered")
        slugs = [item.slug for item in result]
        if len(slugs) != len(set(slugs)):
            raise ValueError("Recommendation event results must be distinct")
        if identity.ranking_mode == "stage_4_fallback" and any(
            item.collaborative_supported
            or item.collaborative_weight_units != 0
            or item.collaborative_contribution_units != 0
            for item in result
        ):
            raise ValueError("Fallback event result must not claim collaborative application")

        collaborative_model = identity.collaborative_model
        hybrid_policy = identity.hybrid_policy
        event = RecommendationEvent(
            generation_id=generation_id,
            event_schema_version="stage-5-v1",
            user_id=user_id,
            model_name=identity.content_model_name,
            model_version=identity.content_model_version,
            data_fingerprint=identity.content_data_fingerprint,
            ranking_policy_name=identity.feedback_policy.name,
            ranking_policy_version=identity.feedback_policy.version,
            ranking_mode=identity.ranking_mode,
            fallback_reason=identity.fallback_reason,
            hybrid_policy_name=None if hybrid_policy is None else hybrid_policy.name,
            hybrid_policy_version=None if hybrid_policy is None else hybrid_policy.version,
            collaborative_model_name=(
                None if collaborative_model is None else collaborative_model.name
            ),
            collaborative_model_version=(
                None if collaborative_model is None else collaborative_model.version
            ),
            collaborative_interaction_fingerprint=(
                None if collaborative_model is None else collaborative_model.interaction_fingerprint
            ),
            collaborative_policy_name=(
                None if collaborative_model is None else collaborative_model.scoring_policy.name
            ),
            collaborative_policy_version=(
                None if collaborative_model is None else collaborative_model.scoring_policy.version
            ),
            request_context=_validated_json(
                context.model_dump(mode="json"),
                maximum_bytes=MAX_EVENT_CONTEXT_BYTES,
            ),
            result_summary=_validated_json(
                [item.model_dump(mode="json") for item in result],
                maximum_bytes=MAX_EVENT_RESULT_BYTES,
            ),
        )
        self.session.add(event)
        return event
