from datetime import UTC, datetime
from typing import cast

import pytest
from app.repositories.collaborative_registry import (
    CollaborativeArtifactRegistryRepository,
    collaborative_readiness_query,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

VALID_UNTIL = datetime(2026, 9, 29, tzinfo=UTC)


class _FakeResult:
    def __init__(self, record: dict[str, object] | None) -> None:
        self.record = record

    def mappings(self) -> "_FakeResult":
        return self

    def one_or_none(self) -> dict[str, object] | None:
        return self.record


class _FakeSession:
    def __init__(self, record: dict[str, object] | None) -> None:
        self.record = record
        self.executions = 0

    def execute(self, _statement: object) -> _FakeResult:
        self.executions += 1
        return _FakeResult(self.record)


def _record() -> dict[str, object]:
    return {
        "build_id": "stage5-live-build-v1",
        "source_kind": "live",
        "status": "active",
        "registered_revision": 7,
        "invalidation_epoch": 0,
        "contributor_count": 12,
        "consent_version": "stage-5-contribution-v1",
        "catalog_fingerprint": "a" * 64,
        "interaction_fingerprint": "b" * 64,
        "valid_until": VALID_UNTIL,
    }


def test_readiness_query_is_one_bounded_registry_lookup_without_membership_scan() -> None:
    compiled = collaborative_readiness_query("stage5-live-build-v1").compile(
        dialect=postgresql.dialect()
    )
    sql = str(compiled).lower()

    assert "from collaborative_artifact_builds" in sql
    assert "collaborative_artifact_contributors" not in sql
    assert " join " not in sql
    assert "count(" not in sql
    assert " limit " in sql
    assert len(compiled.params) == 2


def test_repository_maps_exactly_one_registry_row_to_the_readiness_contract() -> None:
    session = _FakeSession(_record())

    readiness = CollaborativeArtifactRegistryRepository(cast(Session, session)).readiness(
        "stage5-live-build-v1"
    )

    assert readiness is not None
    assert readiness.build_id == "stage5-live-build-v1"
    assert readiness.source_kind == "live"
    assert readiness.status == "active"
    assert readiness.registered_revision == 7
    assert readiness.invalidation_epoch == 0
    assert readiness.contributor_count == 12
    assert readiness.consent_version == "stage-5-contribution-v1"
    assert readiness.catalog_fingerprint == "a" * 64
    assert readiness.interaction_fingerprint == "b" * 64
    assert readiness.valid_until == VALID_UNTIL
    assert session.executions == 1


@pytest.mark.parametrize(
    "build_id",
    ["", "-leading-hyphen", "contains space", "x" * 129, 7],
)
def test_invalid_build_identity_returns_no_row_without_touching_the_database(
    build_id: object,
) -> None:
    session = _FakeSession(_record())

    readiness = CollaborativeArtifactRegistryRepository(cast(Session, session)).readiness(
        build_id  # type: ignore[arg-type]
    )

    assert readiness is None
    assert session.executions == 0


def test_missing_build_returns_none_after_one_query() -> None:
    session = _FakeSession(None)

    readiness = CollaborativeArtifactRegistryRepository(cast(Session, session)).readiness(
        "stage5-missing-build"
    )

    assert readiness is None
    assert session.executions == 1
