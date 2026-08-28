import json
from datetime import UTC, datetime
from pathlib import Path

import gamelens_recommender
from gamelens_recommender import (
    COLLABORATIVE_SCORING_CONFIG,
    AffinityCandidateScore,
    AffinityMaterializationError,
    AffinityMaterializationResult,
    BaseCandidateMaterializationError,
    CatalogItem,
    CollaborativeBuildMetadata,
    CollaborativeCandidateScore,
    CollaborativeQueryContext,
    CollaborativeQuerySource,
    CollaborativeScorer,
    CollaborativeScoringConfig,
    CollaborativeScoringDiagnostics,
    CollaborativeScoringError,
    CollaborativeScoringIdentity,
    CollaborativeScoringResult,
    CollaborativeSourceEdge,
    CollaborativeSourceState,
    ContentRanker,
    FeedbackRanker,
    PositiveFeedbackSource,
    TaxonomyValue,
    UserContext,
    build_artifact,
    build_collaborative_artifact,
    canonical_snapshot,
    canonicalize_collaborative_query_sources,
    fit_collaborative_neighborhoods,
    load_artifact,
    load_collaborative_artifact,
    profile_fingerprint,
)
from gamelens_recommender.interaction_snapshot import load_fixture

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPOSITORY_ROOT / "data" / "catalog" / "games.json"
FIXTURE_PATH = (
    REPOSITORY_ROOT / "data" / "fixtures" / "interactions" / "collaborative-interactions.json"
)
BUILT_AT = datetime(2026, 8, 25, tzinfo=UTC)


def _content_snapshot():
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    taxonomies = {
        family: {
            value["slug"]: TaxonomyValue(slug=value["slug"], name=value["name"]) for value in values
        }
        for family, values in payload["taxonomies"].items()
    }

    def taxonomy_values(family: str, slugs: list[str]) -> tuple[TaxonomyValue, ...]:
        return tuple(taxonomies[family][slug] for slug in slugs)

    return canonical_snapshot(
        CatalogItem(
            slug=game["slug"],
            title=game["title"],
            description=game["description"],
            developer=game["developer"],
            publisher=game["publisher"],
            average_rating=game["average_rating"],
            rating_count=game["rating_count"],
            popularity_score=game["popularity_score"],
            genres=taxonomy_values("genres", game["genre_slugs"]),
            tags=taxonomy_values("tags", game["tag_slugs"]),
            platforms=taxonomy_values("platforms", game["platform_slugs"]),
        )
        for game in payload["games"]
    )


def _collaborative_metadata(
    *, catalog_fingerprint: str, interaction_fingerprint: str
) -> CollaborativeBuildMetadata:
    return CollaborativeBuildMetadata(
        source_kind="fixture",
        catalog_fingerprint=catalog_fingerprint,
        interaction_fingerprint=interaction_fingerprint,
        build_id="stage5-phase3-handoff-v1",
        built_at=BUILT_AT,
        fixture_id="stage-5-collaborative-interactions-v1",
        valid_until=datetime(2099, 1, 1, tzinfo=UTC),
    )


def test_phase3_exports_only_stable_handoff_contracts() -> None:
    stable_exports = {
        AffinityCandidateScore,
        AffinityMaterializationError,
        AffinityMaterializationResult,
        BaseCandidateMaterializationError,
        CollaborativeCandidateScore,
        CollaborativeQueryContext,
        CollaborativeQuerySource,
        CollaborativeScorer,
        CollaborativeScoringConfig,
        CollaborativeScoringDiagnostics,
        CollaborativeScoringError,
        CollaborativeScoringIdentity,
        CollaborativeScoringResult,
        CollaborativeSourceEdge,
        CollaborativeSourceState,
        canonicalize_collaborative_query_sources,
    }
    assert {value.__name__ for value in stable_exports} <= set(gamelens_recommender.__all__)
    assert gamelens_recommender.COLLABORATIVE_SCORING_CONFIG is COLLABORATIVE_SCORING_CONFIG
    assert {
        "CollaborativeNeighborhoodEdge",
        "CollaborativeNeighborhoodLookupDiagnostics",
        "CollaborativeNeighborhoodLookupResult",
        "CollaborativeSourceNeighborhood",
        "lookup_collaborative_neighborhoods",
    }.isdisjoint(gamelens_recommender.__all__)

    collaborative_source = (
        REPOSITORY_ROOT / "ml" / "src" / "gamelens_recommender" / "collaborative.py"
    ).read_text(encoding="utf-8")
    assert "gamelens_recommender.ranking" not in collaborative_source
    assert "gamelens_recommender.feedback" not in collaborative_source


def test_phase2_fixture_reaches_phase4_exact_row_handoff(tmp_path: Path) -> None:
    snapshot = _content_snapshot()
    content_root = build_artifact(snapshot, tmp_path / "content", built_at=BUILT_AT)
    content_artifact = load_artifact(content_root)
    catalog_slugs = frozenset(content_artifact.slug_to_row)

    fixture = load_fixture(FIXTURE_PATH, catalog_slugs=catalog_slugs)
    interaction_fingerprint = profile_fingerprint(fixture.profiles)
    neighborhoods = fit_collaborative_neighborhoods(
        fixture.profiles,
        catalog_slugs=catalog_slugs,
    )
    collaborative_root = build_collaborative_artifact(
        neighborhoods,
        tmp_path / "collaborative",
        metadata=_collaborative_metadata(
            catalog_fingerprint=content_artifact.data_fingerprint,
            interaction_fingerprint=interaction_fingerprint,
        ),
        allow_fixture=True,
    )
    collaborative_artifact = load_collaborative_artifact(
        collaborative_root,
        allow_fixture=True,
        expected_catalog_fingerprint=content_artifact.data_fingerprint,
        now=BUILT_AT,
    )
    assert collaborative_artifact.catalog_fingerprint == content_artifact.data_fingerprint

    positive_sources = (
        PositiveFeedbackSource(
            game_slug="emberfall-tactics",
            kind="liked",
            occurred_at=datetime(2026, 8, 24, tzinfo=UTC),
        ),
    )
    query_context = canonicalize_collaborative_query_sources(
        CollaborativeSourceState(positive_sources=positive_sources)
    )
    assert query_context.sources == (
        CollaborativeQuerySource(game_slug="emberfall-tactics", kind="liked"),
    )

    source_index = collaborative_artifact.slug_to_index["emberfall-tactics"]
    start = int(collaborative_artifact.neighbor_indptr[source_index])
    stop = int(collaborative_artifact.neighbor_indptr[source_index + 1])
    assert (source_index, start, stop) == (1, 4, 8)
    assert tuple(collaborative_artifact.neighbor_indices[start:stop]) == (0, 2, 4, 5)
    assert tuple(collaborative_artifact.similarity_units[start:stop]) == (
        462_910,
        571_429,
        428_571,
        428_571,
    )
    assert tuple(collaborative_artifact.pair_support[start:stop]) == (3, 4, 3, 3)

    collaborative_arrays_before = tuple(
        value.tobytes()
        for value in (
            collaborative_artifact.item_support,
            collaborative_artifact.neighbor_indices,
            collaborative_artifact.neighbor_indptr,
            collaborative_artifact.similarity_units,
            collaborative_artifact.pair_support,
        )
    )
    content_arrays_before = (
        content_artifact.matrix.data.tobytes(),
        content_artifact.matrix.indices.tobytes(),
        content_artifact.matrix.indptr.tobytes(),
        content_artifact.popularity.tobytes(),
    )

    collaborative_result = CollaborativeScorer(collaborative_artifact).score(query_context)
    assert collaborative_result.reason == "recommendations"
    assert (
        collaborative_result.diagnostics.query_source_count,
        collaborative_result.diagnostics.supported_source_count,
        collaborative_result.diagnostics.visited_edge_count,
        collaborative_result.diagnostics.candidate_count_before_exclusions,
        collaborative_result.diagnostics.returned_candidate_count,
    ) == (1, 1, 4, 4, 4)
    assert tuple(
        (
            candidate.slug,
            candidate.collaborative_score_units,
            candidate.item_support,
            tuple(
                (edge.source_slug, edge.similarity_units, edge.pair_support)
                for edge in candidate.source_edges
            ),
        )
        for candidate in collaborative_result.candidates
    ) == (
        ("neon-drift-circuit", 571_429, 7, (("emberfall-tactics", 571_429, 4),)),
        ("clockwork-orchard", 462_910, 6, (("emberfall-tactics", 462_910, 3),)),
        ("starbound-couriers", 428_571, 7, (("emberfall-tactics", 428_571, 3),)),
        ("verdant-vale", 428_571, 7, (("emberfall-tactics", 428_571, 3),)),
    )

    candidate_slugs = tuple(candidate.slug for candidate in collaborative_result.candidates)
    content_context = UserContext(
        preferred_genres=("strategy",),
        preferred_platforms=("windows",),
    )
    content_ranker = ContentRanker(content_artifact)
    assert "starbound-couriers" not in {
        candidate.slug for candidate in content_ranker.score_candidates(content_context)
    }
    base_candidates = content_ranker.materialize_base_candidates(
        content_context,
        candidate_slugs,
    )
    affinity_result = FeedbackRanker(
        content_artifact,
        content_ranker=content_ranker,
    ).materialize_affinity_candidates(positive_sources, candidate_slugs)
    assert affinity_result.profile_active is True
    assert tuple(candidate.slug for candidate in base_candidates) == tuple(sorted(candidate_slugs))
    assert tuple(candidate.slug for candidate in affinity_result.candidates) == tuple(
        sorted(candidate_slugs)
    )

    base_by_slug = {candidate.slug: candidate for candidate in base_candidates}
    affinity_by_slug = {candidate.slug: candidate for candidate in affinity_result.candidates}
    collaborative_by_slug = {
        candidate.slug: candidate for candidate in collaborative_result.candidates
    }
    collaborative_only = collaborative_by_slug["starbound-couriers"]
    base = base_by_slug["starbound-couriers"]
    affinity = affinity_by_slug["starbound-couriers"]
    assert (
        collaborative_only.collaborative_score_units,
        base.content_score_units,
        base.platform_score_units,
        base.popularity_score_units,
        base.base_score_units,
        affinity.affinity_score_units,
    ) == (428_571, 0, 1_000_000, 599_117, 159_912, 0)

    base_view = content_ranker.materialize_candidate(base, content_context, rank=1)
    assert base_view.evidence.matching_genres == ()
    assert base_view.evidence.matching_tags == ()
    assert base_view.evidence.similar_selected_games == ()
    assert tuple(value.slug for value in base_view.evidence.preferred_platforms) == ("windows",)

    phase3_values = repr((query_context, collaborative_result, base_candidates, affinity_result))
    assert not any(
        marker in phase3_values
        for marker in ("synthetic-01", "profile_key", "user_id", "anonymous_key")
    )
    assert not any(
        hasattr(collaborative_only, field)
        for field in (
            "origin",
            "weight_units",
            "played",
            "rank",
            "final_score_units",
            "fallback",
        )
    )
    assert collaborative_arrays_before == tuple(
        value.tobytes()
        for value in (
            collaborative_artifact.item_support,
            collaborative_artifact.neighbor_indices,
            collaborative_artifact.neighbor_indptr,
            collaborative_artifact.similarity_units,
            collaborative_artifact.pair_support,
        )
    )
    assert content_arrays_before == (
        content_artifact.matrix.data.tobytes(),
        content_artifact.matrix.indices.tobytes(),
        content_artifact.matrix.indptr.tobytes(),
        content_artifact.popularity.tobytes(),
    )
