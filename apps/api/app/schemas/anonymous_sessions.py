from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from app.schemas.common import ApiSchema


class AnonymousSessionConsentRequest(ApiSchema):
    model_config = ConfigDict(extra="forbid")

    consent: Literal[True]
    consent_version: str = Field(min_length=1, max_length=100)


class AnonymousSessionResponse(ApiSchema):
    status: Literal["active", "consent_outdated"]
    consent_version: str
    current_consent_version: str
    consented_at: datetime
    expires_at: datetime
    csrf_token: str = Field(pattern=r"^[0-9a-f]{64}$")
