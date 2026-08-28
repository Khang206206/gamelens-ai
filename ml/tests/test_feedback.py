from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from gamelens_recommender import (
    ActiveGameFeedback,
    BaseCandidateScore,
    ContentRanker,
    FeedbackPolicyConfig,
    FeedbackRanker,
    InsufficientContextError,
    PositiveFeedbackSource,
    UserContext,
    build_artifact,
    canonical_snapshot,
    load_artifact,
)
from gamelens_recommender import feedback as feedback_module
from gamelens_recommender.feedback import (
    AffinityCandidateScore,
    AffinityMaterializationError,
    AffinityMaterializationResult,
)
from gamelens_recommender.ranking import contribution

NOW = datetime(2026, 8, 12, tzinfo=UTC)


def _at(days: int = 0) -> datetime:
    return NOW + timedelta(days=days)


def _ranker(snapshot, tmp_path) -> FeedbackRanker:
    return FeedbackRanker(load_artifact(build_artifact(snapshot, tmp_path / "model")))


def _reaction(
    slug: str,
    reaction: str,
    *,
    occurred_at: datetime = NOW,
    rating: Decimal | None = None,
    rating_occurred_at: datetime | None = None,
) -> ActiveGameFeedback:
    return ActiveGameFeedback(
        game_slug=slug,
        reaction=reaction,
        reaction_occurred_at=occurred_at,
        rating=rating,
        rating_occurred_at=rating_occurred_at,
    )


def test_no_feedback_preserves_exact_stage_3_order_scores_and_evidence(snapshot, tmp_path) -> None:
    artifact = load_artifact(build_artifact(snapshot, tmp_path / "model"))
    content_ranker = ContentRanker(artifact)
    feedback_ranker = FeedbackRanker(artifact, content_ranker=content_ranker)
    context = UserContext(
        selected_game_slugs=("alpha-tactics",),
        preferred_genres=("strategy",),
        preferred_platforms=("linux",),
        top_k=3,
    )

    base = content_ranker.rank(context)
    personalized = feedback_ranker.rank(context, ())

    assert personalized.policy.name == "gamelens-feedback-adjustment"
    assert personalized.policy.version == "1.0.0"
    assert personalized.positive_sources == ()
    assert [value.slug for value in personalized.items] == [value.slug for value in base.items]
    for expected, actual in zip(base.items, personalized.items, strict=True):
        assert actual.rank == expected.rank
        assert actual.base_score_units == expected.final_score_units
        assert actual.final_score_units == expected.final_score_units
        assert actual.base_components == expected.components
        assert actual.base_evidence == expected.evidence
        assert actual.explanation_summary == expected.explanation_summary
        assert actual.explanation_reasons == expected.explanation_reasons
        assert actual.base_weight_units == 1_000_000
        assert actual.base_contribution_units == expected.final_score_units
        assert actual.affinity_score_units == 0
        assert actual.affinity_weight_units == 0
        assert actual.affinity_contribution_units == 0
        assert actual.pre_played_score_units == expected.final_score_units
        assert actual.played_factor_units == 1_000_000
        assert actual.played_delta_units == 0
        assert actual.adjustment_reasons == ()


def test_dislike_and_positive_source_exclusions_refill_before_top_k(snapshot, tmp_path) -> None:
    ranker = _ranker(snapshot, tmp_path)
    context = UserContext(preferred_genres=("strategy",), top_k=2)

    disliked = ranker.rank(context, (_reaction("beta-kingdom", "disliked"),))
    sourced = ranker.rank(context, (_reaction("beta-kingdom", "liked"),))

    assert [value.slug for value in disliked.items] == ["alpha-tactics", "delta-command"]
    assert [value.slug for value in sourced.items] == ["alpha-tactics", "delta-command"]
    assert len(disliked.items) == context.top_k
    assert len(sourced.items) == context.top_k
    assert [value.game_slug for value in sourced.positive_sources] == ["beta-kingdom"]


def test_positive_source_precedence_recent_cap_and_timestamp_tie(
    item_factory,
    tmp_path,
) -> None:
    snapshot = canonical_snapshot(item_factory(f"game-{suffix}") for suffix in "abcdefgh")
    ranker = _ranker(snapshot, tmp_path)
    feedback = (
        _reaction(
            "game-a",
            "liked",
            occurred_at=_at(1),
            rating=Decimal("10"),
            rating_occurred_at=_at(20),
        ),
        ActiveGameFeedback(
            game_slug="game-b",
            rating=Decimal("7.00"),
            rating_occurred_at=_at(2),
        ),
        _reaction(
            "game-c",
            "disliked",
            occurred_at=_at(8),
            rating=Decimal("10"),
            rating_occurred_at=_at(30),
        ),
        _reaction("game-d", "liked", occurred_at=_at(6)),
        _reaction("game-e", "liked", occurred_at=_at(5)),
        _reaction("game-f", "liked", occurred_at=_at(4)),
        _reaction("game-g", "liked", occurred_at=_at(3)),
        _reaction("game-h", "liked", occurred_at=_at(2)),
    )

    result = ranker.rank(UserContext(preferred_genres=("strategy",), top_k=1), feedback)

    assert [
        (source.game_slug, source.kind, source.occurred_at) for source in result.positive_sources
    ] == [
        ("game-d", "liked", _at(6)),
        ("game-e", "liked", _at(5)),
        ("game-f", "liked", _at(4)),
        ("game-g", "liked", _at(3)),
        ("game-b", "rating", _at(2)),
    ]
    assert "game-c" not in {source.game_slug for source in result.positive_sources}


def test_rating_threshold_and_reaction_precedence(snapshot, tmp_path) -> None:
    ranker = _ranker(snapshot, tmp_path)
    feedback = (
        ActiveGameFeedback(
            game_slug="alpha-tactics",
            rating=Decimal("7.00"),
            rating_occurred_at=_at(1),
        ),
        ActiveGameFeedback(
            game_slug="beta-kingdom",
            rating=Decimal("6.99"),
            rating_occurred_at=_at(2),
        ),
        _reaction(
            "gamma-drift",
            "disliked",
            occurred_at=_at(3),
            rating=Decimal("10"),
            rating_occurred_at=_at(4),
        ),
        _reaction(
            "delta-command",
            "liked",
            occurred_at=_at(5),
            rating=Decimal("1"),
            rating_occurred_at=_at(6),
        ),
    )

    result = ranker.rank(UserContext(preferred_genres=("strategy",), top_k=4), feedback)

    assert [(value.game_slug, value.kind) for value in result.positive_sources] == [
        ("delta-command", "liked"),
        ("alpha-tactics", "rating"),
    ]
    assert "gamma-drift" not in {value.slug for value in result.items}


def test_wishlist_is_persistable_but_ranking_neutral(snapshot, tmp_path) -> None:
    ranker = _ranker(snapshot, tmp_path)
    context = UserContext(preferred_genres=("strategy",), top_k=4)

    baseline = ranker.rank(context, ())
    wishlisted = ranker.rank(
        context,
        (ActiveGameFeedback(game_slug="beta-kingdom", wishlisted=True),),
    )

    assert wishlisted == baseline


def test_affinity_and_played_adjustment_reconstruct_exact_fixed_units(snapshot, tmp_path) -> None:
    ranker = _ranker(snapshot, tmp_path)
    feedback = (
        _reaction("gamma-drift", "liked"),
        ActiveGameFeedback(game_slug="alpha-tactics", played=True),
    )

    result = ranker.rank(UserContext(preferred_genres=("strategy",), top_k=4), feedback)

    assert [source.game_slug for source in result.positive_sources] == ["gamma-drift"]
    assert "gamma-drift" not in {value.slug for value in result.items}
    for value in result.items:
        assert value.base_weight_units == 900_000
        assert value.affinity_weight_units == 100_000
        assert value.base_contribution_units == contribution(value.base_score_units, 900_000)
        assert value.affinity_contribution_units == contribution(
            value.affinity_score_units,
            100_000,
        )
        assert value.pre_played_score_units == (
            value.base_contribution_units + value.affinity_contribution_units
        )
        expected_factor = 500_000 if value.slug == "alpha-tactics" else 1_000_000
        assert value.played_factor_units == expected_factor
        assert value.final_score_units == contribution(
            value.pre_played_score_units,
            expected_factor,
        )
        assert value.played_delta_units == (value.final_score_units - value.pre_played_score_units)
        assert 0 <= value.affinity_score_units <= 1_000_000
        assert 0 <= value.final_score_units <= 1_000_000
        assert "feedback_affinity" in value.adjustment_reasons
        assert ("played_adjustment" in value.adjustment_reasons) == (value.slug == "alpha-tactics")


def test_exact_affinity_without_positive_profile_returns_inactive_zero_units(
    snapshot,
    tmp_path,
) -> None:
    ranker = _ranker(snapshot, tmp_path)

    result = ranker.materialize_affinity_candidates(
        (),
        ("gamma-drift", "alpha-tactics"),
    )

    assert result == AffinityMaterializationResult(
        profile_active=False,
        candidates=(
            AffinityCandidateScore("alpha-tactics", 0),
            AffinityCandidateScore("gamma-drift", 0),
        ),
    )


def test_exact_affinity_matches_liked_and_qualifying_rating_stage_4_units(
    snapshot,
    tmp_path,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    context = UserContext(
        selected_game_slugs=("alpha-tactics",),
        preferred_genres=("strategy",),
        preferred_platforms=("linux",),
        top_k=4,
    )
    liked = ranker.rank(context, (_reaction("gamma-drift", "liked"),))
    rating = ranker.rank(
        context,
        (
            ActiveGameFeedback(
                game_slug="gamma-drift",
                rating=Decimal("7.00"),
                rating_occurred_at=NOW,
            ),
        ),
    )

    liked_exact = ranker.materialize_affinity_candidates(
        liked.positive_sources,
        ("gamma-drift", "delta-command", "beta-kingdom"),
    )
    rating_exact = ranker.materialize_affinity_candidates(
        rating.positive_sources,
        ("beta-kingdom", "gamma-drift", "delta-command"),
    )

    assert tuple(source.kind for source in liked.positive_sources) == ("liked",)
    assert tuple(source.kind for source in rating.positive_sources) == ("rating",)
    assert ranker.materialize_affinity_candidates(
        liked.positive_sources,
        (),
    ) == AffinityMaterializationResult(profile_active=True, candidates=())
    assert (
        liked_exact
        == rating_exact
        == AffinityMaterializationResult(
            profile_active=True,
            candidates=(
                AffinityCandidateScore("beta-kingdom", 36_098),
                AffinityCandidateScore("delta-command", 24_832),
                AffinityCandidateScore("gamma-drift", 1_000_000),
            ),
        )
    )
    expected_by_slug = {
        candidate.slug: candidate.affinity_score_units for candidate in liked_exact.candidates
    }
    for ranked in (liked, rating):
        assert "gamma-drift" not in {candidate.slug for candidate in ranked.items}
        assert all(
            candidate.affinity_score_units == expected_by_slug[candidate.slug]
            for candidate in ranked.items
        )


def test_exact_affinity_can_be_active_with_zero_candidate_affinity(
    item_factory,
    tmp_path,
) -> None:
    source = replace(
        item_factory(
            "orbit-source",
            title="Quasar",
            description="stellar nebula cosmos",
            genres=("space",),
            tags=("cosmic",),
        ),
        developer="Nebula Studio",
        publisher="Galaxy Works",
    )
    target = replace(
        item_factory(
            "harvest-target",
            title="Orchard",
            description="farming crops village",
            genres=("simulation",),
            tags=("cozy",),
        ),
        developer="Meadow Studio",
        publisher="Garden Works",
    )
    ranker = _ranker(canonical_snapshot((source, target)), tmp_path)

    result = ranker.materialize_affinity_candidates(
        (PositiveFeedbackSource("orbit-source", "liked", NOW),),
        ("harvest-target",),
    )

    assert result == AffinityMaterializationResult(
        profile_active=True,
        candidates=(AffinityCandidateScore("harvest-target", 0),),
    )


def test_exact_affinity_reads_only_source_and_canonical_candidate_rows(
    snapshot,
    tmp_path,
) -> None:
    artifact = load_artifact(build_artifact(snapshot, tmp_path / "model"))
    matrix = artifact.matrix
    row_reads: list[tuple[int, ...]] = []

    class RecordingMatrix:
        shape = matrix.shape

        def __getitem__(self, rows):
            row_reads.append(tuple(int(row) for row in rows))
            return matrix[rows]

    ranker = FeedbackRanker(replace(artifact, matrix=RecordingMatrix()))
    sources = (PositiveFeedbackSource("gamma-drift", "liked", NOW),)
    first = ranker.materialize_affinity_candidates(
        sources,
        ("delta-command", "beta-kingdom"),
    )
    second = ranker.materialize_affinity_candidates(
        sources,
        ("beta-kingdom", "delta-command"),
    )

    source_rows = (artifact.slug_to_row["gamma-drift"],)
    candidate_rows = (
        artifact.slug_to_row["beta-kingdom"],
        artifact.slug_to_row["delta-command"],
    )
    assert first == second
    assert first.candidates == (
        AffinityCandidateScore("beta-kingdom", 36_098),
        AffinityCandidateScore("delta-command", 24_832),
    )
    assert row_reads == [source_rows, candidate_rows, source_rows, candidate_rows]


def test_feedback_rank_delegates_affinity_to_exact_materializer(
    snapshot,
    tmp_path,
    monkeypatch,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    original = ranker.materialize_affinity_candidates
    calls: list[tuple[tuple[PositiveFeedbackSource, ...], tuple[str, ...]]] = []

    def recording_materializer(positive_sources, candidate_slugs):
        calls.append((positive_sources, candidate_slugs))
        return original(positive_sources, candidate_slugs)

    monkeypatch.setattr(ranker, "materialize_affinity_candidates", recording_materializer)
    result = ranker.rank(
        UserContext(preferred_genres=("strategy",), top_k=4),
        (_reaction("gamma-drift", "liked"),),
    )

    assert len(calls) == 1
    exact = original(*calls[0])
    exact_by_slug = {
        candidate.slug: candidate.affinity_score_units for candidate in exact.candidates
    }
    assert all(
        candidate.affinity_score_units == exact_by_slug[candidate.slug]
        for candidate in result.items
    )


def test_feedback_rank_batches_large_stage_4_candidate_sets_without_narrowing(
    snapshot,
    tmp_path,
    monkeypatch,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    candidates = (
        BaseCandidateScore(
            slug="alpha-tactics",
            base_score_units=1_000_000,
            content_score_units=1_000_000,
            platform_score_units=0,
            popularity_score_units=0,
        ),
        *(
            BaseCandidateScore(
                slug=f"candidate-{index}",
                base_score_units=1,
                content_score_units=1,
                platform_score_units=0,
                popularity_score_units=0,
            )
            for index in range(1_000)
        ),
    )
    batch_sizes: list[int] = []

    monkeypatch.setattr(ranker.content_ranker, "score_candidates", lambda _context: candidates)

    def inactive_materializer(_positive_sources, candidate_slugs):
        batch_sizes.append(len(candidate_slugs))
        return AffinityMaterializationResult(
            profile_active=False,
            candidates=tuple(AffinityCandidateScore(slug, 0) for slug in candidate_slugs),
        )

    monkeypatch.setattr(ranker, "materialize_affinity_candidates", inactive_materializer)
    result = ranker.rank(
        UserContext(preferred_genres=("strategy",), top_k=1),
        (),
    )

    assert batch_sizes == [1_000, 1]
    assert tuple(candidate.slug for candidate in result.items) == ("alpha-tactics",)


@pytest.mark.parametrize(
    ("candidate_slugs", "expected_code"),
    [
        pytest.param(
            ["beta-kingdom"],
            "materialization_input_invalid",
            id="mutable-candidates",
        ),
        pytest.param(
            ("beta-kingdom", "beta-kingdom"),
            "materialization_input_invalid",
            id="duplicate-candidate",
        ),
        pytest.param(
            ("Beta-Kingdom",),
            "materialization_input_invalid",
            id="noncanonical-candidate",
        ),
        pytest.param(
            ("unknown-game",),
            "materialization_artifact_incompatible",
            id="missing-candidate",
        ),
        pytest.param(
            tuple(f"unknown-{index}" for index in range(1_000)),
            "materialization_artifact_incompatible",
            id="candidate-at-cap",
        ),
        pytest.param(
            tuple(f"unknown-{index}" for index in range(1_001)),
            "materialization_input_invalid",
            id="candidate-over-cap",
        ),
    ],
)
def test_exact_affinity_rejects_invalid_or_incompatible_candidates(
    snapshot,
    tmp_path,
    monkeypatch,
    candidate_slugs,
    expected_code,
) -> None:
    ranker = _ranker(snapshot, tmp_path)

    def unexpected_profile_traversal(_vector):
        raise AssertionError("Invalid exact candidates must fail before profile traversal")

    monkeypatch.setattr(feedback_module, "_normalize_profile", unexpected_profile_traversal)
    with pytest.raises(AffinityMaterializationError) as captured:
        ranker.materialize_affinity_candidates((), candidate_slugs)

    assert captured.value.code == expected_code


@pytest.mark.parametrize(
    ("positive_sources", "expected_code"),
    [
        pytest.param(
            [PositiveFeedbackSource("gamma-drift", "liked", NOW)],
            "materialization_input_invalid",
            id="mutable-sources",
        ),
        pytest.param(
            (
                PositiveFeedbackSource("alpha-tactics", "liked", NOW),
                PositiveFeedbackSource("beta-kingdom", "rating", _at(1)),
            ),
            "materialization_input_invalid",
            id="noncanonical-source-order",
        ),
        pytest.param(
            (PositiveFeedbackSource("unknown-game", "liked", NOW),),
            "materialization_artifact_incompatible",
            id="missing-source",
        ),
    ],
)
def test_exact_affinity_rejects_noncanonical_or_incompatible_sources(
    snapshot,
    tmp_path,
    positive_sources,
    expected_code,
) -> None:
    ranker = _ranker(snapshot, tmp_path)

    with pytest.raises(AffinityMaterializationError) as captured:
        ranker.materialize_affinity_candidates(positive_sources, ("beta-kingdom",))

    assert captured.value.code == expected_code


def test_feedback_rank_preserves_stage_4_characterization_golden(snapshot, tmp_path) -> None:
    ranker = _ranker(snapshot, tmp_path)
    context = UserContext(
        selected_game_slugs=("alpha-tactics",),
        preferred_genres=("strategy",),
        preferred_platforms=("linux",),
        top_k=3,
    )
    feedback = (
        _reaction("gamma-drift", "liked"),
        ActiveGameFeedback(game_slug="beta-kingdom", played=True),
        ActiveGameFeedback(game_slug="delta-command", wishlisted=True),
    )

    result = ranker.rank(context, feedback)

    assert result.reason == "recommendations"
    assert (result.policy.name, result.policy.version) == (
        "gamelens-feedback-adjustment",
        "1.0.0",
    )
    assert [
        (source.game_slug, source.kind, source.occurred_at) for source in result.positive_sources
    ] == [("gamma-drift", "liked", NOW)]
    assert [
        (
            value.slug,
            value.rank,
            value.base_score_units,
            tuple(
                (
                    component.name,
                    component.raw_units,
                    component.weight_units,
                    component.contribution_units,
                )
                for component in value.base_components
            ),
            tuple((item.slug, item.name) for item in value.base_evidence.matching_genres),
            tuple((item.slug, item.name) for item in value.base_evidence.matching_tags),
            tuple((item.slug, item.name) for item in value.base_evidence.preferred_platforms),
            tuple(
                (item.slug, item.title, item.similarity_units)
                for item in value.base_evidence.similar_selected_games
            ),
            value.base_evidence.popularity_percentile_units,
            value.explanation_summary,
            value.explanation_reasons,
            value.base_weight_units,
            value.base_contribution_units,
            value.affinity_score_units,
            value.affinity_weight_units,
            value.affinity_contribution_units,
            value.pre_played_score_units,
            value.played_factor_units,
            value.played_delta_units,
            value.final_score_units,
            value.adjustment_reasons,
        )
        for value in result.items
    ] == [
        (
            "delta-command",
            1,
            489_035,
            (
                ("content", 420_044, 800_000, 336_035),
                ("platform", 1_000_000, 100_000, 100_000),
                ("popularity", 530_000, 100_000, 53_000),
            ),
            (("strategy", "Strategy"),),
            (),
            (("linux", "LINUX"),),
            (("alpha-tactics", "Alpha Tactics", 389_497),),
            530_000,
            "Its content profile is similar to Alpha Tactics.",
            (
                "Its content profile is similar to Alpha Tactics.",
                "It matches your preferred genres: Strategy.",
                "It is available on preferred platforms: LINUX.",
            ),
            900_000,
            440_132,
            24_832,
            100_000,
            2_483,
            442_615,
            1_000_000,
            0,
            442_615,
            ("feedback_affinity",),
        ),
        (
            "beta-kingdom",
            2,
            467_586,
            (
                ("content", 378_233, 800_000, 302_586),
                ("platform", 1_000_000, 100_000, 100_000),
                ("popularity", 650_000, 100_000, 65_000),
            ),
            (("strategy", "Strategy"),),
            (),
            (("linux", "LINUX"),),
            (("alpha-tactics", "Alpha Tactics", 341_166),),
            650_000,
            "Its content profile is similar to Alpha Tactics.",
            (
                "Its content profile is similar to Alpha Tactics.",
                "It matches your preferred genres: Strategy.",
                "It is available on preferred platforms: LINUX.",
            ),
            900_000,
            420_827,
            36_098,
            100_000,
            3_610,
            424_437,
            500_000,
            -212_218,
            212_219,
            ("feedback_affinity", "played_adjustment"),
        ),
    ]


def test_feedback_cannot_promote_zero_primary_content_candidate(item_factory, tmp_path) -> None:
    anchor = replace(
        item_factory(
            "anchor-strategy",
            title="Fortress",
            description="fortress tactics",
            genres=("strategy",),
            tags=("turn-based",),
        ),
        developer="Anchor Studio",
        publisher="Anchor Publisher",
    )
    source = replace(
        item_factory(
            "source-racer",
            title="Velocity",
            description="neon drifting",
            genres=("racing",),
            tags=("arcade",),
        ),
        developer="Source Studio",
        publisher="Source Publisher",
    )
    target = replace(
        item_factory(
            "target-racer",
            title="Momentum",
            description="neon drifting",
            genres=("racing",),
            tags=("arcade",),
        ),
        developer="Target Studio",
        publisher="Target Publisher",
    )
    ranker = _ranker(canonical_snapshot((anchor, source, target)), tmp_path)

    result = ranker.rank(
        UserContext(preferred_genres=("strategy",), top_k=3),
        (_reaction("source-racer", "liked"),),
    )

    assert [value.slug for value in result.items] == ["anchor-strategy"]
    assert "target-racer" not in {value.slug for value in result.items}


def test_empty_reasons_distinguish_base_support_from_policy_exclusion(
    item_factory,
    snapshot,
    tmp_path,
) -> None:
    single = canonical_snapshot((item_factory("only-game"),))
    no_support = _ranker(single, tmp_path / "single").rank(
        UserContext(selected_game_slugs=("only-game",)),
        (),
    )
    all_excluded = _ranker(snapshot, tmp_path / "catalog").rank(
        UserContext(selected_game_slugs=("alpha-tactics",), top_k=4),
        (
            _reaction("beta-kingdom", "disliked"),
            _reaction("gamma-drift", "disliked"),
            _reaction("delta-command", "disliked"),
        ),
    )

    assert no_support.reason == "no_content_support"
    assert no_support.items == ()
    assert all_excluded.reason == "no_eligible_candidates"
    assert all_excluded.items == ()


def test_disliked_selected_game_cannot_leave_empty_effective_context(snapshot, tmp_path) -> None:
    ranker = _ranker(snapshot, tmp_path)

    with pytest.raises(InsufficientContextError, match="without a content signal"):
        ranker.rank(
            UserContext(selected_game_slugs=("alpha-tactics",)),
            (_reaction("alpha-tactics", "disliked"),),
        )


def test_full_personalized_tie_break_ends_with_stable_slug(item_factory, tmp_path) -> None:
    items = tuple(
        replace(
            item_factory(
                f"same-{suffix}",
                title="Same Game",
                description="identical tactical strategy",
                popularity=50,
            ),
            developer="Same Studio",
            publisher="Same Publisher",
        )
        for suffix in "abc"
    )
    ranker = _ranker(canonical_snapshot(items), tmp_path)

    result = ranker.rank(
        UserContext(preferred_genres=("strategy",), top_k=3),
        (_reaction("same-c", "liked"),),
    )

    assert [value.slug for value in result.items] == ["same-a", "same-b"]
    first, second = result.items
    assert first.final_score_units == second.final_score_units
    assert first.pre_played_score_units == second.pre_played_score_units
    assert first.base_score_units == second.base_score_units
    assert first.affinity_score_units == second.affinity_score_units


@pytest.mark.parametrize(
    "feedback",
    [
        pytest.param([], id="mutable-list"),
        pytest.param(
            (
                ActiveGameFeedback(game_slug="alpha-tactics", played=True),
                ActiveGameFeedback(game_slug="alpha-tactics", wishlisted=True),
            ),
            id="duplicate-slug",
        ),
        pytest.param(
            (ActiveGameFeedback(game_slug="unknown-game", played=True),),
            id="unknown-slug",
        ),
        pytest.param(
            (ActiveGameFeedback(game_slug="alpha-tactics"),),
            id="empty-state",
        ),
        pytest.param(
            (
                ActiveGameFeedback(
                    game_slug="alpha-tactics",
                    reaction="liked",
                    reaction_occurred_at=datetime(2026, 8, 12),
                ),
            ),
            id="naive-reaction-time",
        ),
        pytest.param(
            (
                ActiveGameFeedback(
                    game_slug="alpha-tactics",
                    reaction_occurred_at=NOW,
                    played=True,
                ),
            ),
            id="orphan-reaction-time",
        ),
        pytest.param(
            (
                ActiveGameFeedback(
                    game_slug="alpha-tactics",
                    rating=7.0,
                    rating_occurred_at=NOW,
                ),
            ),
            id="non-decimal-rating",
        ),
        pytest.param(
            (
                ActiveGameFeedback(
                    game_slug="alpha-tactics",
                    rating=Decimal("NaN"),
                    rating_occurred_at=NOW,
                ),
            ),
            id="non-finite-rating",
        ),
        pytest.param(
            (
                ActiveGameFeedback(
                    game_slug="alpha-tactics",
                    rating=Decimal("10.01"),
                    rating_occurred_at=NOW,
                ),
            ),
            id="rating-out-of-range",
        ),
    ],
)
def test_feedback_boundary_rejects_invalid_or_mutable_input(
    snapshot,
    tmp_path,
    feedback,
) -> None:
    ranker = _ranker(snapshot, tmp_path)

    with pytest.raises(ValueError):
        ranker.rank(UserContext(preferred_genres=("strategy",)), feedback)


def test_feedback_schemas_are_frozen() -> None:
    value = ActiveGameFeedback(game_slug="alpha-tactics", played=True)

    with pytest.raises(FrozenInstanceError):
        value.played = False


def test_interleaved_calls_do_not_mutate_artifact_or_leak_feedback_state(
    snapshot, tmp_path
) -> None:
    artifact = load_artifact(build_artifact(snapshot, tmp_path / "model"))
    ranker = FeedbackRanker(artifact)
    matrix = artifact.matrix.data.copy()
    popularity = artifact.popularity.copy()
    identity = (
        artifact.model_name,
        artifact.model_version,
        artifact.data_fingerprint,
        repr(artifact.manifest),
    )
    context = UserContext(preferred_genres=("strategy",), top_k=4)
    first_feedback = (_reaction("beta-kingdom", "disliked"),)
    second_feedback = (_reaction("gamma-drift", "liked"),)

    first = ranker.rank(context, first_feedback)
    ranker.rank(context, second_feedback)
    repeated = ranker.rank(context, first_feedback)

    assert repeated == first
    assert np.array_equal(artifact.matrix.data, matrix)
    assert np.array_equal(artifact.popularity, popularity)
    assert artifact.matrix.data.flags.writeable is False
    assert artifact.popularity.flags.writeable is False
    assert (
        artifact.model_name,
        artifact.model_version,
        artifact.data_fingerprint,
        repr(artifact.manifest),
    ) == identity


@pytest.mark.parametrize(
    "config",
    [
        replace(
            FeedbackPolicyConfig(),
            base_weight_units=800_000,
            affinity_weight_units=100_000,
        ),
        replace(FeedbackPolicyConfig(), played_factor_units=1_000_001),
        replace(FeedbackPolicyConfig(), tie_break=("slug_asc",)),
        replace(FeedbackPolicyConfig(), positive_rating_threshold=Decimal("NaN")),
        replace(FeedbackPolicyConfig(), name="different-feedback-policy"),
    ],
)
def test_feedback_policy_configuration_is_validated(snapshot, tmp_path, config) -> None:
    artifact = load_artifact(build_artifact(snapshot, tmp_path / "model"))

    with pytest.raises(ValueError):
        FeedbackRanker(artifact, config)
