from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url

ALLOWED_DESTRUCTIVE_TEST_DATABASE_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "test-db"})


@dataclass(frozen=True)
class ResolvedDatabaseIdentity:
    authority: str
    fingerprint: str
    server_address: str
    server_port: int
    database: str
    schema: str


def parse_utc(value: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    return parsed.astimezone(UTC)


def database_identity(database_url: str) -> tuple[str, str]:
    url = make_url(database_url)
    authority = f"{url.host or 'local'}:{url.port or 5432}/{url.database or ''}"
    fingerprint = hashlib.sha256(f"{url.drivername}|{authority}".encode()).hexdigest()[:12]
    return authority, fingerprint


def resolved_database_identity(
    database_url: str,
    *,
    server_address: str | None,
    server_port: int | None,
    database: str,
    schema: str,
) -> ResolvedDatabaseIdentity:
    expected = make_url(database_url)
    if not isinstance(database, str) or not database:
        raise RuntimeError("Refusing operator action: PostgreSQL returned no current database")
    if database != expected.database:
        raise RuntimeError(
            "Refusing operator action: the resolved database does not match DATABASE_URL"
        )
    if not isinstance(schema, str) or not schema.strip():
        raise RuntimeError("Refusing operator action: PostgreSQL returned no current schema")
    host = server_address or expected.host or "local"
    rendered_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    port = server_port or expected.port or 5432
    authority = f"{rendered_host}:{port}/{database}/{schema}"
    fingerprint = hashlib.sha256(f"{expected.drivername}|{authority}".encode()).hexdigest()[:12]
    return ResolvedDatabaseIdentity(
        authority=authority,
        fingerprint=fingerprint,
        server_address=host,
        server_port=port,
        database=database,
        schema=schema,
    )


def resolve_database_identity(engine: Engine, database_url: str) -> ResolvedDatabaseIdentity:
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    """
                    SELECT current_database() AS database_name,
                           current_schema() AS schema_name,
                           inet_server_addr()::text AS server_address,
                           inet_server_port() AS server_port
                    """
                )
            )
            .mappings()
            .one()
        )
        connection.rollback()
    return resolved_database_identity(
        database_url,
        server_address=row["server_address"],
        server_port=row["server_port"],
        database=row["database_name"],
        schema=row["schema_name"],
    )


def validate_test_execution_configuration(
    database_url: str,
    *,
    settings_environment: str,
    process_environment: str | None,
    allow_test_reset: str | None,
) -> None:
    test_configuration_present = (
        settings_environment == "test"
        or process_environment == "test"
        or allow_test_reset is not None
    )
    if not test_configuration_present:
        return

    url = make_url(database_url)
    failures: list[str] = []
    if settings_environment != "test":
        failures.append("settings ENVIRONMENT must be exactly 'test'")
    if process_environment != "test":
        failures.append("process ENVIRONMENT must be exactly 'test'")
    if allow_test_reset != "true":
        failures.append("GAMELENS_ALLOW_TEST_DATABASE_RESET must be exactly 'true'")
    if url.get_backend_name() != "postgresql":
        failures.append("the test database backend must be PostgreSQL")
    if not url.database or not url.database.endswith("_test"):
        failures.append("the test database name must end with '_test'")
    if (url.host or "").casefold() not in ALLOWED_DESTRUCTIVE_TEST_DATABASE_HOSTS:
        failures.append("the test database host is outside the destructive-test allowlist")
    if failures:
        raise RuntimeError("Refusing unsafe test operator action: " + "; ".join(failures))
