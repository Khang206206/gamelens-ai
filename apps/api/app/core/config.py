import re
from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import SplitResult, urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


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
    )

    app_name: str = Field(default="GameLens AI API", min_length=1, max_length=100)
    environment: Literal["development", "test", "production"] = "development"
    api_host: str = Field(default="127.0.0.1", min_length=1, max_length=253)
    api_port: int = Field(default=8000, ge=1, le=65535)
    database_url: str = "postgresql+psycopg://gamelens:gamelens_dev_only@localhost:5432/gamelens"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

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

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use postgresql+psycopg")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
