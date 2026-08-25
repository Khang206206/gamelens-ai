import json
from datetime import UTC, datetime
from pathlib import Path

from gamelens_recommender.collaborative_artifacts import (
    CollaborativeBuildMetadata,
    build_collaborative_artifact,
    inspect_collaborative_artifact,
    load_collaborative_artifact,
)
from gamelens_recommender.collaborative_training import fit_collaborative_neighborhoods
from gamelens_recommender.interaction_snapshot import load_fixture, profile_fingerprint

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPOSITORY_ROOT / "data" / "catalog" / "games.json"
FIXTURE_PATH = (
    REPOSITORY_ROOT / "data" / "fixtures" / "interactions" / "collaborative-interactions.json"
)


def _catalog_slugs() -> frozenset[str]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return frozenset(game["slug"] for game in payload["games"])


def _metadata(interaction_fingerprint: str) -> CollaborativeBuildMetadata:
    built_at = datetime(2026, 8, 25, 0, 0, tzinfo=UTC)
    return CollaborativeBuildMetadata(
        source_kind="fixture",
        catalog_fingerprint="a" * 64,
        interaction_fingerprint=interaction_fingerprint,
        build_id="stage5-fixture-functional-pipeline-v1",
        built_at=built_at,
        fixture_id="stage-5-collaborative-interactions-v1",
        valid_until=datetime(2099, 1, 1, tzinfo=UTC),
    )


def test_fixture_pipeline_is_deterministic_identity_free_and_immutable(tmp_path: Path) -> None:
    catalog_slugs = _catalog_slugs()
    fixture = load_fixture(FIXTURE_PATH, catalog_slugs=catalog_slugs)
    fingerprint = profile_fingerprint(fixture.profiles)
    first_neighborhoods = fit_collaborative_neighborhoods(
        fixture.profiles,
        catalog_slugs=catalog_slugs,
    )
    reordered_neighborhoods = fit_collaborative_neighborhoods(
        tuple(tuple(reversed(profile)) for profile in reversed(fixture.profiles)),
        catalog_slugs=catalog_slugs,
    )

    first_root = build_collaborative_artifact(
        first_neighborhoods,
        tmp_path / "first",
        metadata=_metadata(fingerprint),
        allow_fixture=True,
    )
    second_root = build_collaborative_artifact(
        reordered_neighborhoods,
        tmp_path / "second",
        metadata=_metadata(fingerprint),
        allow_fixture=True,
    )

    first_members = {
        path.name: path.read_bytes() for path in first_root.iterdir() if path.is_file()
    }
    second_members = {
        path.name: path.read_bytes() for path in second_root.iterdir() if path.is_file()
    }
    assert first_members == second_members
    assert not any(
        marker in payload
        for payload in first_members.values()
        for marker in (b"synthetic-01", b"profile_key", b"user_id", b"anonymous_key")
    )

    loaded = load_collaborative_artifact(
        first_root,
        allow_fixture=True,
        expected_catalog_fingerprint="a" * 64,
        now=_metadata(fingerprint).built_at,
    )
    assert len(loaded.item_slugs) == 6
    assert loaded.neighbor_indices.size == first_neighborhoods.neighbor_indices.size
    assert loaded.slug_to_index == {slug: index for index, slug in enumerate(loaded.item_slugs)}

    report = inspect_collaborative_artifact(
        first_root,
        allow_fixture=True,
        expected_catalog_fingerprint="a" * 64,
        now=_metadata(fingerprint).built_at,
    )
    assert report["status"] == "valid"
    assert report["source"]["kind"] == "fixture"
    assert report["matrix"]["retained_contributors"] == 12
    assert "item_slugs" not in report
