from typing import Literal

from app.schemas.common import ApiSchema


class ModelCapabilities(ApiSchema):
    recommend: bool
    explanations: bool


class ActiveModel(ApiSchema):
    name: str
    version: str


class ModelStatusResponse(ApiSchema):
    status: Literal["ready", "not_configured"]
    active_model: ActiveModel | None
    capabilities: ModelCapabilities
