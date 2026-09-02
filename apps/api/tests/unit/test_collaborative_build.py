from pathlib import Path
from typing import NoReturn

import pytest
from app.core.config import Settings
from app.services.collaborative_build import (
    CollaborativeLiveBuildError,
    CollaborativeLiveBuildService,
)


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
