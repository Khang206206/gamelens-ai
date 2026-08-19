from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from datetime import timedelta
from time import perf_counter

from app.commands.operator_safety import (
    parse_utc,
    resolve_database_identity,
    validate_test_execution_configuration,
)
from app.core.config import get_settings
from app.core.security import utc_now
from app.db.session import create_database_engine, create_session_factory
from app.services.retention import RetentionCutoffs, RetentionService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview or explicitly purge bounded anonymous-data retention cohorts"
    )
    parser.add_argument("--execute", action="store_true", help="Perform deletion")
    parser.add_argument("--events-before", type=parse_utc)
    parser.add_argument("--expired-before", type=parse_utc)
    parser.add_argument("--revoked-before", type=parse_utc)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--confirm", help="Exact confirmation printed by preview")
    args = parser.parse_args()

    settings = get_settings()
    now = utc_now()
    events_before = args.events_before or now - timedelta(
        days=settings.recommendation_event_retention_days
    )
    expired_before = args.expired_before or now
    cutoffs = RetentionCutoffs(events_before, expired_before, args.revoked_before)
    if args.execute:
        if args.events_before is None or args.expired_before is None:
            parser.error("--execute requires explicit --events-before and --expired-before")
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
            f"PURGE {database.fingerprint} EVENTS {events_before.isoformat()} "
            f"USERS {expired_before.isoformat()}"
        )
        if args.revoked_before is not None:
            confirmation += f" REVOKED {args.revoked_before.isoformat()}"
        if args.execute and args.confirm != confirmation:
            parser.error("--execute requires the exact confirmation emitted by preview")
        batch_size = args.batch_size or settings.retention_batch_size
        service = RetentionService(
            create_session_factory(engine),
            batch_size=batch_size,
        )
        started_at = perf_counter()
        result = service.purge(cutoffs) if args.execute else service.preview(cutoffs)
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
