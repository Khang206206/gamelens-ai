from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from time import perf_counter

from app.commands.operator_safety import (
    parse_utc,
    resolve_database_identity,
    validate_test_execution_configuration,
)
from app.core.config import get_settings
from app.db.session import create_database_engine, create_session_factory
from app.services.retention import AnonymousSessionRevocationService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview or explicitly revoke bounded anonymous-session cohorts"
    )
    parser.add_argument(
        "--created-before",
        type=parse_utc,
        required=True,
        help="Revoke active identities created at or before this UTC timestamp",
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--confirm", help="Exact confirmation printed by preview")
    args = parser.parse_args()

    settings = get_settings()
    if args.execute:
        validate_test_execution_configuration(
            settings.database_url,
            settings_environment=settings.environment,
            process_environment=os.environ.get("ENVIRONMENT"),
            allow_test_reset=os.environ.get("GAMELENS_ALLOW_TEST_DATABASE_RESET"),
        )
    engine = create_database_engine(settings.database_url)
    try:
        database = resolve_database_identity(engine, settings.database_url)
        confirmation = (
            f"REVOKE {database.fingerprint} CREATED THROUGH {args.created_before.isoformat()}"
        )
        if args.execute and args.confirm != confirmation:
            parser.error("--execute requires the exact confirmation emitted by preview")
        batch_size = args.batch_size or settings.retention_batch_size
        service = AnonymousSessionRevocationService(
            create_session_factory(engine),
            batch_size=batch_size,
        )
        started_at = perf_counter()
        result = (
            service.revoke(args.created_before)
            if args.execute
            else service.preview(args.created_before)
        )
        duration_ms = round((perf_counter() - started_at) * 1000, 3)
    finally:
        engine.dispose()
    output = asdict(result)
    output.update(
        {
            "mode": "execute" if args.execute else "preview",
            "database": database.authority,
            "database_fingerprint": database.fingerprint,
            "database_schema": database.schema,
            "batch_size": batch_size,
            "duration_ms": duration_ms,
            "execute_confirmation": confirmation,
        }
    )
    print(json.dumps(output, default=str, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
