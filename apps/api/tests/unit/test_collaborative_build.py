import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn
from unittest.mock import Mock

import pytest
from app.commands.collaborative_snapshot import catalog_from_seed
from app.core.config import Settings
from app.services import collaborative_build
from app.services.collaborative_build import (
    CollaborativeLiveBuildError,
    CollaborativeLiveBuildService,
)
from gamelens_recommender import fit_collaborative_neighborhoods, profile_fingerprint
from gamelens_recommender.interaction_snapshot import load_fixture
from sqlalchemy.exc import SQLAlchemyError

from tests.unit.test_collaborative_artifact_command import CATALOG_PATH, FIXTURE_PATH


def _settings(*, promotion_enabled: bool) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        cors_origins=["http://testserver"],
        collaborative_live_data_enabled=promotion_enabled,
        collaborative_contribution_consent_version=(
            "stage-5-contribution-v1" if promotion_enabled else None
        ),
        collaborative_live_promotion_enabled=promotion_enabled,
    )


def _unexpected_session() -> NoReturn:
    raise AssertionError("fail-closed validation must happen before database access")


def test_live_build_service_rechecks_default_off_gates_before_database_access(
    tmp_path: Path,
) -> None:
    service = CollaborativeLiveBuildService(_unexpected_session)

    with pytest.raises(CollaborativeLiveBuildError) as caught:
        service.build(
            tmp_path / "artifact",
            settings=_settings(promotion_enabled=False),
            build_id="stage5-live-v1",
        )

    assert caught.value.code == "unapproved_live_source"


def test_live_build_service_rejects_existing_target_before_database_access(
    tmp_path: Path,
) -> None:
    target = tmp_path / "artifact"
    target.mkdir()
    service = CollaborativeLiveBuildService(_unexpected_session)

    with pytest.raises(CollaborativeLiveBuildError) as caught:
        service.build(
            target,
            settings=_settings(promotion_enabled=True),
            build_id="stage5-live-v1",
        )

    assert caught.value.code == "artifact_target_exists"


def test_live_recovery_rechecks_default_off_gates_before_filesystem_or_database_access(
    tmp_path: Path,
) -> None:
    service = CollaborativeLiveBuildService(_unexpected_session)

    with pytest.raises(CollaborativeLiveBuildError) as caught:
        service.recover(
            tmp_path / "missing-artifact",
            settings=_settings(promotion_enabled=False),
            build_id="stage5-live-v1",
        )

    assert caught.value.code == "unapproved_live_source"


def test_live_recovery_requires_an_existing_non_symlink_directory_before_database_access(
    tmp_path: Path,
) -> None:
    service = CollaborativeLiveBuildService(_unexpected_session)

    with pytest.raises(CollaborativeLiveBuildError) as caught:
        service.recover(
            tmp_path / "missing-artifact",
            settings=_settings(promotion_enabled=True),
            build_id="stage5-live-v1",
        )

    assert caught.value.code == "recovery_target_invalid"


@pytest.mark.parametrize("failure", [None, "registration"])
def test_build_handoff_keeps_only_identity_free_bundle_on_registration_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    # Unit handoff only: no database extraction, transaction or real registration.
    catalog = catalog_from_seed(CATALOG_PATH)
    profiles = load_fixture(
        FIXTURE_PATH, catalog_slugs=frozenset(item.slug for item in catalog.items)
    ).profiles
    neighborhoods = fit_collaborative_neighborhoods(
        profiles, catalog_slugs=frozenset(slug for profile in profiles for slug in profile)
    )
    now = datetime.now(UTC)
    contributor_ids = tuple(range(900000001, 900000001 + neighborhoods.retained_contributors))
    prepared = SimpleNamespace(
        snapshot=SimpleNamespace(
            data_revision=7,
            catalog_fingerprint="a" * 64,
            cutoff=now,
        ),
        neighborhoods=neighborhoods,
        interaction_fingerprint=profile_fingerprint(profiles),
        retained_user_ids=contributor_ids,
        retained_authority_horizons=(now + timedelta(days=2),) * len(contributor_ids),
    )
    service = CollaborativeLiveBuildService(_unexpected_session)
    monkeypatch.setattr(service, "_preflight_registry", Mock())
    monkeypatch.setattr(service, "_prepare_live_build", Mock(return_value=prepared))
    monkeypatch.setattr(service, "_verified_build_time", Mock(return_value=now))
    monkeypatch.setattr(service, "_revision_check", Mock(return_value=True))
    register = Mock(
        side_effect=(
            CollaborativeLiveBuildError("live_promotion_rejected", "Registration rejected")
            if failure
            else None
        )
    )
    monkeypatch.setattr(service, "_register", register)
    target = tmp_path / "artifact"
    if failure:
        with pytest.raises(CollaborativeLiveBuildError) as caught:
            service.build(
                target, settings=_settings(promotion_enabled=True), build_id="unit-handoff"
            )
        assert caught.value.code == "live_promotion_rejected"
    else:
        report = service.build(
            target, settings=_settings(promotion_enabled=True), build_id="unit-handoff"
        )
        assert report["promotion"]["registered"] is True
        assert not any(str(identity) in json.dumps(report) for identity in contributor_ids)
    registration = register.call_args.args[0]
    assert registration.contributor_user_ids == contributor_ids
    assert register.call_count == 1
    assert list(tmp_path.iterdir()) == [target]
    assert {p.name for p in target.iterdir()} == {
        "manifest.json",
        "item-slugs.json",
        "item-support.npy",
        "neighbors-indices.npy",
        "neighbors-indptr.npy",
        "similarity-units.npy",
        "pair-support.npy",
    }
    payload = b"".join(p.read_bytes() for p in target.iterdir())
    assert not any(str(identity).encode() in payload for identity in contributor_ids)
    assert b"user_id" not in payload and b"profile_key" not in payload
    before = {p.name: p.read_bytes() for p in target.iterdir()}
    with pytest.raises(CollaborativeLiveBuildError) as occupied:
        service.build(target, settings=_settings(promotion_enabled=True), build_id="unit-handoff")
    assert occupied.value.code == "artifact_target_exists"
    assert register.call_count == 1
    assert {p.name: p.read_bytes() for p in target.iterdir()} == before


@pytest.mark.parametrize("stage", ["preflight", "revision", "registration", "commit"])
def test_database_handoff_failures_rollback_close_and_hide_private_details(
    monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    session = Mock()
    repository = Mock(spec=collaborative_build.CollaborativeArtifactRegistryRepository)
    error = SQLAlchemyError("private-identity-marker")
    monkeypatch.setattr(collaborative_build, "begin_read_committed", Mock())
    monkeypatch.setattr(
        collaborative_build, "CollaborativeArtifactRegistryRepository", lambda s: repository
    )
    service = CollaborativeLiveBuildService(lambda: session)
    if stage == "preflight":
        repository.assert_live_build_slot.side_effect = error
    elif stage == "revision":
        monkeypatch.setattr(collaborative_build, "verify_data_revision", Mock(side_effect=error))
    else:
        if stage == "registration":
            repository.register_live_build.side_effect = error
        else:
            session.commit.side_effect = error
    with pytest.raises(CollaborativeLiveBuildError) as caught:
        if stage == "preflight":
            service._preflight_registry("unit-handoff")
        elif stage == "revision":
            service._revision_check(7)
        else:
            service._register(Mock())
    assert caught.value.code == (
        "live_promotion_rejected"
        if stage in {"registration", "commit"}
        else "live_build_database_failed"
    )
    assert "private-identity-marker" not in str(caught.value)
    session.rollback.assert_called_once_with()
    session.close.assert_called_once_with()
    assert session.commit.call_count == (1 if stage == "commit" else 0)
