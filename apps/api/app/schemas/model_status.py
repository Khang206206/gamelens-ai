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


class ModelStatusResponse(ApiSchema):
    status: Literal["ready", "not_configured", "unavailable"]
    active_model: ActiveModel | None
    capabilities: ModelCapabilities
    unavailable_reason: str | None = None
    feature_families: list[str] | None = None
