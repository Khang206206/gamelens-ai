from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

import numpy as np
from scipy import sparse

from gamelens_recommender.artifacts import LoadedArtifact
from gamelens_recommender.collaborative import (
    CollaborativeScoringError,
    CollaborativeSourceState,
    canonicalize_collaborative_query_sources,
)
from gamelens_recommender.config import SCORE_SCALE
from gamelens_recommender.ranking import (
    MAX_EXACT_BASE_CANDIDATES,
    ContentRanker,
    InsufficientContextError,
    contribution,
    quantize,
)
from gamelens_recommender.schemas import (
    SLUG_PATTERN,
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

AffinityMaterializationErrorCode = Literal[
    "materialization_input_invalid",
    "materialization_artifact_incompatible",
]


class AffinityMaterializationError(ValueError):
    def __init__(self, code: AffinityMaterializationErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class AffinityCandidateScore:
    slug: str
    affinity_score_units: int


@dataclass(frozen=True)
class AffinityMaterializationResult:
    profile_active: bool
    candidates: tuple[AffinityCandidateScore, ...]


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
        sources = tuple(
            source
            for value in feedback
            if (source := _positive_source(value, self.config)) is not None
        )
        source_by_slug = {source.game_slug: source for source in sources}
        canonical = canonicalize_collaborative_query_sources(
            CollaborativeSourceState(
                positive_sources=sources,
                disliked_slugs=tuple(
                    value.game_slug for value in feedback if value.reaction == "disliked"
                ),
            )
        )
        return tuple(source_by_slug[source.game_slug] for source in canonical.sources)

    def _validate_canonical_positive_sources(
        self,
        positive_sources: tuple[PositiveFeedbackSource, ...],
    ) -> None:
        if type(positive_sources) is not tuple:
            raise AffinityMaterializationError(
                "materialization_input_invalid",
                "Positive affinity sources must be an immutable tuple",
            )
        try:
            canonical = canonicalize_collaborative_query_sources(
                CollaborativeSourceState(positive_sources=positive_sources)
            )
        except CollaborativeScoringError as error:
            raise AffinityMaterializationError(
                "materialization_input_invalid",
                "Positive affinity sources are invalid",
            ) from error
        actual = tuple((source.game_slug, source.kind) for source in positive_sources)
        expected = tuple((source.game_slug, source.kind) for source in canonical.sources)
        if actual != expected:
            raise AffinityMaterializationError(
                "materialization_input_invalid",
                "Positive affinity sources must be canonical",
            )
        if any(source.game_slug not in self.artifact.slug_to_row for source in positive_sources):
            raise AffinityMaterializationError(
                "materialization_artifact_incompatible",
                "Positive affinity source is not present in the content artifact",
            )

    @staticmethod
    def _canonical_exact_candidate_slugs(candidate_slugs: tuple[str, ...]) -> tuple[str, ...]:
        if type(candidate_slugs) is not tuple:
            raise AffinityMaterializationError(
                "materialization_input_invalid",
                "Exact affinity candidate slugs must be an immutable tuple",
            )
        if len(candidate_slugs) > MAX_EXACT_BASE_CANDIDATES:
            raise AffinityMaterializationError(
                "materialization_input_invalid",
                "Exact affinity candidate count exceeds the materialization limit",
            )
        if any(
            type(slug) is not str or SLUG_PATTERN.fullmatch(slug) is None
            for slug in candidate_slugs
        ):
            raise AffinityMaterializationError(
                "materialization_input_invalid",
                "Exact affinity candidate slugs must be canonical",
            )
        if len(candidate_slugs) != len(set(candidate_slugs)):
            raise AffinityMaterializationError(
                "materialization_input_invalid",
                "Exact affinity candidate slugs must be distinct",
            )
        return tuple(sorted(candidate_slugs))

    def materialize_affinity_candidates(
        self,
        positive_sources: tuple[PositiveFeedbackSource, ...],
        candidate_slugs: tuple[str, ...],
    ) -> AffinityMaterializationResult:
        self._validate_canonical_positive_sources(positive_sources)
        canonical_slugs = self._canonical_exact_candidate_slugs(candidate_slugs)
        if any(slug not in self.artifact.slug_to_row for slug in canonical_slugs):
            raise AffinityMaterializationError(
                "materialization_artifact_incompatible",
                "Exact affinity candidate is not present in the content artifact",
            )
        if not positive_sources:
            return AffinityMaterializationResult(
                profile_active=False,
                candidates=tuple(
                    AffinityCandidateScore(slug=slug, affinity_score_units=0)
                    for slug in canonical_slugs
                ),
            )
        if not canonical_slugs:
            return AffinityMaterializationResult(profile_active=True, candidates=())

        source_rows = [self.artifact.slug_to_row[source.game_slug] for source in positive_sources]
        profile = _normalize_profile(
            sparse.csr_matrix(self.artifact.matrix[source_rows].mean(axis=0))
        )
        candidate_rows = tuple(self.artifact.slug_to_row[slug] for slug in canonical_slugs)
        affinities = (self.artifact.matrix[list(candidate_rows)] @ profile.T).toarray().ravel()
        return AffinityMaterializationResult(
            profile_active=True,
            candidates=tuple(
                AffinityCandidateScore(
                    slug=slug,
                    affinity_score_units=quantize(float(affinity)),
                )
                for slug, affinity in zip(canonical_slugs, affinities, strict=True)
            ),
        )

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

        affinity_profile_active = False
        affinity_by_slug: dict[str, int] = {}
        candidate_slugs = tuple(candidate.slug for candidate in base_candidates)
        for start in range(0, len(candidate_slugs), MAX_EXACT_BASE_CANDIDATES):
            affinity_result = self.materialize_affinity_candidates(
                positive_sources,
                candidate_slugs[start : start + MAX_EXACT_BASE_CANDIDATES],
            )
            affinity_profile_active = affinity_result.profile_active
            affinity_by_slug.update(
                (candidate.slug, candidate.affinity_score_units)
                for candidate in affinity_result.candidates
            )

        source_slugs = {source.game_slug for source in positive_sources}
        excluded = disliked | source_slugs
        played = {value.game_slug for value in feedback if value.played}
        scored: list[_ScoredPersonalizedCandidate] = []
        for candidate in base_candidates:
            if candidate.slug in excluded:
                continue
            if not affinity_profile_active:
                base_weight_units = SCORE_SCALE
                affinity_weight_units = 0
                affinity_score_units = 0
            else:
                base_weight_units = self.config.base_weight_units
                affinity_weight_units = self.config.affinity_weight_units
                affinity_score_units = affinity_by_slug[candidate.slug]
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
            reasons = ("feedback_affinity",) if affinity_profile_active else ()
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
