import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command as alembic_command
from alembic.config import Config
from app.commands import collaborative_artifact as artifact_command
from app.commands import collaborative_snapshot as snapshot_command
from app.core.config import Settings
from app.db.base import Base
from app.db.models import (
    CollaborativeArtifactBuild,
    CollaborativeContributionConsent,
    PreferenceType,
    User,
    UserPreference,
)
from app.db.seed import load_seed_file, seed_database
from app.main import create_app
from app.services import collaborative_build, collaborative_retirement
from fastapi.testclient import TestClient
from gamelens_recommender import build_artifact
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.integration.conftest import assert_connection_targets_guarded_database
from tests.integration.test_stage_5_live_build_promotion import _live_settings, _seed_live_cohort
from tests.integration.test_stage_5_retirement_preview import _filesystem_snapshot

pytestmark = pytest.mark.integration


def _database_snapshot(session: Session) -> dict[str, list[tuple[object, ...]]]:
    session.expire_all()
    result = {
        table.name: sorted([tuple(row) for row in session.execute(select(table)).all()], key=repr)
        for table in Base.metadata.sorted_tables
    }
    session.rollback()
    return result


def _assert_no_private_payload(value: object) -> None:
    forbidden = {
        "user_id",
        "user_ids",
        "contributor_user_ids",
        "cohort_mapping",
        "anonymous_token",
        "anonymous_token_hash",
        "anonymous_token_digest",
        "session_token",
        "token_digest",
        "database_url",
        "secret",
    }
    if isinstance(value, dict):
        assert not forbidden.intersection(value)
        for item in value.values():
            _assert_no_private_payload(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_private_payload(item)


@pytest.mark.parametrize("authority_loss", ["withdrawal", "delete"])
def test_operator_cli_lifecycle_handoff_on_disposable_postgresql(
    postgres_session: Session,
    integration_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    authority_loss: str,
) -> None:
    user_ids, _ = _seed_live_cohort(postgres_session)
    private_digests = tuple(postgres_session.scalars(select(User.anonymous_token_digest)).all())
    postgres_session.rollback()
    root = tmp_path / "artifact-set"
    root.mkdir()
    content = build_artifact(
        snapshot_command.catalog_from_seed(artifact_command.DEFAULT_SEED_PATH), root / "content"
    )
    settings = _live_settings(integration_settings).model_copy(
        update={"model_artifact_path": content, "collaborative_artifact_path": root / "current"}
    )
    original_settings = settings.model_dump()
    content_before = _filesystem_snapshot(content)
    monkeypatch.setattr(artifact_command, "get_settings", lambda: settings)
    monkeypatch.setattr(snapshot_command, "get_settings", lambda: settings)

    def run(*args: str, audit: bool = False, error_code: str | None = None) -> dict:
        monkeypatch.setattr(sys, "argv", ["operator", *args])
        if error_code:
            with pytest.raises(SystemExit) as caught:
                (snapshot_command if audit else artifact_command).main()
            assert caught.value.code == 2
        else:
            (snapshot_command if audit else artifact_command).main()
        captured = capsys.readouterr()
        assert not any(digest in captured.out + captured.err for digest in private_digests)
        payload = json.loads(captured.out)
        _assert_no_private_payload(payload)
        if error_code:
            assert payload["error"]["code"] == error_code
        return payload

    before_audit = _database_snapshot(postgres_session)
    before_files = _filesystem_snapshot(root)
    for _ in range(2):
        audited = run("audit", "--source", "live", audit=True)
        assert audited["ready_for_functional_build"] is True
    assert _database_snapshot(postgres_session) == before_audit
    assert _filesystem_snapshot(root) == before_files

    revisions = []
    for name in ("previous", "current"):
        build_id = f"handoff-{name}"
        built = run(
            "build",
            "--source",
            "live",
            "--output",
            str(root / name),
            "--build-id",
            build_id,
            "--confirm-live-build",
            build_id,
        )
        assert built["promotion"]["status"] == "active"
        assert built["promotion"]["contributor_count"] == 12
        revisions.append(built["lifecycle"]["data_revision"])
        if name == "previous":
            # New positive evidence changes the source revision, but does not
            # invalidate existing lineage or prevent valid-only manual rollback.
            postgres_session.add(
                UserPreference(
                    user_id=user_ids[0],
                    preference_type=PreferenceType.GAME,
                    value="harborlight",
                    weight=Decimal("1"),
                )
            )
            postgres_session.commit()
    assert revisions[1] > revisions[0]
    before_reads = _database_snapshot(postgres_session)
    files_before_reads = _filesystem_snapshot(root)
    for name in ("previous", "current"):
        for operation in ("validate", "inspect", "rollback-check"):
            first = run(operation, "--artifact", str(root / name))
            assert run(operation, "--artifact", str(root / name)) == first
        assert first["candidate_artifact_path"] == str(root / name)
        assert first["configuration_changed"] is False
    preview = run("retirement-preview", "--artifact-set", str(root))
    assert preview["summary"] == {"candidate_count": 0, "protected_count": 3}
    assert run("retirement-preview", "--artifact-set", str(root)) == preview
    assert _database_snapshot(postgres_session) == before_reads
    assert _filesystem_snapshot(root) == files_before_reads

    # Build never overwrites an existing target, including a valid rollback bundle.
    run(
        "build",
        "--output",
        str(root / "previous"),
        "--build-id",
        "handoff-overwrite",
        "--confirm-live-build",
        "handoff-overwrite",
        error_code="artifact_target_exists",
    )
    assert _database_snapshot(postgres_session) == before_reads
    assert _filesystem_snapshot(root) == files_before_reads

    if authority_loss == "withdrawal":
        consent = postgres_session.get(CollaborativeContributionConsent, user_ids[0])
        assert consent is not None
        consent.withdrawn_at = datetime.now(UTC)
    else:
        user = postgres_session.get(User, user_ids[0])
        assert user is not None
        postgres_session.delete(user)
    postgres_session.flush()
    postgres_session.expire_all()
    assert {row.status for row in postgres_session.scalars(select(CollaborativeArtifactBuild))} == {
        "invalidated"
    }
    postgres_session.commit()
    for name in ("previous", "current"):
        run(
            "rollback-check",
            "--artifact",
            str(root / name),
            error_code="rollback_candidate_not_ready",
        )
    run(
        "recover",
        "--artifact",
        str(root / "previous"),
        "--build-id",
        "handoff-previous",
        "--confirm-live-recovery",
        "handoff-previous",
        error_code="revision_race",
    )
    run("retire", "--build-id", "handoff-previous", "--confirm-retirement", "handoff-previous")
    run(
        "rollback-check",
        "--artifact",
        str(root / "previous"),
        error_code="rollback_candidate_not_ready",
    )

    before_cleanup = _database_snapshot(postgres_session)
    preview = run("retirement-preview", "--artifact-set", str(root))
    assert preview["summary"] == {"candidate_count": 1, "protected_count": 2}
    assert preview["candidates"][0]["path"] == str(root / "previous")
    assert preview["candidates"][0]["reason"] == "registry_retired"
    run(
        "cleanup",
        "--artifact-set",
        str(root),
        "--confirm-cleanup",
        "wrong",
        error_code="cleanup_confirmation_mismatch",
    )
    assert _filesystem_snapshot(root) == files_before_reads
    cleaned = run(
        "cleanup", "--artifact-set", str(root), "--confirm-cleanup", preview["cleanup_confirmation"]
    )
    assert cleaned["status"] == "ok"
    assert not (root / "previous").exists()
    assert (root / "current").is_dir()  # Configured path stays protected even if invalidated.
    assert _filesystem_snapshot(content) == content_before
    assert _database_snapshot(postgres_session) == before_cleanup
    assert settings.model_dump() == original_settings
    final_preview = run("retirement-preview", "--artifact-set", str(root))
    assert final_preview["summary"] == {"candidate_count": 0, "protected_count": 2}
    for manifest in root.rglob("*.json"):
        serialized = manifest.read_text()
        assert not any(digest in serialized for digest in private_digests)
        _assert_no_private_payload(json.loads(serialized))
    assert not any(digest in caplog.text for digest in private_digests)


def test_startup_seed_and_populated_migration_do_not_mutate_derived_state(
    postgres_engine: Engine,
    postgres_session: Session,
    integration_settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_live_cohort(postgres_session)
    settings = _live_settings(integration_settings)
    target = tmp_path / "live"
    artifact_command.build_live_artifact(
        settings, target, build_id="handoff-nonmutation", confirmation="handoff-nonmutation"
    )
    for status in ("invalidated", "retired"):
        build_id = f"handoff-nonmutation-{status}"
        artifact_command.build_live_artifact(
            settings, tmp_path / status, build_id=build_id, confirmation=build_id
        )
        artifact_command.mutate_live_artifact_lifecycle(
            settings, operation="invalidate", build_id=build_id, confirmation=build_id
        )
        if status == "retired":
            artifact_command.mutate_live_artifact_lifecycle(
                settings, operation="retire", build_id=build_id, confirmation=build_id
            )
    settings = settings.model_copy(update={"collaborative_artifact_path": target})
    before_db = _database_snapshot(postgres_session)
    before_files = _filesystem_snapshot(tmp_path)

    def forbidden_mutation(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Ordinary lifecycle entrypoint attempted derived-data mutation")

    for method in ("build", "recover", "_register"):
        monkeypatch.setattr(
            collaborative_build.CollaborativeLiveBuildService, method, forbidden_mutation
        )
    monkeypatch.setattr(collaborative_build, "build_collaborative_artifact", forbidden_mutation)
    monkeypatch.setattr(
        collaborative_retirement.CollaborativeArtifactCleanupService, "cleanup", forbidden_mutation
    )
    with TestClient(create_app(settings=settings, database_engine=postgres_engine)) as client:
        assert client.get("/openapi.json").status_code == 200
        response = client.get("/api/v1/models/status")
        assert response.status_code == 200
        assert response.json()["components"]["collaborative"]["status"] == "ready"
    assert _database_snapshot(postgres_session) == before_db
    assert _filesystem_snapshot(tmp_path) == before_files

    seed_database(postgres_session, load_seed_file())
    assert _database_snapshot(postgres_session) == before_db
    assert _filesystem_snapshot(tmp_path) == before_files

    config = Config("alembic.ini")
    with postgres_engine.connect() as connection:
        assert_connection_targets_guarded_database(connection, integration_settings)
        connection.rollback()
        config.attributes["connection"] = connection
        try:
            alembic_command.downgrade(config, "0010_stage_5_event_contract")
            alembic_command.upgrade(config, "head")
            alembic_command.upgrade(config, "head")
            alembic_command.check(config)
        finally:
            connection.rollback()
            alembic_command.upgrade(config, "head")
    assert _database_snapshot(postgres_session) == before_db
    assert _filesystem_snapshot(tmp_path) == before_files
