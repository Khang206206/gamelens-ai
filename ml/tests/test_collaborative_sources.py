from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from itertools import permutations

import pytest

from gamelens_recommender.collaborative import (
    COLLABORATIVE_SCORING_CONFIG,
    CollaborativeQueryContext,
    CollaborativeScoringError,
    CollaborativeSourceState,
    canonicalize_collaborative_query_sources,
)
from gamelens_recommender.schemas import PositiveFeedbackSource


def _at(hour: int, *, slug: str, kind: str = "liked") -> PositiveFeedbackSource:
    return PositiveFeedbackSource(
        game_slug=slug,
        kind=kind,
        occurred_at=datetime(2026, 8, 27, hour, tzinfo=UTC),
    )


def _project(context: CollaborativeQueryContext) -> tuple[tuple[str, str], ...]:
    return tuple((source.game_slug, source.kind) for source in context.sources)


def test_canonicalizer_applies_precedence_cross_kind_deduplication_and_stable_order() -> None:
    state = CollaborativeSourceState(
        positive_sources=(
            _at(1, slug="alpha-source", kind="liked"),
            _at(9, slug="alpha-source", kind="liked"),
            _at(10, slug="alpha-source", kind="rating"),
            _at(8, slug="gamma-source", kind="liked"),
            _at(8, slug="beta-source", kind="rating"),
            _at(9, slug="blocked-source", kind="liked"),
        ),
        saved_game_slugs=(
            "saved-z",
            "alpha-source",
            "saved-a",
            "blocked-source",
            "beta-source",
        ),
        disliked_slugs=("blocked-source",),
    )

    result = canonicalize_collaborative_query_sources(state)

    assert _project(result) == (
        ("alpha-source", "liked"),
        ("beta-source", "rating"),
        ("gamma-source", "liked"),
        ("saved-a", "saved_game"),
        ("saved-z", "saved_game"),
    )
    assert result.disliked_slugs == ("blocked-source",)


def test_permutations_and_duplicate_representations_are_canonicalized_equally() -> None:
    positives = (
        _at(3, slug="same-source", kind="rating"),
        _at(1, slug="same-source", kind="liked"),
        _at(2, slug="other-source", kind="rating"),
    )
    saved = ("saved-source", "same-source", "saved-source")
    disliked = ("blocked-source", "blocked-source")
    expected = canonicalize_collaborative_query_sources(
        CollaborativeSourceState(
            positive_sources=positives,
            saved_game_slugs=saved,
            disliked_slugs=disliked,
        )
    )

    for positive_order in permutations(positives):
        for saved_order in permutations(saved):
            result = canonicalize_collaborative_query_sources(
                CollaborativeSourceState(
                    positive_sources=positive_order,
                    saved_game_slugs=saved_order,
                    disliked_slugs=tuple(reversed(disliked)),
                )
            )
            assert result == expected

    assert _project(expected) == (
        ("other-source", "rating"),
        ("same-source", "liked"),
        ("saved-source", "saved_game"),
    )
    assert expected.disliked_slugs == ("blocked-source",)


def test_equal_instants_across_timezone_offsets_use_slug_tie_break() -> None:
    same_instant_utc = datetime(2026, 8, 27, 12, tzinfo=UTC)
    same_instant_plus_seven = datetime(
        2026,
        8,
        27,
        19,
        tzinfo=timezone(timedelta(hours=7)),
    )
    state = CollaborativeSourceState(
        positive_sources=(
            PositiveFeedbackSource("zeta-source", "liked", same_instant_utc),
            PositiveFeedbackSource("alpha-source", "rating", same_instant_plus_seven),
            PositiveFeedbackSource(
                "newer-source",
                "liked",
                same_instant_utc + timedelta(seconds=1),
            ),
        )
    )

    result = canonicalize_collaborative_query_sources(state)

    assert _project(result) == (
        ("newer-source", "liked"),
        ("alpha-source", "rating"),
        ("zeta-source", "liked"),
    )


def test_caps_apply_after_dislike_and_cross_kind_precedence() -> None:
    positives = tuple(
        _at(hour, slug=f"source-{suffix}") for hour, suffix in enumerate("abcdefg", start=1)
    )
    state = CollaborativeSourceState(
        positive_sources=positives,
        saved_game_slugs=(
            "source-e",
            "blocked-source",
            *(f"saved-{suffix}" for suffix in "abcdef"),
        ),
        disliked_slugs=("source-g", "blocked-source"),
    )

    result = canonicalize_collaborative_query_sources(state)

    assert _project(result) == (
        ("source-f", "liked"),
        ("source-e", "liked"),
        ("source-d", "liked"),
        ("source-c", "liked"),
        ("source-b", "liked"),
        ("saved-a", "saved_game"),
        ("saved-b", "saved_game"),
        ("saved-c", "saved_game"),
        ("saved-d", "saved_game"),
        ("saved-e", "saved_game"),
    )
    assert len(result.sources) == COLLABORATIVE_SCORING_CONFIG.max_query_sources


def test_empty_source_state_returns_empty_canonical_context() -> None:
    result = canonicalize_collaborative_query_sources(CollaborativeSourceState())

    assert result == CollaborativeQueryContext()


@pytest.mark.parametrize(
    "state",
    [
        pytest.param(
            CollaborativeSourceState(positive_sources=[]),
            id="mutable-positive-sources",
        ),
        pytest.param(
            CollaborativeSourceState(saved_game_slugs=["saved-source"]),
            id="mutable-saved-sources",
        ),
        pytest.param(
            CollaborativeSourceState(disliked_slugs=["blocked-source"]),
            id="mutable-dislikes",
        ),
        pytest.param(
            CollaborativeSourceState(positive_sources=(object(),)),
            id="invalid-positive-source-type",
        ),
        pytest.param(
            CollaborativeSourceState(
                positive_sources=(_at(1, slug="source-a", kind="saved_game"),)
            ),
            id="invalid-positive-source-kind",
        ),
        pytest.param(
            CollaborativeSourceState(
                positive_sources=(
                    PositiveFeedbackSource(
                        game_slug="source-a",
                        kind=[],
                        occurred_at=datetime(2026, 8, 27, tzinfo=UTC),
                    ),
                )
            ),
            id="invalid-positive-source-kind-type",
        ),
        pytest.param(
            CollaborativeSourceState(
                positive_sources=(
                    PositiveFeedbackSource(
                        game_slug="source-a",
                        kind="liked",
                        occurred_at=datetime(2026, 8, 27),
                    ),
                )
            ),
            id="naive-positive-timestamp",
        ),
        pytest.param(
            CollaborativeSourceState(positive_sources=(_at(1, slug="Not-Canonical"),)),
            id="invalid-positive-slug",
        ),
        pytest.param(
            CollaborativeSourceState(saved_game_slugs=("Not-Canonical",)),
            id="invalid-saved-slug",
        ),
        pytest.param(
            CollaborativeSourceState(disliked_slugs=("Not-Canonical",)),
            id="invalid-dislike-slug",
        ),
    ],
)
def test_canonicalizer_rejects_invalid_or_mutable_source_state(
    state: CollaborativeSourceState,
) -> None:
    with pytest.raises(CollaborativeScoringError) as captured:
        canonicalize_collaborative_query_sources(state)

    assert captured.value.code == "scoring_input_invalid"


def test_canonicalizer_rejects_non_source_state_input() -> None:
    with pytest.raises(CollaborativeScoringError) as captured:
        canonicalize_collaborative_query_sources(object())

    assert captured.value.code == "scoring_input_invalid"


def test_canonicalizer_does_not_mutate_inputs_and_returns_frozen_records() -> None:
    source = _at(1, slug="positive-source")
    state = CollaborativeSourceState(
        positive_sources=(source,),
        saved_game_slugs=("saved-source",),
        disliked_slugs=("blocked-source",),
    )
    snapshot = (
        state.positive_sources,
        state.saved_game_slugs,
        state.disliked_slugs,
    )

    result = canonicalize_collaborative_query_sources(state)

    assert (
        state.positive_sources,
        state.saved_game_slugs,
        state.disliked_slugs,
    ) == snapshot
    assert state.positive_sources[0] is source
    with pytest.raises(FrozenInstanceError):
        result.sources = ()
    with pytest.raises(FrozenInstanceError):
        result.sources[0].kind = "rating"
