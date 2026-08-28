from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

import gamelens_recommender
from gamelens_recommender import (
    ActiveGameFeedback,
    FeedbackRanker,
    InsufficientContextError,
    PositiveFeedbackSource,
    PreparedFeedbackRankingContext,
    UserContext,
    build_artifact,
    canonical_snapshot,
    load_artifact,
)
from gamelens_recommender.collaborative import (
    CollaborativeQueryContext,
    CollaborativeQuerySource,
)

NOW = datetime(2026, 8, 28, tzinfo=UTC)


def _ranker(snapshot, tmp_path) -> FeedbackRanker:
    return FeedbackRanker(load_artifact(build_artifact(snapshot, tmp_path / "model")))


def _reaction(
    slug: str,
    reaction: str,
    *,
    occurred_at: datetime = NOW,
) -> ActiveGameFeedback:
    return ActiveGameFeedback(
        game_slug=slug,
        reaction=reaction,
        reaction_occurred_at=occurred_at,
    )


def test_prepare_feedback_context_exposes_one_canonical_stage4_state(
    snapshot,
    tmp_path,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    context = UserContext(
        selected_game_slugs=("alpha-tactics", "gamma-drift"),
        preferred_genres=("strategy",),
        preferred_platforms=("linux",),
        top_k=4,
    )
    feedback = (
        ActiveGameFeedback(game_slug="alpha-tactics", played=True, wishlisted=True),
        _reaction("beta-kingdom", "liked"),
        _reaction("gamma-drift", "disliked", occurred_at=NOW + timedelta(minutes=2)),
        ActiveGameFeedback(
            game_slug="delta-command",
            played=True,
            rating=Decimal("8"),
            rating_occurred_at=NOW + timedelta(minutes=1),
        ),
    )

    prepared = ranker.prepare_ranking_context(context, feedback)

    assert prepared == PreparedFeedbackRankingContext(
        effective_context=UserContext(
            selected_game_slugs=("alpha-tactics",),
            preferred_genres=("strategy",),
            preferred_platforms=("linux",),
            top_k=4,
        ),
        positive_sources=(
            PositiveFeedbackSource(
                "delta-command",
                "rating",
                NOW + timedelta(minutes=1),
            ),
            PositiveFeedbackSource("beta-kingdom", "liked", NOW),
        ),
        collaborative_query_context=CollaborativeQueryContext(
            sources=(
                CollaborativeQuerySource("delta-command", "rating"),
                CollaborativeQuerySource("beta-kingdom", "liked"),
                CollaborativeQuerySource("alpha-tactics", "saved_game"),
            ),
            disliked_slugs=("gamma-drift",),
        ),
        candidate_exclusion_slugs=(
            "alpha-tactics",
            "beta-kingdom",
            "delta-command",
            "gamma-drift",
        ),
        played_slugs=("alpha-tactics", "delta-command"),
    )
    prepared.validate()
    assert not hasattr(prepared, "wishlisted_slugs")


def test_prepare_feedback_context_uses_feedback_over_saved_source_precedence(
    snapshot,
    tmp_path,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    context = UserContext(
        selected_game_slugs=("beta-kingdom", "alpha-tactics", "gamma-drift"),
        top_k=4,
    )
    feedback = (
        ActiveGameFeedback(
            game_slug="alpha-tactics",
            rating=Decimal("7"),
            rating_occurred_at=NOW,
        ),
        ActiveGameFeedback(
            game_slug="beta-kingdom",
            reaction="liked",
            reaction_occurred_at=NOW + timedelta(minutes=1),
            rating=Decimal("10"),
            rating_occurred_at=NOW + timedelta(minutes=2),
        ),
    )

    prepared = ranker.prepare_ranking_context(context, feedback)

    assert tuple(
        (source.game_slug, source.kind) for source in prepared.collaborative_query_context.sources
    ) == (
        ("beta-kingdom", "liked"),
        ("alpha-tactics", "rating"),
        ("gamma-drift", "saved_game"),
    )
    assert tuple((source.game_slug, source.kind) for source in prepared.positive_sources) == (
        ("beta-kingdom", "liked"),
        ("alpha-tactics", "rating"),
    )


def test_capped_positive_source_cannot_reenter_as_a_saved_source(item_factory, tmp_path) -> None:
    snapshot = canonical_snapshot(item_factory(f"game-{suffix}") for suffix in "abcdefg")
    ranker = _ranker(snapshot, tmp_path)
    feedback = tuple(
        _reaction(
            f"game-{suffix}",
            "liked",
            occurred_at=NOW + timedelta(minutes=index),
        )
        for index, suffix in enumerate("abcdef", start=1)
    )

    prepared = ranker.prepare_ranking_context(
        UserContext(selected_game_slugs=("game-a",)),
        feedback,
    )

    assert tuple(source.game_slug for source in prepared.positive_sources) == (
        "game-f",
        "game-e",
        "game-d",
        "game-c",
        "game-b",
    )
    assert "game-a" not in {
        source.game_slug for source in prepared.collaborative_query_context.sources
    }
    prepared.validate()


def test_wishlist_remains_neutral_in_prepared_and_ranked_state(snapshot, tmp_path) -> None:
    ranker = _ranker(snapshot, tmp_path)
    context = UserContext(preferred_genres=("strategy",), top_k=4)
    wishlist = (ActiveGameFeedback(game_slug="beta-kingdom", wishlisted=True),)

    baseline_context = ranker.prepare_ranking_context(context, ())
    wishlist_context = ranker.prepare_ranking_context(context, wishlist)

    assert wishlist_context == baseline_context
    assert ranker.rank(context, wishlist) == ranker.rank(context, ())


def test_prepare_feedback_context_is_frozen_and_rejects_inconsistent_copies(
    snapshot,
    tmp_path,
) -> None:
    prepared = _ranker(snapshot, tmp_path).prepare_ranking_context(
        UserContext(
            selected_game_slugs=("alpha-tactics",),
            preferred_genres=("strategy",),
        ),
        (_reaction("beta-kingdom", "liked"),),
    )

    with pytest.raises(FrozenInstanceError):
        prepared.played_slugs = ("alpha-tactics",)
    for invalid in (
        replace(prepared, candidate_exclusion_slugs=("alpha-tactics",)),
        replace(prepared, played_slugs=("beta-kingdom", "alpha-tactics")),
        replace(
            prepared,
            collaborative_query_context=CollaborativeQueryContext(
                sources=(CollaborativeQuerySource("alpha-tactics", "saved_game"),),
                disliked_slugs=(),
            ),
        ),
    ):
        with pytest.raises(ValueError, match="Prepared"):
            invalid.validate()


def test_prepare_feedback_context_performs_no_candidate_scoring(
    snapshot,
    tmp_path,
    monkeypatch,
) -> None:
    ranker = _ranker(snapshot, tmp_path)

    def unexpected_call(*_args, **_kwargs):
        raise AssertionError("Context preparation must not score or materialize candidates")

    monkeypatch.setattr(ranker.content_ranker, "score_candidates", unexpected_call)
    monkeypatch.setattr(ranker.content_ranker, "materialize_candidate", unexpected_call)
    monkeypatch.setattr(ranker, "materialize_affinity_candidates", unexpected_call)

    prepared = ranker.prepare_ranking_context(
        UserContext(preferred_genres=("strategy",)),
        (_reaction("beta-kingdom", "liked"),),
    )

    assert prepared.positive_sources == (PositiveFeedbackSource("beta-kingdom", "liked", NOW),)


def test_feedback_rank_delegates_context_preparation_once(
    snapshot,
    tmp_path,
    monkeypatch,
) -> None:
    ranker = _ranker(snapshot, tmp_path)
    context = UserContext(preferred_genres=("strategy",), top_k=3)
    feedback = (
        _reaction("gamma-drift", "liked"),
        ActiveGameFeedback(game_slug="alpha-tactics", played=True),
    )
    original = ranker.prepare_ranking_context
    calls: list[tuple[UserContext, tuple[ActiveGameFeedback, ...]]] = []

    def recording_prepare(actual_context, actual_feedback):
        calls.append((actual_context, actual_feedback))
        return original(actual_context, actual_feedback)

    monkeypatch.setattr(ranker, "prepare_ranking_context", recording_prepare)

    result = ranker.rank(context, feedback)

    assert calls == [(context, feedback)]
    assert result.positive_sources == original(context, feedback).positive_sources


def test_prepare_feedback_context_preserves_stage4_validation_order(snapshot, tmp_path) -> None:
    ranker = _ranker(snapshot, tmp_path)

    with pytest.raises(ValueError, match="Selected game is not present"):
        ranker.prepare_ranking_context(
            UserContext(selected_game_slugs=("unknown-game",)),
            [],  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="Feedback input must be an immutable tuple"):
        ranker.prepare_ranking_context(
            UserContext(preferred_genres=("strategy",)),
            [],  # type: ignore[arg-type]
        )
    with pytest.raises(InsufficientContextError, match="without a content signal"):
        ranker.prepare_ranking_context(
            UserContext(selected_game_slugs=("alpha-tactics",)),
            (_reaction("alpha-tactics", "disliked"),),
        )


def test_prepared_feedback_context_is_a_stable_package_export() -> None:
    assert "PreparedFeedbackRankingContext" in gamelens_recommender.__all__
    assert gamelens_recommender.PreparedFeedbackRankingContext is PreparedFeedbackRankingContext
