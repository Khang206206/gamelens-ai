import re
from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import SplitResult, urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEVELOPMENT_SESSION_SECRET = "development-only-stage-4-session-secret-change-me"


def _normalized_http_origin(origin: str) -> str:
    if origin != origin.strip() or any(character.isspace() for character in origin):
        raise ValueError("CORS origins must not contain whitespace")

    parsed: SplitResult = urlsplit(origin)
    scheme = parsed.scheme.casefold()
    if scheme not in {"http", "https"}:
        raise ValueError("CORS origins must use http:// or https://")
    if (
        parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or "\\" in parsed.netloc
    ):
        raise ValueError("CORS origins must contain only a scheme, host, and optional port")

    try:
        port = parsed.port
        normalized_host = parsed.hostname.encode("idna").decode("ascii").casefold()
    except (UnicodeError, ValueError) as error:
        raise ValueError("CORS origin host or port is invalid") from error
    try:
        ip_address(normalized_host)
    except ValueError:
        hostname_pattern = re.compile(
            r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)"
            r"(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*"
        )
        if hostname_pattern.fullmatch(normalized_host) is None:
            raise ValueError("CORS origin hostname is invalid") from None
    if port == 0:
        raise ValueError("CORS origin port must be between 1 and 65535")

    if ":" in normalized_host:
        normalized_host = f"[{normalized_host}]"
    if port in {None, 80 if scheme == "http" else 443}:
        authority = normalized_host
    else:
        authority = f"{normalized_host}:{port}"
    return f"{scheme}://{authority}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        hide_input_in_errors=True,
    )

    app_name: str = Field(default="GameLens AI API", min_length=1, max_length=100)
    environment: Literal["development", "test", "production"] = "development"
    api_host: str = Field(default="127.0.0.1", min_length=1, max_length=253)
    api_port: int = Field(default=8000, ge=1, le=65535)
    database_url: str = "postgresql+psycopg://gamelens:gamelens_dev_only@localhost:5432/gamelens"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    model_artifact_path: Path | None = None
    collaborative_artifact_path: Path | None = None
    anonymous_session_secret: SecretStr = Field(
        default=SecretStr(DEVELOPMENT_SESSION_SECRET),
        min_length=32,
        max_length=512,
    )
    anonymous_session_cookie_name: str = Field(
        default="gamelens_session",
        pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$",
    )
    anonymous_session_cookie_path: str = Field(default="/api/v1", min_length=1, max_length=200)
    anonymous_session_cookie_secure: bool = False
    anonymous_session_cookie_samesite: Literal["lax", "strict"] = "lax"
    anonymous_session_ttl_seconds: int = Field(default=15_552_000, ge=3600, le=31_536_000)
    consent_version: str = Field(default="stage-4-v1", min_length=1, max_length=100)
    collaborative_live_data_enabled: bool = False
    collaborative_contribution_consent_version: (
        Annotated[str, Field(min_length=1, max_length=100)] | None
    ) = None
    collaborative_live_promotion_enabled: bool = False
    collaborative_allow_test_fixture: bool = False
    collaborative_fixture_path: Path = (
        PROJECT_ROOT / "data" / "fixtures" / "interactions" / "collaborative-interactions.json"
    )
    csrf_header_name: str = Field(
        default="X-CSRF-Token",
        pattern=r"^[A-Za-z][A-Za-z0-9-]{0,63}$",
    )
    recommendation_event_retention_days: int = Field(default=90, ge=1, le=3650)
    retention_batch_size: int = Field(default=500, ge=1, le=10_000)

    @field_validator("model_artifact_path", "collaborative_artifact_path", mode="before")
    @classmethod
    def empty_artifact_path_is_unconfigured(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("collaborative_contribution_consent_version", mode="before")
    @classmethod
    def empty_contribution_consent_version_is_unconfigured(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        if not origins:
            raise ValueError("CORS_ORIGINS must contain at least one origin")
        if "*" in origins:
            raise ValueError("CORS_ORIGINS must use explicit origins")

        normalized_origins: list[str] = []
        seen: set[str] = set()
        for origin in origins:
            normalized = _normalized_http_origin(origin)
            if normalized not in seen:
                normalized_origins.append(normalized)
                seen.add(normalized)
        return normalized_origins

    @field_validator("app_name", "api_host")
    @classmethod
    def strip_non_empty_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped

    @field_validator(
        "anonymous_session_cookie_path",
        "consent_version",
        "csrf_header_name",
    )
    @classmethod
    def strip_security_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("security settings must not be blank")
        return stripped

    @field_validator("anonymous_session_secret", mode="before")
    @classmethod
    def strip_session_secret(cls, value: object) -> object:
        raw_value = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not isinstance(raw_value, str):
            return raw_value
        stripped = raw_value.strip()
        if not stripped:
            raise ValueError("security settings must not be blank")
        return stripped

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        return value

    @model_validator(mode="after")
    def validate_session_security(self) -> "Settings":
        if not self.anonymous_session_cookie_path.startswith("/"):
            raise ValueError("ANONYMOUS_SESSION_COOKIE_PATH must start with /")
        if self.environment == "production":
            if not self.anonymous_session_cookie_secure:
                raise ValueError("production requires a Secure anonymous session cookie")
            if self.anonymous_session_secret.get_secret_value() == DEVELOPMENT_SESSION_SECRET:
                raise ValueError("production requires an explicit anonymous session secret")
            if any(origin.startswith("http://") for origin in self.cors_origins):
                raise ValueError("production credentialed CORS origins must use HTTPS")
        if not self.anonymous_session_cookie_secure:
            for origin in self.cors_origins:
                parsed = urlsplit(origin)
                if parsed.scheme == "https":
                    continue
                hostname = (parsed.hostname or "").casefold()
                loopback = hostname in {"localhost", "127.0.0.1", "::1"}
                reserved_test = self.environment == "test" and hostname.endswith(".test")
                legacy_testserver = self.environment == "test" and hostname == "testserver"
                if not (loopback or reserved_test):
                    if legacy_testserver:
                        continue
                    raise ValueError(
                        "insecure cookies require loopback development or reserved test origins"
                    )
        if (
            self.collaborative_live_data_enabled
            and self.collaborative_contribution_consent_version is None
        ):
            raise ValueError("live collaborative data requires a contribution consent version")
        if self.collaborative_live_promotion_enabled and not self.collaborative_live_data_enabled:
            raise ValueError("live collaborative promotion requires live data to be enabled")
        if self.collaborative_allow_test_fixture and self.environment != "test":
            raise ValueError("collaborative fixture access is limited to ENVIRONMENT=test")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
