from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import numpy as np
from scipy import sparse

from gamelens_recommender.artifacts import LoadedArtifact
from gamelens_recommender.config import RANKING_CONFIG, SCORE_SCALE, RankingConfig
from gamelens_recommender.features import build_preference_document
from gamelens_recommender.schemas import (
    BaseCandidateScore,
    RankedRecommendation,
    RankingResult,
    RecommendationEvidence,
    ScoreComponent,
    SimilarSelectedGame,
    TaxonomyValue,
    UserContext,
)


class InsufficientContextError(ValueError):
    pass


def quantize(value: float) -> int:
    bounded = min(1.0, max(0.0, float(value)))
    return int(
        (Decimal(str(bounded)) * Decimal(SCORE_SCALE)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def contribution(raw_units: int, weight_units: int) -> int:
    return (raw_units * weight_units + SCORE_SCALE // 2) // SCORE_SCALE


def _normalized(vector: sparse.spmatrix) -> sparse.csr_matrix:
    result = vector.tocsr()
    norm = float(np.sqrt(result.multiply(result).sum()))
    if not np.isfinite(norm) or norm <= 0:
        raise InsufficientContextError("The selected context has no usable content signal")
    return result / norm


class ContentRanker:
    def __init__(self, artifact: LoadedArtifact, config: RankingConfig = RANKING_CONFIG) -> None:
        config.validate()
        self.artifact = artifact
        self.config = config

    def _user_vector(self, context: UserContext) -> sparse.csr_matrix:
        vectors: list[tuple[sparse.csr_matrix, int]] = []
        has_taxonomy = bool(context.preferred_genres or context.preferred_tags)
        if context.selected_game_slugs:
            rows = [self.artifact.slug_to_row[slug] for slug in context.selected_game_slugs]
            centroid = sparse.csr_matrix(self.artifact.matrix[rows].mean(axis=0))
            weight = self.config.selected_game_weight_units if has_taxonomy else SCORE_SCALE
            vectors.append((_normalized(centroid), weight))
        if has_taxonomy:
            document = build_preference_document(context.preferred_genres, context.preferred_tags)
            preference = self.artifact.vectorizer.transform([document]).tocsr()
            weight = (
                self.config.taxonomy_weight_units if context.selected_game_slugs else SCORE_SCALE
            )
            vectors.append((_normalized(preference), weight))
        if not vectors:
            raise InsufficientContextError("At least one content signal is required")
        combined = sum(
            (vector * (weight / SCORE_SCALE) for vector, weight in vectors),
            start=sparse.csr_matrix((1, self.artifact.matrix.shape[1])),
        )
        return _normalized(combined)

    def score_candidates(self, context: UserContext) -> tuple[BaseCandidateScore, ...]:
        context.validate()
        missing = [
            slug for slug in context.selected_game_slugs if slug not in self.artifact.slug_to_row
        ]
        if missing:
            raise ValueError("Selected game is not present in the artifact")
        user_vector = self._user_vector(context)
        similarities = (self.artifact.matrix @ user_vector.T).toarray().ravel()
        selected = set(context.selected_game_slugs)
        platform_slugs = set(context.preferred_platforms)
        candidates: list[BaseCandidateScore] = []
        for row, item in enumerate(self.artifact.items):
            if item.slug in selected:
                continue
            content_units = quantize(float(similarities[row]))
            if content_units == 0:
                continue
            platform_match_count = sum(value.slug in platform_slugs for value in item.platforms)
            platform_raw = platform_match_count / len(platform_slugs) if platform_slugs else 0
            platform_units = quantize(platform_raw)
            popularity_units = quantize(float(self.artifact.popularity[row]))
            final_units = sum(
                contribution(raw, weight)
                for raw, weight in (
                    (content_units, self.config.content_weight_units),
                    (platform_units, self.config.platform_weight_units),
                    (popularity_units, self.config.popularity_weight_units),
                )
            )
            candidates.append(
                BaseCandidateScore(
                    slug=item.slug,
                    base_score_units=final_units,
                    content_score_units=content_units,
                    platform_score_units=platform_units,
                    popularity_score_units=popularity_units,
                )
            )
        candidates.sort(
            key=lambda value: (
                -value.base_score_units,
                -value.content_score_units,
                -value.popularity_score_units,
                value.slug,
            )
        )
        return tuple(candidates)

    def materialize_candidate(
        self,
        candidate: BaseCandidateScore,
        context: UserContext,
        *,
        rank: int,
    ) -> RankedRecommendation:
        row = self.artifact.slug_to_row[candidate.slug]
        item = self.artifact.items[row]
        platform_slugs = set(context.preferred_platforms)
        platform_matches = tuple(value for value in item.platforms if value.slug in platform_slugs)
        components = tuple(
            ScoreComponent(
                name=name,
                raw_units=raw,
                weight_units=weight,
                contribution_units=contribution(raw, weight),
            )
            for name, raw, weight in (
                ("content", candidate.content_score_units, self.config.content_weight_units),
                ("platform", candidate.platform_score_units, self.config.platform_weight_units),
                (
                    "popularity",
                    candidate.popularity_score_units,
                    self.config.popularity_weight_units,
                ),
            )
        )
        matching_genres = tuple(
            value for value in item.genres if value.slug in context.preferred_genres
        )
        matching_tags = tuple(value for value in item.tags if value.slug in context.preferred_tags)
        similar_selected: list[SimilarSelectedGame] = []
        for slug in context.selected_game_slugs:
            selected_row = self.artifact.slug_to_row[slug]
            similarity = float(
                self.artifact.matrix[row].multiply(self.artifact.matrix[selected_row]).sum()
            )
            units = quantize(similarity)
            if units:
                similar_selected.append(
                    SimilarSelectedGame(
                        slug=slug,
                        title=self.artifact.items[selected_row].title,
                        similarity_units=units,
                    )
                )
        similar_selected.sort(key=lambda value: (-value.similarity_units, value.slug))
        evidence = RecommendationEvidence(
            matching_genres=matching_genres,
            matching_tags=matching_tags,
            preferred_platforms=platform_matches,
            similar_selected_games=tuple(similar_selected[:3]),
            popularity_percentile_units=candidate.popularity_score_units,
        )
        summary, reasons = _explain(evidence)
        return RankedRecommendation(
            slug=item.slug,
            rank=rank,
            final_score_units=candidate.base_score_units,
            components=components,
            evidence=evidence,
            explanation_summary=summary,
            explanation_reasons=reasons,
        )

    def rank(self, context: UserContext) -> RankingResult:
        candidates = self.score_candidates(context)
        ranked = tuple(
            self.materialize_candidate(candidate, context, rank=rank)
            for rank, candidate in enumerate(candidates[: context.top_k], start=1)
        )
        return RankingResult(
            items=ranked,
            reason="recommendations" if ranked else "no_content_support",
        )


def _names(values: tuple[TaxonomyValue, ...]) -> str:
    return ", ".join(value.name for value in values[:3])


def _explain(evidence: RecommendationEvidence) -> tuple[str, tuple[str, ...]]:
    reasons: list[str] = []
    if evidence.similar_selected_games:
        names = ", ".join(value.title for value in evidence.similar_selected_games[:2])
        reasons.append(f"Its content profile is similar to {names}.")
    if evidence.matching_genres:
        reasons.append(f"It matches your preferred genres: {_names(evidence.matching_genres)}.")
    if evidence.matching_tags:
        reasons.append(f"It matches your preferred tags: {_names(evidence.matching_tags)}.")
    if evidence.preferred_platforms:
        reasons.append(
            f"It is available on preferred platforms: {_names(evidence.preferred_platforms)}."
        )
    if evidence.popularity_percentile_units >= 700_000:
        reasons.append("Its catalog rating and popularity signals provide supporting evidence.")
    if not reasons:
        reasons.append("Its catalog content is related to the context you selected.")
    return reasons[0], tuple(reasons)
