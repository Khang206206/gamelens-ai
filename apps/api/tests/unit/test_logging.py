import json
import logging

from app.core.logging import JsonFormatter, configure_logging


def test_json_formatter_redacts_database_credentials_and_passwords() -> None:
    record = logging.LogRecord(
        name="app.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=(
            "Failed postgresql+psycopg://gamelens:super-secret@db:5432/gamelens "
            "password=another-secret"
        ),
        args=(),
        exc_info=None,
    )
    record.error_type = "OperationalError"

    payload = json.loads(JsonFormatter().format(record))

    assert "super-secret" not in payload["message"]
    assert "another-secret" not in payload["message"]
    assert "postgresql+psycopg://gamelens:***@db:5432/gamelens" in payload["message"]
    assert payload["error_type"] == "OperationalError"


def test_configure_logging_applies_json_to_root_and_uvicorn_loggers() -> None:
    loggers = [
        logging.getLogger(),
        logging.getLogger("uvicorn"),
        logging.getLogger("uvicorn.error"),
        logging.getLogger("uvicorn.access"),
    ]
    snapshots = [
        (logger, list(logger.handlers), logger.level, logger.propagate) for logger in loggers
    ]
    try:
        configure_logging("WARNING")

        for logger in loggers:
            assert logger.level == logging.WARNING
            assert len(logger.handlers) == 1
            assert isinstance(logger.handlers[0].formatter, JsonFormatter)
    finally:
        for logger, handlers, level, propagate in snapshots:
            logger.handlers = handlers
            logger.setLevel(level)
            logger.propagate = propagate
