import pytest
from app.core.config import Settings
from pydantic import ValidationError


def test_settings_split_cors_origins() -> None:
    settings = Settings(
        _env_file=None,
        cors_origins=("http://localhost:3000,https://EXAMPLE.test:443/,https://example.test"),
    )

    assert settings.cors_origins == ["http://localhost:3000", "https://example.test"]
    assert settings.api_host == "127.0.0.1"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("environment", "staging"),
        ("api_port", 70000),
        ("log_level", "TRACE"),
        ("cors_origins", "*"),
        ("cors_origins", "http://"),
        ("cors_origins", "https://example.test/path"),
        ("cors_origins", "https://example.test?query=value"),
        ("cors_origins", "https://user@example.test"),
        ("cors_origins", "https://*.example.test"),
        ("cors_origins", "https://example.test:99999"),
        ("api_host", " "),
        ("app_name", ""),
        ("database_url", "sqlite:///local.db"),
    ],
)
def test_invalid_settings_fail(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})
