from pathlib import Path

import pytest
from app.core.config import DEVELOPMENT_SESSION_SECRET, Settings
from pydantic import ValidationError


def test_settings_split_cors_origins() -> None:
    settings = Settings(
        _env_file=None,
        cors_origins=("http://localhost:3000,https://EXAMPLE.test:443/,https://example.test"),
        anonymous_session_cookie_secure=True,
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
        ("anonymous_session_secret", "too-short"),
        ("anonymous_session_cookie_name", "invalid cookie name"),
        ("anonymous_session_cookie_path", "api/v1"),
        ("anonymous_session_ttl_seconds", 3599),
        ("consent_version", " "),
        ("csrf_header_name", "invalid header"),
        ("recommendation_event_retention_days", 0),
        ("retention_batch_size", 10_001),
    ],
)
def test_invalid_settings_fail(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_production_requires_https_secure_cookie_and_explicit_secret() -> None:
    with pytest.raises(ValidationError, match="Secure anonymous session cookie"):
        Settings(
            _env_file=None,
            environment="production",
            cors_origins=["https://app.example.com"],
        )

    with pytest.raises(ValidationError, match="explicit anonymous session secret"):
        Settings(
            _env_file=None,
            environment="production",
            cors_origins=["https://app.example.com"],
            anonymous_session_cookie_secure=True,
            anonymous_session_secret=DEVELOPMENT_SESSION_SECRET,
        )

    with pytest.raises(ValidationError, match="must use HTTPS"):
        Settings(
            _env_file=None,
            environment="production",
            cors_origins=["http://app.example.com"],
            anonymous_session_cookie_secure=True,
            anonymous_session_secret="production-only-secret-with-at-least-32-bytes",
        )


def test_production_accepts_explicit_secure_session_configuration() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        cors_origins=["https://app.example.com"],
        anonymous_session_cookie_secure=True,
        anonymous_session_secret="production-only-secret-with-at-least-32-bytes",
    )

    assert settings.anonymous_session_cookie_secure is True
    assert settings.anonymous_session_cookie_path == "/api/v1"
    assert settings.anonymous_session_ttl_seconds == 180 * 24 * 60 * 60
    assert settings.recommendation_event_retention_days == 90


def test_session_secret_is_redacted_from_settings_representations() -> None:
    raw_secret = "unit-test-secret-that-must-not-appear-in-settings-output"
    settings = Settings(
        _env_file=None,
        anonymous_session_secret=raw_secret,
    )

    assert settings.anonymous_session_secret.get_secret_value() == raw_secret
    assert raw_secret not in repr(settings)
    assert raw_secret not in settings.model_dump_json()


@pytest.mark.parametrize(
    ("field", "secret_value"),
    [
        ("anonymous_session_secret", "SENSITIVE_SHORT_VALUE"),
        ("database_url", "postgresql://secret-user:secret-pass@db/gamelens"),
    ],
)
def test_invalid_security_settings_hide_input_from_validation_errors(
    field: str,
    secret_value: str,
) -> None:
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, **{field: secret_value})

    assert secret_value not in str(error.value)


def test_insecure_cookie_is_limited_to_loopback_or_test_origins() -> None:
    development = Settings(
        _env_file=None,
        environment="development",
        cors_origins=["http://localhost:3000"],
    )
    test = Settings(
        _env_file=None,
        environment="test",
        cors_origins=["http://web.gamelens.test:3000"],
    )

    assert development.anonymous_session_cookie_secure is False
    assert test.anonymous_session_cookie_secure is False

    with pytest.raises(ValidationError, match="insecure cookies require"):
        Settings(
            _env_file=None,
            environment="development",
            cors_origins=["http://web.gamelens.test:3000"],
        )


def test_collaborative_live_data_is_default_off_and_requires_contribution_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable in (
        "COLLABORATIVE_LIVE_DATA_ENABLED",
        "COLLABORATIVE_CONTRIBUTION_CONSENT_VERSION",
        "COLLABORATIVE_ALLOW_TEST_FIXTURE",
        "COLLABORATIVE_ARTIFACT_PATH",
    ):
        monkeypatch.delenv(variable, raising=False)
    settings = Settings(_env_file=None)

    assert settings.collaborative_live_data_enabled is False
    assert settings.collaborative_contribution_consent_version is None
    assert settings.collaborative_allow_test_fixture is False
    assert settings.collaborative_artifact_path is None

    blank_path = Settings(_env_file=None, collaborative_artifact_path="   ")
    assert blank_path.collaborative_artifact_path is None

    configured_path = Settings(
        _env_file=None,
        collaborative_artifact_path="ml/artifacts/collaborative-v1",
    )
    assert configured_path.collaborative_artifact_path == Path("ml/artifacts/collaborative-v1")

    with pytest.raises(ValidationError, match="contribution consent version"):
        Settings(_env_file=None, collaborative_live_data_enabled=True)

    enabled = Settings(
        _env_file=None,
        collaborative_live_data_enabled=True,
        collaborative_contribution_consent_version=" stage-5-contribution-v1 ",
    )
    assert enabled.collaborative_contribution_consent_version == "stage-5-contribution-v1"

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            collaborative_contribution_consent_version="x" * 101,
        )


def test_collaborative_fixture_gate_is_test_only() -> None:
    with pytest.raises(ValidationError, match="ENVIRONMENT=test"):
        Settings(
            _env_file=None,
            environment="development",
            cors_origins=["http://localhost:3000"],
            collaborative_allow_test_fixture=True,
        )

    settings = Settings(
        _env_file=None,
        environment="test",
        cors_origins=["http://testserver"],
        collaborative_allow_test_fixture=True,
    )
    assert settings.collaborative_allow_test_fixture is True
