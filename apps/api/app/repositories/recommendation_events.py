import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import RecommendationEvent
from app.schemas.personalized_recommendations import (
    RecommendationEventContext,
    RecommendationEventResultItem,
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
