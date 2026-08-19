from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from gamelens_recommender import (
    ActiveGameFeedback,
    ContentRanker,
    FeedbackPolicyConfig,
    FeedbackRanker,
    InsufficientContextError,
    UserContext,
    build_artifact,
    canonical_snapshot,
    load_artifact,
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
