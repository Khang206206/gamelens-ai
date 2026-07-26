from unittest.mock import Mock

from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError


def test_health_contract(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "GameLens AI API",
        "environment": "test",
        "database": "ready",
    }


def test_openapi_endpoints_are_available(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
        }
    }


def test_cors_allows_configured_origin(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "http://testserver",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://testserver"


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_health_reports_database_unavailable(test_settings: Settings) -> None:
    with TestClient(
        create_app(test_settings, database_health_check=lambda _engine: False)
    ) as unavailable_client:
        response = unavailable_client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "unavailable"


def test_health_uses_app_local_engine_and_lifespan_disposes_it(
    test_settings: Settings,
    monkeypatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    dispose = Mock(wraps=engine.dispose)
    monkeypatch.setattr(engine, "dispose", dispose)
    checked_engines = []

    with TestClient(
        create_app(
            test_settings,
            database_engine=engine,
            database_health_check=lambda checked: checked_engines.append(checked) or True,
        )
    ) as local_client:
        response = local_client.get("/health")

    assert response.status_code == 200
    assert checked_engines == [engine]
    dispose.assert_called_once_with()


def test_database_failures_use_safe_503_envelope(test_settings: Settings) -> None:
    app = create_app(test_settings, database_health_check=lambda _engine: True)

    @app.get("/database-failure")
    def database_failure() -> None:
        raise OperationalError(
            "SELECT 1",
            {},
            RuntimeError("password=must-not-be-returned"),
        )

    with TestClient(app, raise_server_exceptions=False) as error_client:
        response = error_client.get(
            "/database-failure",
            headers={"Origin": "http://testserver"},
        )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "database_unavailable",
            "message": "The database is temporarily unavailable",
        }
    }
    assert "must-not-be-returned" not in response.text
    assert response.headers["access-control-allow-origin"] == "http://testserver"


def test_unhandled_failures_use_safe_500_envelope(test_settings: Settings) -> None:
    app = create_app(test_settings, database_health_check=lambda _engine: True)

    @app.get("/unexpected-failure")
    def unexpected_failure() -> None:
        raise RuntimeError("private implementation detail")

    with TestClient(app, raise_server_exceptions=False) as error_client:
        response = error_client.get(
            "/unexpected-failure",
            headers={"Origin": "http://testserver"},
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "An unexpected internal error occurred",
        }
    }
    assert "private implementation detail" not in response.text
    assert response.headers["access-control-allow-origin"] == "http://testserver"


def test_configured_app_name_is_used_as_openapi_title(test_settings: Settings) -> None:
    custom_settings = test_settings.model_copy(update={"app_name": "Custom Catalog API"})
    with TestClient(
        create_app(custom_settings, database_health_check=lambda _engine: True)
    ) as custom_client:
        response = custom_client.get("/openapi.json")

    assert response.json()["info"]["title"] == "Custom Catalog API"
