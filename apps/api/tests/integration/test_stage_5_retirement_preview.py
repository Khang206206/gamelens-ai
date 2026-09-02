import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.db.models import CollaborativeArtifactBuild
from app.db.session import create_session_factory
from app.services.collaborative_retirement import (
    CollaborativeRetirementPreviewError,
    CollaborativeRetirementPreviewService,
)
from gamelens_recommender.collaborative_artifacts import (
    CollaborativeBuildMetadata,
    build_collaborative_artifact,
)
from gamelens_recommender.collaborative_training import fit_collaborative_neighborhoods
from gamelens_recommender.interaction_snapshot import profile_fingerprint
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

CONSENT_VERSION = "stage-5-contribution-v1"
BUILD_STATUSES = (
    ("stage5-live-preview-active-v1", "active"),
    ("stage5-live-preview-invalidated-v1", "invalidated"),
    ("stage5-live-preview-retired-v1", "retired"),
)


def _build_bundle(
    root: Path,
    *,
    build_id: str,
    now: datetime,
) -> tuple[str, datetime, datetime]:
    item_slugs = (
        "emberfall-tactics",
        "neon-drift-arena",
        "orbital-farmstead",
        "signal-and-steel",
        "verdant-circuit",
        "warden-of-glass",
    )
    profiles = tuple(item_slugs for _index in range(12))
    neighborhoods = fit_collaborative_neighborhoods(
        profiles,
        catalog_slugs=frozenset(item_slugs),
    )
    cutoff = now - timedelta(hours=1)
    valid_until = now + timedelta(days=30)
    interaction_fingerprint = profile_fingerprint(profiles)
    build_collaborative_artifact(
        neighborhoods,
        root,
        metadata=CollaborativeBuildMetadata(
            source_kind="live",
            catalog_fingerprint="a" * 64,
            interaction_fingerprint=interaction_fingerprint,
            build_id=build_id,
            built_at=now,
            cutoff=cutoff,
            consent_version=CONSENT_VERSION,
            data_revision=7,
            valid_until=valid_until,
        ),
        revision_check=lambda revision: revision == 7,
    )
    return interaction_fingerprint, cutoff, valid_until


def _register_build(
    session: Session,
    *,
    build_id: str,
    status: str,
    interaction_fingerprint: str,
    cutoff: datetime,
    valid_until: datetime,
    now: datetime,
) -> None:
    invalidated_at = now if status in {"invalidated", "retired"} else None
    retired_at = now + timedelta(seconds=1) if status == "retired" else None
    session.add(
        CollaborativeArtifactBuild(
            build_id=build_id,
            source_kind="live",
            status=status,
            registered_revision=7,
            invalidation_epoch=0 if status == "active" else 1,
            expected_contributor_count=12,
            current_contributor_count=0,
            consent_version=CONSENT_VERSION,
            catalog_fingerprint="a" * 64,
            interaction_fingerprint=interaction_fingerprint,
            cutoff=cutoff,
            valid_until=valid_until,
            invalidated_at=invalidated_at,
            retired_at=retired_at,
        )
    )


def _filesystem_snapshot(root: Path) -> dict[str, tuple[int, int, str]]:
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_size,
            path.stat().st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_postgresql_retirement_preview_is_exact_read_only_and_idempotent(
    postgres_engine: Engine,
    postgres_session: Session,
    tmp_path: Path,
) -> None:
    artifact_set = tmp_path / "artifact-set"
    artifact_set.mkdir()
    now = datetime.now(UTC)
    for build_id, status in BUILD_STATUSES:
        interaction_fingerprint, cutoff, valid_until = _build_bundle(
            artifact_set / status,
            build_id=build_id,
            now=now,
        )
        _register_build(
            postgres_session,
            build_id=build_id,
            status=status,
            interaction_fingerprint=interaction_fingerprint,
            cutoff=cutoff,
            valid_until=valid_until,
            now=now,
        )
    postgres_session.commit()
    before_files = _filesystem_snapshot(artifact_set)
    before_rows = postgres_session.execute(
        select(
            CollaborativeArtifactBuild.build_id,
            CollaborativeArtifactBuild.status,
            CollaborativeArtifactBuild.invalidation_epoch,
        ).order_by(CollaborativeArtifactBuild.build_id)
    ).all()
    postgres_session.rollback()
    service = CollaborativeRetirementPreviewService(create_session_factory(postgres_engine))

    first = service.preview(
        artifact_set,
        database_fingerprint="a" * 12,
        configured_content_artifact=None,
        configured_collaborative_artifact=None,
    )
    second = service.preview(
        artifact_set,
        database_fingerprint="a" * 12,
        configured_content_artifact=None,
        configured_collaborative_artifact=None,
    )

    assert first == second
    assert first["summary"] == {"candidate_count": 2, "protected_count": 1}
    assert [item["registry_status"] for item in first["candidates"]] == [  # type: ignore[union-attr]
        "invalidated",
        "retired",
    ]
    assert [item["reason"] for item in first["candidates"]] == [  # type: ignore[union-attr]
        "registry_invalidated",
        "registry_retired",
    ]
    assert first["protected"][0]["reason"] == "registry_active"  # type: ignore[index]
    assert "user_id" not in json.dumps(first, sort_keys=True)
    assert "contributor" not in json.dumps(first, sort_keys=True)
    assert _filesystem_snapshot(artifact_set) == before_files
    after_rows = postgres_session.execute(
        select(
            CollaborativeArtifactBuild.build_id,
            CollaborativeArtifactBuild.status,
            CollaborativeArtifactBuild.invalidation_epoch,
        ).order_by(CollaborativeArtifactBuild.build_id)
    ).all()
    assert after_rows == before_rows


def test_postgresql_retirement_preview_rejects_unregistered_bundle_fail_closed(
    postgres_engine: Engine,
    tmp_path: Path,
) -> None:
    artifact_set = tmp_path / "artifact-set"
    artifact_set.mkdir()
    _build_bundle(
        artifact_set / "orphan",
        build_id="stage5-live-preview-orphan-v1",
        now=datetime.now(UTC),
    )
    before = _filesystem_snapshot(artifact_set)
    service = CollaborativeRetirementPreviewService(create_session_factory(postgres_engine))

    with pytest.raises(CollaborativeRetirementPreviewError) as caught:
        service.preview(
            artifact_set,
            database_fingerprint="b" * 12,
            configured_content_artifact=None,
            configured_collaborative_artifact=None,
        )

    assert caught.value.code == "retirement_bundle_unregistered"
    assert _filesystem_snapshot(artifact_set) == before
