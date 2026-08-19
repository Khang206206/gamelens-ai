from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import numpy as np
from scipy import sparse

from gamelens_recommender.artifacts import LoadedArtifact
from gamelens_recommender.config import SCORE_SCALE
from gamelens_recommender.ranking import (
    ContentRanker,
    InsufficientContextError,
    contribution,
    quantize,
)
from gamelens_recommender.schemas import (
    ActiveGameFeedback,
    BaseCandidateScore,
    FeedbackPolicyIdentity,
    PersonalizedRankingResult,
    PersonalizedRecommendation,
    PositiveFeedbackSource,
    UserContext,
)


@dataclass(frozen=True)
class FeedbackPolicyConfig:
    name: str = "gamelens-feedback-adjustment"
    version: str = "1.0.0"
    positive_rating_threshold: Decimal = Decimal("7")
    max_positive_sources: int = 5
    base_weight_units: int = 900_000
    affinity_weight_units: int = 100_000
    played_factor_units: int = 500_000
    tie_break: tuple[str, ...] = (
        "final_score_desc",
        "pre_played_score_desc",
        "base_score_desc",
        "affinity_score_desc",
        "content_score_desc",
        "popularity_score_desc",
        "slug_asc",
    )

    def validate(self) -> None:
        if (self.name, self.version) != ("gamelens-feedback-adjustment", "1.0.0"):
            raise ValueError("Feedback policy identity is unsupported")
        if (
            not isinstance(self.positive_rating_threshold, Decimal)
            or not self.positive_rating_threshold.is_finite()
            or not Decimal("0") <= self.positive_rating_threshold <= Decimal("10")
        ):
            raise ValueError("Positive rating threshold must be a finite value from 0 to 10")
        if type(self.max_positive_sources) is not int or self.max_positive_sources <= 0:
            raise ValueError("Positive feedback source cap must be positive")
        weights = (self.base_weight_units, self.affinity_weight_units)
        if any(type(weight) is not int or weight < 0 for weight in weights):
            raise ValueError("Feedback blend weights must be non-negative integers")
        if sum(weights) != SCORE_SCALE:
            raise ValueError("Feedback blend weights must sum to the score scale")
        if (
            type(self.played_factor_units) is not int
            or not 0 <= self.played_factor_units <= SCORE_SCALE
        ):
            raise ValueError("Played factor must be bounded by the score scale")
        if self.tie_break != (
            "final_score_desc",
            "pre_played_score_desc",
            "base_score_desc",
            "affinity_score_desc",
            "content_score_desc",
            "popularity_score_desc",
            "slug_asc",
        ):
            raise ValueError("Feedback policy tie-break is unsupported")
        if (
            self.positive_rating_threshold,
            self.max_positive_sources,
            self.base_weight_units,
            self.affinity_weight_units,
            self.played_factor_units,
        ) != (Decimal("7"), 5, 900_000, 100_000, 500_000):
            raise ValueError("Feedback configuration does not match policy version 1.0.0")


FEEDBACK_POLICY_CONFIG = FeedbackPolicyConfig()


@dataclass(frozen=True)
class _ScoredPersonalizedCandidate:
    base: BaseCandidateScore
    base_weight_units: int
    base_contribution_units: int
    affinity_score_units: int
    affinity_weight_units: int
    affinity_contribution_units: int
    pre_played_score_units: int
    played_factor_units: int
    played_delta_units: int
    final_score_units: int
    adjustment_reasons: tuple[str, ...]


def _normalize_profile(vector: sparse.spmatrix) -> sparse.csr_matrix:
    result = vector.tocsr()
    norm = float(np.sqrt(result.multiply(result).sum()))
    if not np.isfinite(norm) or norm <= 0:
        raise ValueError("Positive feedback profile has no usable content signal")
    return result / norm


def _positive_source(
    feedback: ActiveGameFeedback,
    config: FeedbackPolicyConfig,
) -> PositiveFeedbackSource | None:
    if feedback.reaction == "liked":
        if feedback.reaction_occurred_at is None:
            raise RuntimeError("Validated liked feedback has no timestamp")
        return PositiveFeedbackSource(
            game_slug=feedback.game_slug,
            kind="liked",
            occurred_at=feedback.reaction_occurred_at,
        )
    if (
        feedback.reaction is None
        and feedback.rating is not None
        and feedback.rating >= config.positive_rating_threshold
    ):
        if feedback.rating_occurred_at is None:
            raise RuntimeError("Validated positive rating has no timestamp")
        return PositiveFeedbackSource(
            game_slug=feedback.game_slug,
            kind="rating",
            occurred_at=feedback.rating_occurred_at,
        )
    return None


class FeedbackRanker:
    def __init__(
        self,
        artifact: LoadedArtifact,
        config: FeedbackPolicyConfig = FEEDBACK_POLICY_CONFIG,
        *,
        content_ranker: ContentRanker | None = None,
    ) -> None:
        config.validate()
        if content_ranker is not None and content_ranker.artifact is not artifact:
            raise ValueError("Content and feedback rankers must use the same artifact")
        self.artifact = artifact
        self.config = config
        self.content_ranker = content_ranker or ContentRanker(artifact)

    @property
    def identity(self) -> FeedbackPolicyIdentity:
        return FeedbackPolicyIdentity(name=self.config.name, version=self.config.version)

    def _validate_feedback(self, feedback: tuple[ActiveGameFeedback, ...]) -> None:
        if type(feedback) is not tuple:
            raise ValueError("Feedback input must be an immutable tuple")
        if len(feedback) > len(self.artifact.items):
            raise ValueError("Feedback input exceeds the artifact catalog bound")
        for value in feedback:
            if not isinstance(value, ActiveGameFeedback):
                raise ValueError("Feedback input contains an invalid value")
            value.validate()
        slugs = [value.game_slug for value in feedback]
        if len(slugs) != len(set(slugs)):
            raise ValueError("Feedback game slugs must be distinct")
        if any(slug not in self.artifact.slug_to_row for slug in slugs):
            raise ValueError("Feedback game is not present in the artifact")

    def _positive_sources(
        self,
        feedback: tuple[ActiveGameFeedback, ...],
    ) -> tuple[PositiveFeedbackSource, ...]:
        sources = [
            source
            for value in feedback
            if (source := _positive_source(value, self.config)) is not None
        ]
        sources.sort(key=lambda value: value.game_slug)
        sources.sort(key=lambda value: value.occurred_at, reverse=True)
        return tuple(sources[: self.config.max_positive_sources])

    def rank(
        self,
        context: UserContext,
        feedback: tuple[ActiveGameFeedback, ...],
    ) -> PersonalizedRankingResult:
        context.validate()
        missing_context = [
            slug for slug in context.selected_game_slugs if slug not in self.artifact.slug_to_row
        ]
        if missing_context:
            raise ValueError("Selected game is not present in the artifact")
        self._validate_feedback(feedback)

        disliked = {value.game_slug for value in feedback if value.reaction == "disliked"}
        effective_context = UserContext(
            selected_game_slugs=tuple(
                slug for slug in context.selected_game_slugs if slug not in disliked
            ),
            preferred_genres=context.preferred_genres,
            preferred_tags=context.preferred_tags,
            preferred_platforms=context.preferred_platforms,
            top_k=context.top_k,
        )
        if not (
            effective_context.selected_game_slugs
            or effective_context.preferred_genres
            or effective_context.preferred_tags
        ):
            raise InsufficientContextError(
                "Disliked games leave the saved context without a content signal"
            )

        positive_sources = self._positive_sources(feedback)
        base_candidates = self.content_ranker.score_candidates(effective_context)
        if not base_candidates:
            return PersonalizedRankingResult(
                items=(),
                reason="no_content_support",
                policy=self.identity,
                positive_sources=positive_sources,
            )

        affinity_by_row: np.ndarray | None = None
        if positive_sources:
            source_rows = [
                self.artifact.slug_to_row[source.game_slug] for source in positive_sources
            ]
            profile = _normalize_profile(
                sparse.csr_matrix(self.artifact.matrix[source_rows].mean(axis=0))
            )
            affinity_by_row = (self.artifact.matrix @ profile.T).toarray().ravel()

        source_slugs = {source.game_slug for source in positive_sources}
        excluded = disliked | source_slugs
        played = {value.game_slug for value in feedback if value.played}
        scored: list[_ScoredPersonalizedCandidate] = []
        for candidate in base_candidates:
            if candidate.slug in excluded:
                continue
            if affinity_by_row is None:
                base_weight_units = SCORE_SCALE
                affinity_weight_units = 0
                affinity_score_units = 0
            else:
                base_weight_units = self.config.base_weight_units
                affinity_weight_units = self.config.affinity_weight_units
                row = self.artifact.slug_to_row[candidate.slug]
                affinity_score_units = quantize(float(affinity_by_row[row]))
            base_contribution_units = contribution(
                candidate.base_score_units,
                base_weight_units,
            )
            affinity_contribution_units = contribution(
                affinity_score_units,
                affinity_weight_units,
            )
            pre_played_score_units = base_contribution_units + affinity_contribution_units
            is_played = candidate.slug in played
            played_factor_units = self.config.played_factor_units if is_played else SCORE_SCALE
            final_score_units = contribution(pre_played_score_units, played_factor_units)
            reasons = ("feedback_affinity",) if affinity_by_row is not None else ()
            if is_played:
                reasons += ("played_adjustment",)
            scored.append(
                _ScoredPersonalizedCandidate(
                    base=candidate,
                    base_weight_units=base_weight_units,
                    base_contribution_units=base_contribution_units,
                    affinity_score_units=affinity_score_units,
                    affinity_weight_units=affinity_weight_units,
                    affinity_contribution_units=affinity_contribution_units,
                    pre_played_score_units=pre_played_score_units,
                    played_factor_units=played_factor_units,
                    played_delta_units=final_score_units - pre_played_score_units,
                    final_score_units=final_score_units,
                    adjustment_reasons=reasons,
                )
            )

        scored.sort(
            key=lambda value: (
                -value.final_score_units,
                -value.pre_played_score_units,
                -value.base.base_score_units,
                -value.affinity_score_units,
                -value.base.content_score_units,
                -value.base.popularity_score_units,
                value.base.slug,
            )
        )
        selected = scored[: effective_context.top_k]
        items: list[PersonalizedRecommendation] = []
        for rank, value in enumerate(selected, start=1):
            base = self.content_ranker.materialize_candidate(
                value.base,
                effective_context,
                rank=rank,
            )
            items.append(
                PersonalizedRecommendation(
                    slug=base.slug,
                    rank=rank,
                    base_score_units=base.final_score_units,
                    base_components=base.components,
                    base_evidence=base.evidence,
                    explanation_summary=base.explanation_summary,
                    explanation_reasons=base.explanation_reasons,
                    base_weight_units=value.base_weight_units,
                    base_contribution_units=value.base_contribution_units,
                    affinity_score_units=value.affinity_score_units,
                    affinity_weight_units=value.affinity_weight_units,
                    affinity_contribution_units=value.affinity_contribution_units,
                    pre_played_score_units=value.pre_played_score_units,
                    played_factor_units=value.played_factor_units,
                    played_delta_units=value.played_delta_units,
                    final_score_units=value.final_score_units,
                    adjustment_reasons=value.adjustment_reasons,
                )
            )
        return PersonalizedRankingResult(
            items=tuple(items),
            reason="recommendations" if items else "no_eligible_candidates",
            policy=self.identity,
            positive_sources=positive_sources,
        )
