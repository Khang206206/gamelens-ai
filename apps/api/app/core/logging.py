import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

DATABASE_CREDENTIAL_PATTERN = re.compile(
    r"(?i)\b(postgresql(?:\+[a-z0-9_-]+)?://[^:\s/@]+:)([^@\s/]+)(@)"
)
PASSWORD_ASSIGNMENT_PATTERN = re.compile(r"(?i)\b(password|passwd|pwd)(\s*=\s*)([^\s,;]+)")
STRUCTURED_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")
SAFE_EXTRA_FIELDS = (
    "request_id",
    "error_type",
    "method",
    "path",
    "status_code",
    "games_inserted",
    "games_updated",
    "games_unchanged",
    "taxonomies_inserted",
    "taxonomies_updated",
    "taxonomies_unchanged",
)


def redact_sensitive_text(value: str) -> str:
    value = DATABASE_CREDENTIAL_PATTERN.sub(r"\1***\3", value)
    return PASSWORD_ASSIGNMENT_PATTERN.sub(r"\1\2***", value)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_text(record.getMessage()),
        }
        for field in SAFE_EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = redact_sensitive_text(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(log_level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    for logger_name in STRUCTURED_LOGGERS:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(log_level)
        logger.propagate = False
