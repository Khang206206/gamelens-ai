import json
from datetime import UTC, datetime
from pathlib import Path

import gamelens_recommender
from gamelens_recommender import (
    ActiveGameFeedback,
    CatalogItem,
    CollaborativeBuildMetadata,
    CollaborativeComponentReady,
    CollaborativeScorer,
    FeedbackRanker,
    HybridRanker,
    HybridRecommendationsResult,
    Stage4FallbackResult,
    TaxonomyValue,
    UserContext,
    build_artifact,
    build_collaborative_artifact,
    canonical_snapshot,
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
FEEDBACK_AT = datetime(2026, 8, 24, tzinfo=UTC)


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


def _build_loaded_artifacts(tmp_path: Path):
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
        metadata=CollaborativeBuildMetadata(
            source_kind="fixture",
            catalog_fingerprint=content_artifact.data_fingerprint,
            interaction_fingerprint=interaction_fingerprint,
            build_id="stage5-phase4-handoff-v1",
            built_at=BUILT_AT,
            fixture_id="stage-5-collaborative-interactions-v1",
            valid_until=datetime(2099, 1, 1, tzinfo=UTC),
        ),
        allow_fixture=True,
    )
    collaborative_artifact = load_collaborative_artifact(
        collaborative_root,
        allow_fixture=True,
        expected_catalog_fingerprint=content_artifact.data_fingerprint,
        now=BUILT_AT,
    )
    return content_artifact, collaborative_artifact


def _artifact_bytes(content_artifact, collaborative_artifact):
    return (
        content_artifact.matrix.data.tobytes(),
        content_artifact.matrix.indices.tobytes(),
        content_artifact.matrix.indptr.tobytes(),
        content_artifact.popularity.tobytes(),
        collaborative_artifact.item_support.tobytes(),
        collaborative_artifact.neighbor_indices.tobytes(),
        collaborative_artifact.neighbor_indptr.tobytes(),
        collaborative_artifact.similarity_units.tobytes(),
        collaborative_artifact.pair_support.tobytes(),
    )


def _liked(slug: str) -> tuple[ActiveGameFeedback, ...]:
    return (
        ActiveGameFeedback(
            game_slug=slug,
            reaction="liked",
            reaction_occurred_at=FEEDBACK_AT,
        ),
    )


def _phase4_signature(result: HybridRecommendationsResult):
    return tuple(
        (
            item.slug,
            item.rank,
            item.candidate_origin,
            item.base_score_units,
            tuple(component.raw_units for component in item.base_components),
            item.affinity_score_units,
            item.collaborative_score_units,
            item.base_contribution_units,
            item.affinity_contribution_units,
            item.collaborative_contribution_units,
            item.pre_played_score_units,
            item.played_factor_units,
            item.played_delta_units,
            item.final_score_units,
        )
        for item in result.items
    )


def test_phase4_exports_public_policy_but_keeps_pipeline_stages_internal() -> None:
    assert {
        "CollaborativeComponentOutcome",
        "CollaborativeComponentReady",
        "CollaborativeComponentUnavailable",
        "HybridPolicyConfig",
        "HybridPolicyIdentity",
        "HybridRanker",
        "HybridRankingResult",
        "HybridRecommendation",
        "HybridRecommendationsResult",
        "Stage4FallbackResult",
    } <= set(gamelens_recommender.__all__)
    assert {
        "HybridCandidateComponents",
        "HybridCandidateRanking",
        "HybridCandidateUnion",
        "RankedHybridCandidate",
        "materialize_hybrid_candidate_union",
        "materialize_hybrid_recommendations",
        "rank_hybrid_candidate_union",
    }.isdisjoint(gamelens_recommender.__all__)


def test_phase2_fixture_runs_through_public_phase4_hybrid_policy(tmp_path: Path) -> None:
    content_artifact, collaborative_artifact = _build_loaded_artifacts(tmp_path)
    feedback_ranker = FeedbackRanker(content_artifact)
    collaborative_scorer = CollaborativeScorer(collaborative_artifact)
    hybrid_ranker = HybridRanker(feedback_ranker)
    context = UserContext(
        preferred_genres=("strategy",),
        preferred_platforms=("windows",),
        top_k=20,
    )
    feedback = _liked("emberfall-tactics")
    prepared = feedback_ranker.prepare_ranking_context(context, feedback)
    collaborative_result = collaborative_scorer.score(prepared.collaborative_query_context)
    artifact_bytes_before = _artifact_bytes(content_artifact, collaborative_artifact)
    baseline = feedback_ranker.rank(context, feedback)

    first = hybrid_ranker.rank(
        context,
        feedback,
        CollaborativeComponentReady(collaborative_result),
    )
    second = hybrid_ranker.rank(
        context,
        feedback,
        CollaborativeComponentReady(collaborative_result),
    )

    assert type(first) is HybridRecommendationsResult
    assert first == second
    assert first.mode == "hybrid"
    assert collaborative_result.reason == "recommendations"
    assert collaborative_result.diagnostics.returned_candidate_count == 4
    assert "emberfall-tactics" not in {item.slug for item in first.items}
    assert "starbound-couriers" not in {item.slug for item in baseline.items}
    by_slug = {item.slug: item for item in first.items}
    collaborative_only = by_slug["starbound-couriers"]
    assert collaborative_only.candidate_origin == "collaborative"
    assert tuple(component.raw_units for component in collaborative_only.base_components) == (
        0,
        1_000_000,
        599_117,
    )
    assert (
        collaborative_only.base_score_units,
        collaborative_only.affinity_score_units,
        collaborative_only.collaborative_score_units,
        collaborative_only.base_contribution_units,
        collaborative_only.affinity_contribution_units,
        collaborative_only.collaborative_contribution_units,
        collaborative_only.pre_played_score_units,
        collaborative_only.final_score_units,
    ) == (159_912, 0, 428_571, 127_930, 0, 42_857, 170_787, 170_787)
    assert tuple(edge.source_slug for edge in collaborative_only.collaborative_source_edges) == (
        "emberfall-tactics",
    )
    assert tuple(value.slug for value in collaborative_only.base_evidence.preferred_platforms) == (
        "windows",
    )
    assert collaborative_only.base_evidence.matching_genres == ()
    assert collaborative_only.base_evidence.matching_tags == ()
    assert collaborative_only.base_evidence.similar_selected_games == ()
    assert artifact_bytes_before == _artifact_bytes(content_artifact, collaborative_artifact)
    assert not any(
        marker in repr((collaborative_result, first))
        for marker in ("synthetic-01", "profile_key", "user_id", "anonymous_key")
    )


def test_loaded_fixture_cold_source_returns_exact_stage4_fallback(tmp_path: Path) -> None:
    content_artifact, collaborative_artifact = _build_loaded_artifacts(tmp_path)
    feedback_ranker = FeedbackRanker(content_artifact)
    collaborative_scorer = CollaborativeScorer(collaborative_artifact)
    hybrid_ranker = HybridRanker(feedback_ranker)
    context = UserContext(preferred_genres=("strategy",), top_k=5)
    unsupported_slug = next(
        slug
        for slug in sorted(content_artifact.slug_to_row)
        if slug not in collaborative_artifact.slug_to_index
    )
    feedback = _liked(unsupported_slug)
    prepared = feedback_ranker.prepare_ranking_context(context, feedback)
    collaborative_result = collaborative_scorer.score(prepared.collaborative_query_context)
    expected = feedback_ranker.rank(context, feedback)
    artifact_bytes_before = _artifact_bytes(content_artifact, collaborative_artifact)

    result = hybrid_ranker.rank(
        context,
        feedback,
        CollaborativeComponentReady(collaborative_result),
    )

    assert collaborative_result.reason == "no_supported_sources"
    assert type(result) is Stage4FallbackResult
    assert result.mode == "stage_4_fallback"
    assert result.fallback_reason == "no_supported_sources"
    assert result.stage_4_result == expected
    assert artifact_bytes_before == _artifact_bytes(content_artifact, collaborative_artifact)


def test_phase4_fixture_trace_is_a_frozen_functional_diagnostic(tmp_path: Path) -> None:
    """Freeze behavior only; this fixture is not recommendation-quality evidence."""

    content_artifact, collaborative_artifact = _build_loaded_artifacts(tmp_path)
    feedback_ranker = FeedbackRanker(content_artifact)
    context = UserContext(
        preferred_genres=("strategy",),
        preferred_platforms=("windows",),
        top_k=20,
    )
    feedback = _liked("emberfall-tactics")
    prepared = feedback_ranker.prepare_ranking_context(context, feedback)
    collaborative_result = CollaborativeScorer(collaborative_artifact).score(
        prepared.collaborative_query_context
    )
    result = HybridRanker(feedback_ranker).rank(
        context,
        feedback,
        CollaborativeComponentReady(collaborative_result),
    )

    assert _phase4_signature(result) == (
        (
            "warden-of-glass",
            1,
            "content",
            304_504,
            (164_937, 1_000_000, 725_539),
            311_593,
            0,
            243_603,
            31_159,
            0,
            274_762,
            1_000_000,
            0,
            274_762,
        ),
        (
            "paper-kingdoms",
            2,
            "content",
            301_576,
            (160_315, 1_000_000, 733_240),
            161_703,
            0,
            241_261,
            16_170,
            0,
            257_431,
            1_000_000,
            0,
            257_431,
        ),
        (
            "frontier-foundry",
            3,
            "content",
            314_452,
            (173_884, 1_000_000, 753_454),
            47_368,
            0,
            251_562,
            4_737,
            0,
            256_299,
            1_000_000,
            0,
            256_299,
        ),
        (
            "frostline-caravan",
            4,
            "content",
            299_820,
            (164_451, 1_000_000, 682_589),
            116_234,
            0,
            239_856,
            11_623,
            0,
            251_479,
            1_000_000,
            0,
            251_479,
        ),
        (
            "null-protocol",
            5,
            "content",
            305_852,
            (155_451, 1_000_000, 814_912),
            49_553,
            0,
            244_682,
            4_955,
            0,
            249_637,
            1_000_000,
            0,
            249_637,
        ),
        (
            "harborlight",
            6,
            "content",
            286_872,
            (182_485, 1_000_000, 408_836),
            58_170,
            0,
            229_498,
            5_817,
            0,
            235_315,
            1_000_000,
            0,
            235_315,
        ),
        (
            "tin-star-sheriff",
            7,
            "content",
            265_626,
            (154_211, 1_000_000, 422_569),
            191_465,
            0,
            212_501,
            19_147,
            0,
            231_648,
            1_000_000,
            0,
            231_648,
        ),
        (
            "verdant-vale",
            8,
            "collaborative",
            196_637,
            (0, 1_000_000, 966_366),
            0,
            428_571,
            157_310,
            0,
            42_857,
            200_167,
            1_000_000,
            0,
            200_167,
        ),
        (
            "neon-drift-circuit",
            9,
            "collaborative",
            155_118,
            (0, 1_000_000, 551_178),
            7_170,
            571_429,
            124_094,
            717,
            57_143,
            181_954,
            1_000_000,
            0,
            181_954,
        ),
        (
            "starbound-couriers",
            10,
            "collaborative",
            159_912,
            (0, 1_000_000, 599_117),
            0,
            428_571,
            127_930,
            0,
            42_857,
            170_787,
            1_000_000,
            0,
            170_787,
        ),
        (
            "clockwork-orchard",
            11,
            "collaborative",
            129_531,
            (0, 1_000_000, 295_311),
            0,
            462_910,
            103_625,
            0,
            46_291,
            149_916,
            1_000_000,
            0,
            149_916,
        ),
    )
