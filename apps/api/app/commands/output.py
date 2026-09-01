from __future__ import annotations

import json
from typing import NoReturn

COMMAND_FAILURE_EXIT_CODE = 2


def write_json(payload: object) -> None:
    """Write one deterministic machine-readable command result."""

    print(json.dumps(payload, indent=2, sort_keys=True))


def fail_command(error: Exception, *, fallback_code: str) -> NoReturn:
    """Emit the stable command error shape and terminate with the failure code."""

    candidate = getattr(error, "code", fallback_code)
    code = candidate if isinstance(candidate, str) and candidate else fallback_code
    write_json(
        {
            "status": "error",
            "error": {
                "code": code,
                "message": str(error),
            },
        }
    )
    raise SystemExit(COMMAND_FAILURE_EXIT_CODE) from error
