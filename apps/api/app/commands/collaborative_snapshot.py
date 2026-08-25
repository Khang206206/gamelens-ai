from __future__ import annotations

import argparse
import json
from pathlib import Path

from gamelens_recommender import (
    CatalogItem,
    CatalogSnapshot,
    TaxonomyValue,
    audit_fixture,
    canonical_snapshot,
)
from gamelens_recommender.interaction_snapshot import SnapshotAuditError

from app.core.config import Settings, get_settings
from app.db.seed import DEFAULT_SEED_PATH, load_seed_file
from app.db.session import create_database_engine, create_session_factory
from app.repositories.collaborative_snapshot import CollaborativeSnapshotError
from app.services.collaborative_snapshot import audit_live_snapshot, blocked_live_audit


def catalog_from_seed(path: Path) -> CatalogSnapshot:
    seed = load_seed_file(path)
    taxonomies = {
        family: {value.slug: TaxonomyValue(slug=value.slug, name=value.name) for value in values}
        for family, values in (
            ("genres", seed.taxonomies.genres),
            ("tags", seed.taxonomies.tags),
            ("platforms", seed.taxonomies.platforms),
        )
    }
    items = (
        CatalogItem(
            slug=game.slug,
            title=game.title,
            description=game.description,
            developer=game.developer,
            publisher=game.publisher,
            average_rating=(None if game.average_rating is None else float(game.average_rating)),
            rating_count=game.rating_count,
            popularity_score=float(game.popularity_score),
            genres=tuple(taxonomies["genres"][slug] for slug in game.genre_slugs),
            tags=tuple(taxonomies["tags"][slug] for slug in game.tag_slugs),
            platforms=tuple(taxonomies["platforms"][slug] for slug in game.platform_slugs),
        )
        for game in seed.games
    )
    return canonical_snapshot(items)


def audit_fixture_source(
    settings: Settings,
    *,
    fixture_path: Path,
    catalog_path: Path,
) -> dict[str, object]:
    if settings.environment != "test" or not settings.collaborative_allow_test_fixture:
        raise SnapshotAuditError(
            "fixture_not_allowed",
            "The collaborative fixture requires ENVIRONMENT=test and explicit fixture access",
        )
    catalog = catalog_from_seed(catalog_path)
    return audit_fixture(
        fixture_path,
        catalog_slugs=frozenset(item.slug for item in catalog.items),
        catalog_fingerprint=catalog.fingerprint,
    )


def audit_live_source(settings: Settings) -> dict[str, object]:
    if (
        not settings.collaborative_live_data_enabled
        or settings.collaborative_contribution_consent_version is None
    ):
        return blocked_live_audit(
            live_data_enabled=settings.collaborative_live_data_enabled,
            contribution_consent_version_configured=(
                settings.collaborative_contribution_consent_version is not None
            ),
        )
    engine = create_database_engine(settings.database_url)
    try:
        return audit_live_snapshot(create_session_factory(engine), settings=settings)
    finally:
        engine.dispose()


def _summary(report: dict[str, object]) -> str:
    reasons = report.get("reasons", [])
    reason_text = ",".join(str(reason) for reason in reasons) or "none"
    return (
        f"source={report.get('source_kind')} status={report.get('status')} "
        f"ready={str(report.get('ready_for_functional_build')).lower()} "
        f"approved_live={str(report.get('approved_live_training_eligibility')).lower()} "
        f"reasons={reason_text}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit Stage 5 interaction inputs without building an artifact"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    audit_parser = commands.add_parser("audit", help="Run a read-only aggregate audit")
    audit_parser.add_argument("--source", choices=("live", "fixture"), required=True)
    audit_parser.add_argument("--fixture", type=Path)
    audit_parser.add_argument("--catalog", type=Path, default=DEFAULT_SEED_PATH)
    audit_parser.add_argument("--format", choices=("json", "summary"), default="json")
    args = parser.parse_args()
    settings = get_settings()
    try:
        if args.source == "fixture":
            report = audit_fixture_source(
                settings,
                fixture_path=args.fixture or settings.collaborative_fixture_path,
                catalog_path=args.catalog,
            )
        else:
            report = audit_live_source(settings)
    except (CollaborativeSnapshotError, SnapshotAuditError, OSError, ValueError) as error:
        code = getattr(error, "code", "audit_failed")
        print(
            json.dumps(
                {"status": "error", "error": {"code": code, "message": str(error)}},
                sort_keys=True,
            )
        )
        raise SystemExit(2) from error
    print(
        json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else _summary(report)
    )


if __name__ == "__main__":
    main()
