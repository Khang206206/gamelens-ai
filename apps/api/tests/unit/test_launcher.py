from unittest.mock import Mock

from app import __main__ as launcher
from app.core.config import Settings


def test_module_launcher_uses_configured_bind_address(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        app_name="Launcher Test",
        environment="test",
        api_host="127.0.0.7",
        api_port=8123,
        database_url="postgresql+psycopg://test:test@localhost:5433/gamelens_test",
        cors_origins=["http://testserver"],
        log_level="WARNING",
    )
    run = Mock()
    monkeypatch.setattr(launcher, "get_settings", lambda: settings)
    monkeypatch.setattr(launcher.uvicorn, "run", run)

    launcher.main()

    run.assert_called_once_with(
        "app.main:app",
        host="127.0.0.7",
        port=8123,
        log_level="warning",
    )
