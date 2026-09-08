"""Read-only aggregate snapshots for the explicit Phase 8 container gate."""

import hashlib
import json
import os

from app.db.models import (
    CollaborativeArtifactBuild,
    CollaborativeArtifactContributor,
    CollaborativeDataRevision,
)
from sqlalchemy import select

from tests.fixtures.e2e_live_source import ARTIFACT_SET, _guarded_engine


def snapshot() -> dict:
    if os.getuid() == 0:
        raise RuntimeError("Isolation probe must run as non-root")
    files = {}
    for path in sorted(ARTIFACT_SET.rglob("*")):
        if path.is_symlink():
            raise RuntimeError("Unexpected artifact symlink")
        if path.is_file():
            payload = path.read_bytes()
            files[str(path.relative_to(ARTIFACT_SET))] = {
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
    if not files:
        raise RuntimeError("Isolation probe requires built artifacts")
    registry = {}
    with _guarded_engine() as (_, engine), engine.connect() as connection:
        for model in (
            CollaborativeArtifactBuild,
            CollaborativeArtifactContributor,
            CollaborativeDataRevision,
        ):
            rows = sorted(map(repr, connection.execute(select(model.__table__)).all()))
            registry[model.__tablename__] = {
                "rows": len(rows),
                "sha256": hashlib.sha256(json.dumps(rows).encode()).hexdigest(),
            }
    return {"files": files, "registry": registry, "runtime_uid": os.getuid()}


if __name__ == "__main__":
    print(json.dumps(snapshot(), sort_keys=True))
