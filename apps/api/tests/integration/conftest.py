import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from app.core.config import Settings
from app.db.base import Base
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import validate_test_database_reset


def assert_connection_targets_guarded_database(
    connection: Connection,
    settings: Settings,
) -> None:
    expected_url = make_url(settings.database_url)
    if connection.engine.url != expected_url:
        raise RuntimeError(
            "Refusing destructive integration-test database operations: "
            "the engine URL does not match the guarded test settings"
        )

    actual_database = connection.scalar(text("SELECT current_database()"))
    if actual_database != expected_url.database:
        raise RuntimeError(
            "Refusing destructive integration-test database operations: "
            "the connected database does not match the guarded test database name"
        )


@pytest.fixture(scope="session")
def integration_settings() -> Settings:
    database_url = os.environ.get("GAMELENS_TEST_DATABASE_URL")
    if database_url is None:
        raise RuntimeError(
            "GAMELENS_TEST_DATABASE_URL is required; integration tests never fall back "
            "to DATABASE_URL or .env"
        )

    settings = Settings(
        _env_file=None,
        app_name="GameLens AI API",
        environment="test",
        api_host="127.0.0.1",
        api_port=8000,
        database_url=database_url,
        cors_origins=["http://testserver"],
        log_level="WARNING",
    )
    validate_test_database_reset(
        settings,
        process_environment=os.environ.get("ENVIRONMENT"),
        allow_reset=os.environ.get("GAMELENS_ALLOW_TEST_DATABASE_RESET"),
    )
    return settings


@pytest.fixture(scope="session")
def postgres_engine(integration_settings: Settings) -> Generator[Engine]:
    engine = create_engine(integration_settings.database_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_database(
    postgres_engine: Engine,
    integration_settings: Settings,
) -> Generator[None]:
    validate_test_database_reset(
        integration_settings,
        process_environment=os.environ.get("ENVIRONMENT"),
        allow_reset=os.environ.get("GAMELENS_ALLOW_TEST_DATABASE_RESET"),
    )
    config = Config("alembic.ini")
    with postgres_engine.connect() as connection:
        assert_connection_targets_guarded_database(connection, integration_settings)
        connection.rollback()
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        command.upgrade(config, "0001_initial_schema")
        command.upgrade(config, "head")
        command.check(config)
        current_revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        if current_revision != "0002_stage_1_integrity_hardening":
            raise RuntimeError(f"Unexpected Alembic head revision: {current_revision!r}")
    yield


def truncate_application_tables(engine: Engine, settings: Settings) -> None:
    validate_test_database_reset(
        settings,
        process_environment=os.environ.get("ENVIRONMENT"),
        allow_reset=os.environ.get("GAMELENS_ALLOW_TEST_DATABASE_RESET"),
    )
    table_names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        assert_connection_targets_guarded_database(connection, settings)
        connection.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def postgres_session(
    postgres_engine: Engine,
    integration_settings: Settings,
) -> Generator[Session]:
    truncate_application_tables(postgres_engine, integration_settings)
    session = sessionmaker(bind=postgres_engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        truncate_application_tables(postgres_engine, integration_settings)
