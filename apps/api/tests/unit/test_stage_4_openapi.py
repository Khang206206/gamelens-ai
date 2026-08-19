import json

from app.core.config import Settings
from app.main import ANONYMOUS_SESSION_SECURITY_SCHEME, create_app


def _header_parameter(operation: dict[str, object], name: str) -> dict[str, object]:
    return next(
        parameter
        for parameter in operation.get("parameters", [])  # type: ignore[union-attr]
        if isinstance(parameter, dict)
        and str(parameter.get("name", "")).casefold() == name.casefold()
    )


def test_openapi_describes_runtime_cookie_csrf_origin_and_no_store_contracts(
    test_settings: Settings,
) -> None:
    schema = create_app(
        test_settings,
        database_health_check=lambda _engine: True,
    ).openapi()
    security_scheme = schema["components"]["securitySchemes"][ANONYMOUS_SESSION_SECURITY_SCHEME]
    assert security_scheme == {
        "type": "apiKey",
        "in": "cookie",
        "name": test_settings.anonymous_session_cookie_name,
        "description": "Host-only HttpOnly anonymous-session cookie.",
    }

    initial_consent = schema["paths"]["/api/v1/anonymous-sessions"]["post"]
    assert initial_consent["security"] == [
        {},
        {ANONYMOUS_SESSION_SECURITY_SCHEME: []},
    ]
    assert _header_parameter(initial_consent, "Origin")["required"] is True
    assert _header_parameter(initial_consent, test_settings.csrf_header_name)["required"] is False

    protected_write = schema["paths"]["/api/v1/me/preferences"]["put"]
    assert protected_write["security"] == [{ANONYMOUS_SESSION_SECURITY_SCHEME: []}]
    assert _header_parameter(protected_write, "Origin")["required"] is True
    assert _header_parameter(protected_write, test_settings.csrf_header_name)["required"] is True

    for path, path_item in schema["paths"].items():
        if path != "/api/v1/anonymous-sessions" and not path.startswith("/api/v1/me"):
            continue
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "delete", "patch"}:
                continue
            for response in operation["responses"].values():
                assert response["headers"]["Cache-Control"]["schema"]["enum"] == ["no-store"]

    assert "security" not in schema["paths"]["/api/v1/recommendations"]["post"]
    assert test_settings.anonymous_session_secret.get_secret_value() not in json.dumps(schema)
