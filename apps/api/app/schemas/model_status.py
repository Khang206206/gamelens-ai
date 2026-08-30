from typing import Literal

from app.schemas.common import ApiSchema


class ModelCapabilities(ApiSchema):
    recommend: bool
    explanations: bool


class ActiveModel(ApiSchema):
    name: str
    version: str
    artifact_schema: str | None = None
    data_fingerprint: str | None = None


class ContentComponentStatus(ApiSchema):
    status: Literal["ready", "not_configured", "unavailable"]
    reason: str | None


class CollaborativeComponentStatus(ApiSchema):
    status: Literal[
        "not_configured",
        "fixture_only",
        "insufficient_data",
        "unavailable",
        "stale",
        "ready",
    ]
    reason: (
        Literal[
            "not_configured",
            "fixture_not_allowed",
            "insufficient_data",
            "artifact_missing",
            "artifact_corrupt",
            "artifact_incompatible",
            "artifact_stale",
            "privacy_invalid",
            "artifact_expired",
            "catalog_stale",
            "artifact_retired",
        ]
        | None
    )
    source_kind: Literal["fixture", "live"] | None


class ModelComponentsStatus(ApiSchema):
    content: ContentComponentStatus
    collaborative: CollaborativeComponentStatus


class ModelStatusResponse(ApiSchema):
    status: Literal["ready", "not_configured", "unavailable"]
    active_model: ActiveModel | None
    capabilities: ModelCapabilities
    unavailable_reason: str | None = None
    feature_families: list[str] | None = None
    components: ModelComponentsStatus | None = None
