from typing import Any

from pydantic import BaseModel, ConfigDict


class ApiSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(ApiSchema):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(ApiSchema):
    error: ErrorDetail
