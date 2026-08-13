import argparse
import json
from pathlib import Path

from gamelens_recommender import CatalogSnapshot, build_artifact
from gamelens_recommender.training import inspect_artifact

from app.core.config import get_settings
from app.db.session import begin_repeatable_read, create_database_engine, create_session_factory
from app.repositories.recommendation_catalog import (
    RecommendationCatalogRepository,
    RecommendationCatalogSnapshot,
)


def _buildable_snapshot(catalog: RecommendationCatalogSnapshot) -> CatalogSnapshot:
    if catalog.model_snapshot is not None:
        return catalog.model_snapshot
    if catalog.model_unavailable_reason == "catalog_invalid":
        raise ValueError("Cannot build a recommendation artifact from an invalid catalog")
    raise ValueError("Cannot build a recommendation artifact from an empty catalog")


def build(output: Path) -> dict[str, object]:
    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    try:
        session_factory = create_session_factory(engine)
        with session_factory() as session:
            begin_repeatable_read(session, read_only=True)
            snapshot = _buildable_snapshot(RecommendationCatalogRepository(session).load())
            path = build_artifact(snapshot, output)
        return inspect_artifact(path)
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or validate recommendation artifacts")
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build", help="Build from the configured database")
    build_parser.add_argument("--output", type=Path)
    validate_parser = commands.add_parser("validate", help="Validate without database access")
    validate_parser.add_argument("--artifact", type=Path)
    args = parser.parse_args()
    configured_path = get_settings().model_artifact_path
    artifact_path = (
        getattr(args, "output", None)
        if args.command == "build"
        else getattr(args, "artifact", None)
    )
    if artifact_path is None:
        artifact_path = configured_path
    if artifact_path is None:
        parser.error("configure MODEL_ARTIFACT_PATH or pass an explicit artifact path")
    result = build(artifact_path) if args.command == "build" else inspect_artifact(artifact_path)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
