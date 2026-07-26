import pytest
from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

ALLOWED_DESTRUCTIVE_TEST_DATABASE_HOSTS = frozenset(
    {
        "127.0.0.1",
        "::1",
        "localhost",
        "test-db",
    }
)


def validate_test_database_reset(
    settings: Settings,
    *,
    process_environment: str | None,
    allow_reset: str | None,
) -> None:
    url = make_url(settings.database_url)
    failures: list[str] = []

    if process_environment != "test":
        failures.append("the process ENVIRONMENT must be exactly 'test'")
    if settings.environment != "test":
        failures.append("settings.environment must be exactly 'test'")
    if allow_reset != "true":
        failures.append("GAMELENS_ALLOW_TEST_DATABASE_RESET must be exactly 'true'")
    if url.get_backend_name() != "postgresql":
        failures.append("the database backend must be PostgreSQL")
    if not url.database or not url.database.endswith("_test"):
        failures.append("the database name must end with '_test'")
    if (url.host or "").lower() not in ALLOWED_DESTRUCTIVE_TEST_DATABASE_HOSTS:
        failures.append("the database host is not in the destructive-test allowlist")

    if failures:
        raise RuntimeError(
            "Refusing destructive integration-test database operations: " + "; ".join(failures)
        )


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run tests that reset the explicitly configured disposable PostgreSQL database",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-integration"):
        return

    integration_items = [item for item in items if "integration" in item.keywords]
    if integration_items and len(integration_items) == len(items):
        raise pytest.UsageError(
            "Integration-only test runs require --run-integration and an explicitly "
            "authorized disposable PostgreSQL database"
        )

    skip_integration = pytest.mark.skip(
        reason="integration tests require --run-integration and a disposable test database"
    )
    for item in integration_items:
        item.add_marker(skip_integration)


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_name="GameLens AI API",
        environment="test",
        api_host="127.0.0.1",
        api_port=8000,
        database_url="postgresql+psycopg://test:test@localhost:5433/gamelens_test",
        cors_origins=["http://testserver"],
        log_level="WARNING",
    )


@pytest.fixture
def client(test_settings: Settings) -> TestClient:
    with TestClient(
        create_app(test_settings, database_health_check=lambda _engine: True)
    ) as test_client:
        yield test_client
