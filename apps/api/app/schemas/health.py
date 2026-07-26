from typing import Literal

from app.schemas.common import ApiSchema


class HealthResponse(ApiSchema):
    status: Literal["ok", "degraded"]
    service: str
    environment: str
    database: Literal["ready", "unavailable"]
