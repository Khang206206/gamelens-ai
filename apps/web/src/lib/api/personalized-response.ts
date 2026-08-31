import type { components } from "@/lib/api/generated";
import { ApiClientError } from "@/lib/api/errors";

type Schemas = components["schemas"];
type CollaborativeModelIdentity = Schemas["CollaborativeModelIdentityResponse"];
type CollaborativeSourceEdge = Schemas["CollaborativeSourceEdgeResponse"];
type EvidenceValue = Schemas["EvidenceValue"];
type GameSummary = Schemas["GameSummary"];
type RecommendationEvidence = Schemas["RecommendationEvidenceResponse"];
type RecommendationExplanation = Schemas["RecommendationExplanationResponse"];
type SimilarSelectedGame = Schemas["SimilarSelectedGameResponse"];
type Stage5Item = Schemas["Stage5PersonalizedRecommendationItem"];
type Stage5Policy = Schemas["Stage5PolicyIdentity"];
type Stage5PositiveSource = Schemas["Stage5PositiveFeedbackSourceResponse"];
type Stage5ScoreComponent = Schemas["Stage5ScoreComponentResponse"];
type TaxonomyItem = Schemas["TaxonomyItem"];

export type Stage5PersonalizedRecommendationResponse =
  Schemas["Stage5PersonalizedRecommendationResponse"];

function defineKeys<T>() {
  return <const K extends readonly (keyof T)[]>(
    keys: K & (Exclude<keyof T, K[number]> extends never ? unknown : never),
  ): K => keys;
}

function defineLiterals<T extends string>() {
  return <const V extends readonly T[]>(
    values: V & (Exclude<T, V[number]> extends never ? unknown : never),
  ): V => values;
}

const COLLABORATIVE_MODEL_KEYS = defineKeys<CollaborativeModelIdentity>()([
  "name",
  "version",
  "interaction_fingerprint",
  "scoring_policy",
]);
const COLLABORATIVE_SOURCE_EDGE_KEYS = defineKeys<CollaborativeSourceEdge>()([
  "source_game_slug",
  "source_kind",
  "similarity_score",
  "pair_support",
]);
const EVIDENCE_VALUE_KEYS = defineKeys<EvidenceValue>()(["slug", "name"]);
const GAME_SUMMARY_KEYS = defineKeys<GameSummary>()([
  "id",
  "title",
  "slug",
  "release_date",
  "developer",
  "publisher",
  "average_rating",
  "rating_count",
  "popularity_score",
  "genres",
  "tags",
  "platforms",
  "cover_image_url",
]);
const RECOMMENDATION_EVIDENCE_KEYS = defineKeys<RecommendationEvidence>()([
  "matching_genres",
  "matching_tags",
  "preferred_platforms",
  "similar_selected_games",
  "popularity_score",
]);
const RECOMMENDATION_EXPLANATION_KEYS = defineKeys<RecommendationExplanation>()([
  "summary",
  "reasons",
]);
const SIMILAR_SELECTED_GAME_KEYS = defineKeys<SimilarSelectedGame>()([
  "slug",
  "title",
  "similarity_score",
]);
const STAGE_5_ITEM_KEYS = defineKeys<Stage5Item>()([
  "rank",
  "game",
  "base_ranking_score",
  "base_components",
  "base_weight",
  "base_contribution",
  "feedback_affinity_score",
  "feedback_affinity_weight",
  "feedback_affinity_contribution",
  "pre_played_score",
  "played_factor",
  "played_delta",
  "ranking_score",
  "adjustment_reasons",
  "evidence",
  "explanation",
  "candidate_origin",
  "collaborative_supported",
  "collaborative_score",
  "collaborative_weight",
  "collaborative_contribution",
  "collaborative_item_support",
  "collaborative_source_edges",
]);
const STAGE_5_POLICY_KEYS = defineKeys<Stage5Policy>()(["name", "version"]);
const STAGE_5_POSITIVE_SOURCE_KEYS = defineKeys<Stage5PositiveSource>()([
  "game_slug",
  "kind",
]);
const STAGE_5_RESPONSE_KEYS = defineKeys<Stage5PersonalizedRecommendationResponse>()([
  "generation_id",
  "model_name",
  "model_version",
  "data_fingerprint",
  "policy",
  "response_reason",
  "requested_top_k",
  "positive_feedback_sources",
  "items",
  "ranking_mode",
  "fallback_reason",
  "hybrid_policy",
  "collaborative_model",
]);
const STAGE_5_SCORE_COMPONENT_KEYS = defineKeys<Stage5ScoreComponent>()([
  "name",
  "raw_score",
  "weight",
  "contribution",
]);
const TAXONOMY_ITEM_KEYS = defineKeys<TaxonomyItem>()(["id", "name", "slug"]);

const ADJUSTMENT_REASONS = defineLiterals<Stage5Item["adjustment_reasons"][number]>()([
  "feedback_affinity",
  "collaborative_similarity",
  "played_adjustment",
]);
const CANDIDATE_ORIGINS = defineLiterals<Stage5Item["candidate_origin"]>()([
  "content",
  "collaborative",
  "both",
]);
const COLLABORATIVE_SOURCE_KINDS = defineLiterals<
  CollaborativeSourceEdge["source_kind"]
>()(["liked", "rating", "saved_game"]);
const FALLBACK_REASONS = defineLiterals<
  NonNullable<Stage5PersonalizedRecommendationResponse["fallback_reason"]>
>()([
  "not_configured",
  "fixture_not_allowed",
  "insufficient_data",
  "artifact_missing",
  "artifact_corrupt",
  "artifact_incompatible",
  "artifact_stale",
  "privacy_invalid",
  "artifact_expired",
  "catalog_stale",
  "artifact_retired",
  "no_query_sources",
  "no_supported_sources",
  "no_candidate_edges",
  "no_eligible_candidates",
]);
const POSITIVE_SOURCE_KINDS = defineLiterals<Stage5PositiveSource["kind"]>()([
  "liked",
  "rating",
]);
const RANKING_MODES = defineLiterals<
  Stage5PersonalizedRecommendationResponse["ranking_mode"]
>()(["hybrid", "stage_4_fallback"]);
const RESPONSE_REASONS = defineLiterals<
  Stage5PersonalizedRecommendationResponse["response_reason"]
>()(["recommendations", "no_content_support", "no_eligible_candidates"]);
const SCORE_COMPONENT_NAMES = defineLiterals<Stage5ScoreComponent["name"]>()([
  "content",
  "platform",
  "popularity",
]);

function hasExactKeys<const K extends readonly string[]>(
  value: unknown,
  keys: K,
): value is Record<K[number], unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const actualKeys = Object.keys(value);
  return (
    actualKeys.length === keys.length &&
    keys.every((key) => Object.prototype.hasOwnProperty.call(value, key))
  );
}

function isArrayOf<T>(
  value: unknown,
  predicate: (item: unknown) => item is T,
  maximumLength?: number,
): value is T[] {
  return (
    Array.isArray(value) &&
    (maximumLength === undefined || value.length <= maximumLength) &&
    value.every(predicate)
  );
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isIntegerBetween(
  value: unknown,
  minimum: number,
  maximum: number,
): value is number {
  return Number.isInteger(value) && Number(value) >= minimum && Number(value) <= maximum;
}

function isOneOf<const T extends string>(
  value: unknown,
  allowed: readonly T[],
): value is T {
  return typeof value === "string" && allowed.includes(value as T);
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isFixedPointBetween(
  value: unknown,
  minimum: number,
  maximum: number,
): value is number {
  if (!isFiniteNumber(value) || value < minimum || value > maximum) return false;
  const scaled = value * 1_000_000;
  return Math.abs(scaled - Math.round(scaled)) <= 0.000001;
}

function isIdentityPart(value: unknown): value is string {
  return (
    typeof value === "string" && value.length <= 100 && /^\S(?:[^\r\n]*\S)?$/.test(value)
  );
}

function isCanonicalSlug(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length <= 220 &&
    /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value)
  );
}

function isFingerprint(value: unknown): value is string {
  return typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
}

function isTaxonomyItem(value: unknown): value is TaxonomyItem {
  return (
    hasExactKeys(value, TAXONOMY_ITEM_KEYS) &&
    Number.isInteger(value.id) &&
    typeof value.name === "string" &&
    typeof value.slug === "string"
  );
}

function isGameSummary(value: unknown): value is GameSummary {
  if (!hasExactKeys(value, GAME_SUMMARY_KEYS)) return false;
  return (
    Number.isInteger(value.id) &&
    typeof value.title === "string" &&
    typeof value.slug === "string" &&
    isNullableString(value.release_date) &&
    isNullableString(value.developer) &&
    isNullableString(value.publisher) &&
    (value.average_rating === null || isFiniteNumber(value.average_rating)) &&
    Number.isInteger(value.rating_count) &&
    isFiniteNumber(value.popularity_score) &&
    isArrayOf(value.genres, isTaxonomyItem) &&
    isArrayOf(value.tags, isTaxonomyItem) &&
    isArrayOf(value.platforms, isTaxonomyItem) &&
    isNullableString(value.cover_image_url)
  );
}

function isEvidenceValue(value: unknown): value is EvidenceValue {
  return (
    hasExactKeys(value, EVIDENCE_VALUE_KEYS) &&
    typeof value.slug === "string" &&
    typeof value.name === "string"
  );
}

function isSimilarSelectedGame(value: unknown): value is SimilarSelectedGame {
  return (
    hasExactKeys(value, SIMILAR_SELECTED_GAME_KEYS) &&
    typeof value.slug === "string" &&
    typeof value.title === "string" &&
    isFiniteNumber(value.similarity_score)
  );
}

function isRecommendationEvidence(value: unknown): value is RecommendationEvidence {
  return (
    hasExactKeys(value, RECOMMENDATION_EVIDENCE_KEYS) &&
    isArrayOf(value.matching_genres, isEvidenceValue) &&
    isArrayOf(value.matching_tags, isEvidenceValue) &&
    isArrayOf(value.preferred_platforms, isEvidenceValue) &&
    isArrayOf(value.similar_selected_games, isSimilarSelectedGame) &&
    isFiniteNumber(value.popularity_score)
  );
}

function isRecommendationExplanation(value: unknown): value is RecommendationExplanation {
  return (
    hasExactKeys(value, RECOMMENDATION_EXPLANATION_KEYS) &&
    typeof value.summary === "string" &&
    isArrayOf(value.reasons, (reason): reason is string => typeof reason === "string")
  );
}

function isStage5Policy(value: unknown): value is Stage5Policy {
  return (
    hasExactKeys(value, STAGE_5_POLICY_KEYS) &&
    isIdentityPart(value.name) &&
    isIdentityPart(value.version)
  );
}

function isCollaborativeModelIdentity(
  value: unknown,
): value is CollaborativeModelIdentity {
  return (
    hasExactKeys(value, COLLABORATIVE_MODEL_KEYS) &&
    isIdentityPart(value.name) &&
    isIdentityPart(value.version) &&
    isFingerprint(value.interaction_fingerprint) &&
    isStage5Policy(value.scoring_policy)
  );
}

function isStage5PositiveSource(value: unknown): value is Stage5PositiveSource {
  return (
    hasExactKeys(value, STAGE_5_POSITIVE_SOURCE_KEYS) &&
    isCanonicalSlug(value.game_slug) &&
    isOneOf(value.kind, POSITIVE_SOURCE_KINDS)
  );
}

function isCollaborativeSourceEdge(value: unknown): value is CollaborativeSourceEdge {
  return (
    hasExactKeys(value, COLLABORATIVE_SOURCE_EDGE_KEYS) &&
    isCanonicalSlug(value.source_game_slug) &&
    isOneOf(value.source_kind, COLLABORATIVE_SOURCE_KINDS) &&
    isFixedPointBetween(value.similarity_score, 0.000001, 1) &&
    isIntegerBetween(value.pair_support, 2, 500_000)
  );
}

function isStage5ScoreComponent(value: unknown): value is Stage5ScoreComponent {
  return (
    hasExactKeys(value, STAGE_5_SCORE_COMPONENT_KEYS) &&
    isOneOf(value.name, SCORE_COMPONENT_NAMES) &&
    isFixedPointBetween(value.raw_score, 0, 1) &&
    isFixedPointBetween(value.weight, 0, 1) &&
    isFixedPointBetween(value.contribution, 0, 1)
  );
}

function isStage5Item(value: unknown): value is Stage5Item {
  if (!hasExactKeys(value, STAGE_5_ITEM_KEYS)) return false;
  if (
    !isIntegerBetween(value.rank, 1, 20) ||
    !isGameSummary(value.game) ||
    !isFixedPointBetween(value.base_ranking_score, 0, 1) ||
    !isArrayOf(value.base_components, isStage5ScoreComponent) ||
    value.base_components.length !== SCORE_COMPONENT_NAMES.length ||
    !value.base_components.every(
      (component, index) => component.name === SCORE_COMPONENT_NAMES[index],
    ) ||
    !isFixedPointBetween(value.base_weight, 0, 1) ||
    !isFixedPointBetween(value.base_contribution, 0, 1) ||
    !isFixedPointBetween(value.feedback_affinity_score, 0, 1) ||
    !isFixedPointBetween(value.feedback_affinity_weight, 0, 1) ||
    !isFixedPointBetween(value.feedback_affinity_contribution, 0, 1) ||
    !isFixedPointBetween(value.pre_played_score, 0, 1) ||
    !isFixedPointBetween(value.played_factor, 0, 1) ||
    !isFixedPointBetween(value.played_delta, -1, 0) ||
    !isFixedPointBetween(value.ranking_score, 0, 1) ||
    !isArrayOf(
      value.adjustment_reasons,
      (reason): reason is Stage5Item["adjustment_reasons"][number] =>
        isOneOf(reason, ADJUSTMENT_REASONS),
      3,
    ) ||
    !isRecommendationEvidence(value.evidence) ||
    !isRecommendationExplanation(value.explanation) ||
    !isOneOf(value.candidate_origin, CANDIDATE_ORIGINS) ||
    typeof value.collaborative_supported !== "boolean" ||
    !isFixedPointBetween(value.collaborative_score, 0, 1) ||
    !isFixedPointBetween(value.collaborative_weight, 0, 1) ||
    !isFixedPointBetween(value.collaborative_contribution, 0, 1) ||
    !(
      value.collaborative_item_support === null ||
      isIntegerBetween(value.collaborative_item_support, 2, 500_000)
    ) ||
    !isArrayOf(value.collaborative_source_edges, isCollaborativeSourceEdge, 10)
  ) {
    return false;
  }

  if (value.collaborative_supported) {
    return (
      value.candidate_origin !== "content" &&
      value.collaborative_score > 0 &&
      value.collaborative_weight > 0 &&
      value.collaborative_item_support !== null &&
      value.collaborative_source_edges.length > 0
    );
  }
  return (
    value.candidate_origin === "content" &&
    value.collaborative_score === 0 &&
    value.collaborative_contribution === 0 &&
    value.collaborative_item_support === null &&
    value.collaborative_source_edges.length === 0
  );
}

function isStage5Response(
  value: unknown,
): value is Stage5PersonalizedRecommendationResponse {
  if (!hasExactKeys(value, STAGE_5_RESPONSE_KEYS)) return false;
  if (
    typeof value.generation_id !== "string" ||
    !/^[0-9a-f]{32}$/.test(value.generation_id) ||
    !isIdentityPart(value.model_name) ||
    !isIdentityPart(value.model_version) ||
    !isFingerprint(value.data_fingerprint) ||
    !isStage5Policy(value.policy) ||
    !isOneOf(value.response_reason, RESPONSE_REASONS) ||
    !isIntegerBetween(value.requested_top_k, 1, 20) ||
    !isArrayOf(value.positive_feedback_sources, isStage5PositiveSource, 5) ||
    !isArrayOf(value.items, isStage5Item, 20) ||
    !isOneOf(value.ranking_mode, RANKING_MODES) ||
    !(
      value.fallback_reason === null || isOneOf(value.fallback_reason, FALLBACK_REASONS)
    ) ||
    !(value.hybrid_policy === null || isStage5Policy(value.hybrid_policy)) ||
    !(
      value.collaborative_model === null ||
      isCollaborativeModelIdentity(value.collaborative_model)
    )
  ) {
    return false;
  }

  if (value.items.length > value.requested_top_k) return false;
  if (value.items.some((item, index) => item.rank !== index + 1)) return false;
  if (new Set(value.items.map((item) => item.game.slug)).size !== value.items.length) {
    return false;
  }
  if (
    new Set(value.positive_feedback_sources.map((source) => source.game_slug)).size !==
    value.positive_feedback_sources.length
  ) {
    return false;
  }

  if (value.ranking_mode === "hybrid") {
    return (
      value.response_reason === "recommendations" &&
      value.items.length > 0 &&
      value.fallback_reason === null &&
      value.hybrid_policy !== null &&
      value.collaborative_model !== null
    );
  }
  return (
    value.fallback_reason !== null &&
    value.hybrid_policy === null &&
    value.collaborative_model === null &&
    value.items.every(
      (item) =>
        !item.collaborative_supported &&
        item.collaborative_weight === 0 &&
        item.collaborative_contribution === 0,
    )
  );
}

export function parseStage5PersonalizedRecommendationResponse(
  value: unknown,
): Stage5PersonalizedRecommendationResponse {
  if (!isStage5Response(value)) {
    throw new ApiClientError({
      kind: "invalid_response",
      status: 200,
      message: "The saved recommendation response did not match the API contract.",
    });
  }
  return value;
}
