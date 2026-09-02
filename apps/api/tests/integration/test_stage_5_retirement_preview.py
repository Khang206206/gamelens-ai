import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from app.commands.collaborative_artifact import (
    cleanup_collaborative_artifacts,
    preview_collaborative_retirement,
    recover_collaborative_files,
)
from app.core.config import Settings
from app.db.models import CollaborativeArtifactBuild
from app.db.session import create_session_factory
from app.services import collaborative_retirement
from app.services.collaborative_recovery import PROMOTION_LOCK_BYTES
from app.services.collaborative_retirement import (
    CollaborativeArtifactCleanupService,
    CollaborativeRetirementPreviewError,
    CollaborativeRetirementPreviewService,
)
from gamelens_recommender.collaborative_artifacts import (
    CollaborativeArtifactError,
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


def test_confirmed_postgresql_cleanup_removes_only_exact_non_active_bundles(
    postgres_engine: Engine,
    postgres_session: Session,
    tmp_path: Path,
) -> None:
    artifact_set = tmp_path / "artifact-set"
    artifact_set.mkdir()
    content_artifact = artifact_set / "content-artifact"
    content_artifact.write_bytes(b"protected-content-artifact")
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
    before_rows = postgres_session.execute(
        select(
            CollaborativeArtifactBuild.build_id,
            CollaborativeArtifactBuild.status,
            CollaborativeArtifactBuild.invalidation_epoch,
        ).order_by(CollaborativeArtifactBuild.build_id)
    ).all()
    postgres_session.rollback()
    session_factory = create_session_factory(postgres_engine)
    preview_arguments = {
        "database_fingerprint": "c" * 12,
        "configured_content_artifact": content_artifact,
        "configured_collaborative_artifact": None,
    }
    preview = CollaborativeRetirementPreviewService(session_factory).preview(
        artifact_set,
        **preview_arguments,
    )
    confirmation = preview["cleanup_confirmation"]
    assert isinstance(confirmation, str)

    result = CollaborativeArtifactCleanupService(session_factory).cleanup(
        artifact_set,
        **preview_arguments,
        confirmation=confirmation,
    )

    assert result["summary"] == {
        "selected_count": 2,
        "removed_count": 2,
        "remaining_candidate_count": 0,
        "protected_count": 2,
    }
    assert [item["registry_status"] for item in result["removed"]] == [  # type: ignore[union-attr]
        "invalidated",
        "retired",
    ]
    assert (artifact_set / "active").is_dir()
    assert not (artifact_set / "invalidated").exists()
    assert not (artifact_set / "retired").exists()
    assert content_artifact.read_bytes() == b"protected-content-artifact"
    assert "user_id" not in json.dumps(result, sort_keys=True)
    assert "contributor" not in json.dumps(result, sort_keys=True)
    after_rows = postgres_session.execute(
        select(
            CollaborativeArtifactBuild.build_id,
            CollaborativeArtifactBuild.status,
            CollaborativeArtifactBuild.invalidation_epoch,
        ).order_by(CollaborativeArtifactBuild.build_id)
    ).all()
    assert after_rows == before_rows

    with pytest.raises(CollaborativeRetirementPreviewError) as stale:
        CollaborativeArtifactCleanupService(session_factory).cleanup(
            artifact_set,
            **preview_arguments,
            confirmation=confirmation,
        )
    assert stale.value.code == "cleanup_confirmation_mismatch"
    assert (artifact_set / "active").is_dir()
    assert content_artifact.is_file()


def test_cleanup_rejects_registry_change_after_preview_without_removing_bundle(
    postgres_engine: Engine,
    postgres_session: Session,
    tmp_path: Path,
) -> None:
    artifact_set = tmp_path / "artifact-set"
    artifact_set.mkdir()
    now = datetime.now(UTC)
    build_id = "stage5-live-preview-state-change-v1"
    interaction_fingerprint, cutoff, valid_until = _build_bundle(
        artifact_set / "candidate",
        build_id=build_id,
        now=now,
    )
    _register_build(
        postgres_session,
        build_id=build_id,
        status="invalidated",
        interaction_fingerprint=interaction_fingerprint,
        cutoff=cutoff,
        valid_until=valid_until,
        now=now,
    )
    postgres_session.commit()
    session_factory = create_session_factory(postgres_engine)
    preview_arguments = {
        "database_fingerprint": "d" * 12,
        "configured_content_artifact": None,
        "configured_collaborative_artifact": None,
    }
    preview = CollaborativeRetirementPreviewService(session_factory).preview(
        artifact_set,
        **preview_arguments,
    )
    confirmation = preview["cleanup_confirmation"]
    assert isinstance(confirmation, str)
    build = postgres_session.get(CollaborativeArtifactBuild, build_id)
    assert build is not None
    build.status = "retired"
    build.retired_at = now + timedelta(seconds=1)
    postgres_session.commit()

    with pytest.raises(CollaborativeRetirementPreviewError) as caught:
        CollaborativeArtifactCleanupService(session_factory).cleanup(
            artifact_set,
            **preview_arguments,
            confirmation=confirmation,
        )

    assert caught.value.code == "cleanup_confirmation_mismatch"
    assert (artifact_set / "candidate").is_dir()


def test_interrupted_postgresql_cleanup_recovers_from_durable_receipt(
    postgres_session: Session,
    integration_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "artifact-set"
    root.mkdir()
    content = root / "content"
    content.write_bytes(b"protected-content")
    build_id = "stage5-cleanup-recovery-v1"
    original = root / "retired"
    now = datetime.now(UTC)
    interaction_fingerprint, cutoff, valid_until = _build_bundle(
        original, build_id=build_id, now=now
    )
    _register_build(
        postgres_session,
        build_id=build_id,
        status="retired",
        interaction_fingerprint=interaction_fingerprint,
        cutoff=cutoff,
        valid_until=valid_until,
        now=now,
    )
    postgres_session.commit()
    settings = integration_settings.model_copy(
        update={"model_artifact_path": content, "collaborative_artifact_path": None}
    )
    preview = preview_collaborative_retirement(settings, artifact_set=root)

    def interrupted_remove(path: Path) -> None:
        assert path.name == "bundle"
        (path / "manifest.json").unlink()
        raise OSError("simulated interruption after first deletion")

    with monkeypatch.context() as patch:
        patch.setattr(collaborative_retirement.shutil, "rmtree", interrupted_remove)
        with pytest.raises(CollaborativeRetirementPreviewError) as interrupted:
            cleanup_collaborative_artifacts(
                settings, artifact_set=root, confirmation=preview["cleanup_confirmation"]
            )
    assert interrupted.value.code == "cleanup_filesystem_failed"
    assert not original.exists()
    quarantine = next(root.glob(".gamelens-cleanup-*"))
    assert (quarantine / "receipt.json").is_file()
    assert not (quarantine / "bundle" / "manifest.json").exists()
    before = _filesystem_snapshot(root)
    arguments = {"artifact_set": root, "target": quarantine, "kind": "cleanup"}
    recovery_preview = recover_collaborative_files(settings, **arguments)
    assert recover_collaborative_files(settings, **arguments) == recovery_preview
    assert _filesystem_snapshot(root) == before
    assert "user_id" not in json.dumps(recovery_preview)
    assert "contributor" not in json.dumps(recovery_preview)

    result = recover_collaborative_files(
        settings,
        **arguments,
        execute=True,
        writers_stopped=True,
        confirmation=recovery_preview["recovery_confirmation"],
    )

    assert result["operation"] == "recovery_cleanup"
    assert result["removed_count"] == 1
    assert not quarantine.exists()
    assert content.read_bytes() == b"protected-content"
    postgres_session.expire_all()
    row = postgres_session.get(CollaborativeArtifactBuild, build_id)
    assert row is not None
    assert (row.status, row.invalidation_epoch, row.current_contributor_count) == ("retired", 1, 0)
    with pytest.raises(CollaborativeRetirementPreviewError) as stale:
        recover_collaborative_files(
            settings,
            **arguments,
            execute=True,
            writers_stopped=True,
            confirmation=recovery_preview["recovery_confirmation"],
        )
    assert stale.value.code == "recovery_confirmation_mismatch"


@pytest.mark.parametrize("registered", [True, False])
def test_postgresql_build_file_recovery_preserves_active_or_orphan_final_bundle(
    postgres_session: Session,
    integration_settings: Settings,
    tmp_path: Path,
    registered: bool,
) -> None:
    root = tmp_path / "artifact-set"
    root.mkdir()
    final = root / "candidate"
    build_id = "stage5-build-debris-recovery-v1"
    now = datetime.now(UTC)
    interaction_fingerprint, cutoff, valid_until = _build_bundle(final, build_id=build_id, now=now)
    if registered:
        _register_build(
            postgres_session,
            build_id=build_id,
            status="active",
            interaction_fingerprint=interaction_fingerprint,
            cutoff=cutoff,
            valid_until=valid_until,
            now=now,
        )
        postgres_session.commit()
    temporary = root / ".candidate.tmp-abcdefgh"
    temporary.mkdir()
    (temporary / "item-slugs.json").write_bytes(b"[]")
    lock = root / ".candidate.promotion.lock"
    lock.write_bytes(PROMOTION_LOCK_BYTES)
    settings = integration_settings.model_copy(update={"collaborative_artifact_path": final})
    arguments = {"artifact_set": root, "target": final, "kind": "build"}
    before = _filesystem_snapshot(final)
    preview = recover_collaborative_files(settings, **arguments)

    result = recover_collaborative_files(
        settings,
        **arguments,
        execute=True,
        writers_stopped=True,
        confirmation=preview["recovery_confirmation"],
    )

    assert result["removed_count"] == 2
    assert _filesystem_snapshot(final) == before
    assert not temporary.exists()
    assert not lock.exists()
    postgres_session.expire_all()
    row = postgres_session.get(CollaborativeArtifactBuild, build_id)
    if registered:
        assert row is not None and row.status == "active" and row.invalidation_epoch == 0
    else:
        assert row is None


def test_build_can_retry_only_after_explicit_stale_workspace_recovery(
    postgres_session: Session,
    integration_settings: Settings,
    tmp_path: Path,
) -> None:
    root = tmp_path / "artifact-set"
    root.mkdir()
    target = root / "candidate"
    temporary = root / ".candidate.tmp-abcdefgh"
    temporary.mkdir()
    (temporary / "item-slugs.json").write_bytes(b"[]")
    lock = root / ".candidate.promotion.lock"
    lock.write_bytes(PROMOTION_LOCK_BYTES)
    with pytest.raises(CollaborativeArtifactError) as locked:
        _build_bundle(target, build_id="stage5-build-after-recovery-v1", now=datetime.now(UTC))
    assert locked.value.code == "artifact_target_exists"
    arguments = {"artifact_set": root, "target": target, "kind": "build"}
    preview = recover_collaborative_files(integration_settings, **arguments)
    recover_collaborative_files(
        integration_settings,
        **arguments,
        execute=True,
        writers_stopped=True,
        confirmation=preview["recovery_confirmation"],
    )
    assert not target.exists()
    assert not lock.exists()
    assert not temporary.exists()

    _build_bundle(target, build_id="stage5-build-after-recovery-v1", now=datetime.now(UTC))

    assert (target / "manifest.json").is_file()
    assert not lock.exists()
    assert (
        postgres_session.get(CollaborativeArtifactBuild, "stage5-build-after-recovery-v1") is None
    )
