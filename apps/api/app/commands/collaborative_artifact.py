from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from gamelens_recommender.collaborative_artifacts import (
    CollaborativeArtifactError,
    CollaborativeBuildMetadata,
    build_collaborative_artifact,
    inspect_collaborative_artifact,
)
from gamelens_recommender.collaborative_training import fit_collaborative_neighborhoods
from gamelens_recommender.interaction_snapshot import (
    SnapshotAuditError,
    audit_fixture,
    canonical_json_bytes,
    load_fixture,
    profile_fingerprint,
)

from app.commands.collaborative_snapshot import catalog_from_seed
from app.commands.output import fail_command, write_json
from app.core.config import Settings, get_settings
from app.db.seed import DEFAULT_SEED_PATH
from app.db.session import create_database_engine, create_session_factory
from app.repositories.collaborative_registry import CollaborativeRegistryMutationError
from app.services.collaborative_build import (
    CollaborativeLiveBuildError,
    CollaborativeLiveBuildService,
)

DEFAULT_FIXTURE_VALIDITY_DAYS = 30


class CollaborativeArtifactCommandError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _fixture_allowed(settings: Settings) -> bool:
    return settings.environment == "test" and settings.collaborative_allow_test_fixture


def _fixture_build_id(
    *,
    fixture_id: str,
    fixture_contract_fingerprint: str,
    catalog_fingerprint: str,
    interaction_fingerprint: str,
) -> str:
    payload = {
        "catalog_fingerprint": catalog_fingerprint,
        "fixture_contract_fingerprint": fixture_contract_fingerprint,
        "fixture_id": fixture_id,
        "interaction_fingerprint": interaction_fingerprint,
    }
    return f"stage5-fixture-{hashlib.sha256(canonical_json_bytes(payload)).hexdigest()}"


def build_fixture_artifact(
    settings: Settings,
    output: Path,
    *,
    fixture_path: Path,
    catalog_path: Path,
    built_at: datetime | None = None,
) -> dict[str, object]:
    if not _fixture_allowed(settings):
        raise CollaborativeArtifactCommandError(
            "fixture_not_allowed",
            "Collaborative fixture builds require ENVIRONMENT=test and explicit fixture access",
        )
    timestamp = built_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise CollaborativeArtifactCommandError(
            "build_metadata_invalid", "Artifact build time must be timezone-aware"
        )
    timestamp = timestamp.astimezone(UTC)
    catalog = catalog_from_seed(catalog_path)
    catalog_slugs = frozenset(item.slug for item in catalog.items)
    report = audit_fixture(
        fixture_path,
        catalog_slugs=catalog_slugs,
        catalog_fingerprint=catalog.fingerprint,
    )
    if report.get("ready_for_functional_build") is not True:
        raise CollaborativeArtifactCommandError(
            "insufficient_data", "Fixture does not pass the functional build thresholds"
        )
    fixture = load_fixture(fixture_path, catalog_slugs=catalog_slugs)
    interaction_fingerprint = str(report["interaction_fingerprint"])
    report_fixture = report.get("fixture")
    if (
        profile_fingerprint(fixture.profiles) != interaction_fingerprint
        or not isinstance(report_fixture, dict)
        or report_fixture.get("contract_fingerprint") != fixture.contract_fingerprint
    ):
        raise CollaborativeArtifactCommandError(
            "fixture_changed", "Fixture changed between audit and build preparation"
        )
    neighborhoods = fit_collaborative_neighborhoods(
        fixture.profiles,
        catalog_slugs=catalog_slugs,
    )
    metadata = CollaborativeBuildMetadata(
        source_kind="fixture",
        catalog_fingerprint=catalog.fingerprint,
        interaction_fingerprint=interaction_fingerprint,
        build_id=_fixture_build_id(
            fixture_id=fixture.fixture_id,
            fixture_contract_fingerprint=fixture.contract_fingerprint,
            catalog_fingerprint=catalog.fingerprint,
            interaction_fingerprint=interaction_fingerprint,
        ),
        built_at=timestamp,
        fixture_id=fixture.fixture_id,
        valid_until=timestamp + timedelta(days=DEFAULT_FIXTURE_VALIDITY_DAYS),
    )
    built = build_collaborative_artifact(
        neighborhoods,
        output,
        metadata=metadata,
        allow_fixture=True,
    )
    return inspect_collaborative_artifact(
        built,
        allow_fixture=True,
        expected_catalog_fingerprint=catalog.fingerprint,
        now=timestamp,
    )


def build_live_artifact(
    settings: Settings,
    output: Path,
    *,
    build_id: str | None,
    confirmation: str | None,
) -> dict[str, object]:
    if not settings.collaborative_live_promotion_enabled:
        raise CollaborativeArtifactCommandError(
            "unapproved_live_source",
            "Live collaborative promotion is disabled by default",
        )
    if build_id is None:
        raise CollaborativeArtifactCommandError(
            "build_id_required",
            "Live collaborative builds require an explicit build ID",
        )
    if confirmation != build_id:
        raise CollaborativeArtifactCommandError(
            "live_build_confirmation_required",
            "Live collaborative promotion requires --confirm-live-build to match --build-id",
        )
    engine = create_database_engine(settings.database_url)
    try:
        return CollaborativeLiveBuildService(create_session_factory(engine)).build(
            output,
            settings=settings,
            build_id=build_id,
        )
    finally:
        engine.dispose()


def _artifact_path(
    settings: Settings,
    explicit: Path | None,
) -> Path:
    value = explicit or settings.collaborative_artifact_path
    if value is None:
        raise CollaborativeArtifactCommandError(
            "artifact_path_required",
            "Configure COLLABORATIVE_ARTIFACT_PATH or pass an explicit artifact path",
        )
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build, validate, or inspect Stage 5 collaborative artifacts"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    build_parser = commands.add_parser("build", help="Build a new immutable bundle")
    build_parser.add_argument("--source", choices=("live", "fixture"), default="live")
    build_parser.add_argument("--output", type=Path)
    build_parser.add_argument("--fixture", type=Path)
    build_parser.add_argument("--catalog", type=Path, default=DEFAULT_SEED_PATH)
    build_parser.add_argument("--build-id")
    build_parser.add_argument("--confirm-live-build")

    validate_parser = commands.add_parser("validate", help="Validate without mutation")
    validate_parser.add_argument("--artifact", type=Path)
    validate_parser.add_argument("--catalog", type=Path, default=DEFAULT_SEED_PATH)
    inspect_parser = commands.add_parser("inspect", help="Inspect aggregate metadata")
    inspect_parser.add_argument("--artifact", type=Path)
    inspect_parser.add_argument("--catalog", type=Path, default=DEFAULT_SEED_PATH)

    args = parser.parse_args()
    try:
        settings = get_settings()
        explicit_path = (
            getattr(args, "output", None)
            if args.command == "build"
            else getattr(args, "artifact", None)
        )
        artifact_path = _artifact_path(settings, explicit_path)
        allow_fixture = _fixture_allowed(settings)
        if args.command == "build":
            if args.source == "fixture":
                result = build_fixture_artifact(
                    settings,
                    artifact_path,
                    fixture_path=args.fixture or settings.collaborative_fixture_path,
                    catalog_path=args.catalog,
                )
            else:
                result = build_live_artifact(
                    settings,
                    artifact_path,
                    build_id=args.build_id,
                    confirmation=args.confirm_live_build,
                )
        else:
            catalog = catalog_from_seed(args.catalog)
            result = inspect_collaborative_artifact(
                artifact_path,
                allow_fixture=allow_fixture,
                expected_catalog_fingerprint=catalog.fingerprint,
            )
    except (
        CollaborativeArtifactCommandError,
        CollaborativeArtifactError,
        CollaborativeLiveBuildError,
        CollaborativeRegistryMutationError,
        SnapshotAuditError,
        OSError,
        ValueError,
    ) as error:
        fail_command(error, fallback_code="collaborative_artifact_failed")
    write_json(result)


if __name__ == "__main__":
    main()
