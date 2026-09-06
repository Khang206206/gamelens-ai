import {
  expect,
  type APIRequestContext,
  type Page,
  type TestInfo,
} from "@playwright/test";

import type {
  RecommendationResponse,
  PersonalizedRecommendationResponse,
} from "../src/lib/api/client";
import {
  enableSavedPersonalization,
  generateSavedRecommendations,
  savePreferences,
} from "./hybrid-fixture-helpers";

export type BrowserFallbackReason =
  "artifact_missing" | "artifact_corrupt" | "no_supported_sources";

const FALLBACK_COPY: Record<BrowserFallbackReason, RegExp> = {
  artifact_missing: /not available to the server/i,
  artifact_corrupt: /could not be read safely/i,
  no_supported_sources: /no retained aggregate interaction support/i,
};

const SOURCE_BY_REASON: Record<BrowserFallbackReason, { gameId: number; slug: string }> =
  {
    artifact_missing: { gameId: 1, slug: "emberfall-tactics" },
    artifact_corrupt: { gameId: 1, slug: "emberfall-tactics" },
    no_supported_sources: { gameId: 4, slug: "abyssal-signal" },
  };

export function expectedBrowserFallbackReason(): BrowserFallbackReason {
  const value = process.env.E2E_EXPECTED_FALLBACK_REASON;
  if (
    value !== "artifact_missing" &&
    value !== "artifact_corrupt" &&
    value !== "no_supported_sources"
  ) {
    throw new Error(`Unsupported browser fallback reason: ${value ?? "missing"}`);
  }
  return value;
}

async function stage4Reference(
  request: APIRequestContext,
  selectedGameId: number,
): Promise<RecommendationResponse> {
  const apiUrl = process.env.STAGE4_ORACLE_API_URL;
  if (!apiUrl) throw new Error("STAGE4_ORACLE_API_URL is required for fallback E2E");
  const response = await request.post(`${apiUrl}/api/v1/recommendations`, {
    data: {
      selected_game_ids: [selectedGameId],
      preferred_genres: ["strategy"],
      preferred_tags: [],
      preferred_platforms: [],
      top_k: 10,
    },
  });
  expect(response.status()).toBe(200);
  return (await response.json()) as RecommendationResponse;
}

function expectExactStage4Result(
  result: PersonalizedRecommendationResponse,
  reference: RecommendationResponse,
  expectedReason: BrowserFallbackReason,
) {
  expect(result.ranking_mode).toBe("stage_4_fallback");
  expect(result.fallback_reason).toBe(expectedReason);
  expect(result.hybrid_policy).toBeNull();
  expect(result.collaborative_model).toBeNull();
  expect(result.model_name).toBe(reference.model.name);
  expect(result.model_version).toBe(reference.model.version);
  expect(result.data_fingerprint).toBe(reference.model.data_fingerprint);
  expect(result.response_reason).toBe(reference.response_reason);
  expect(result.requested_top_k).toBe(reference.requested_top_k);
  expect(result.positive_feedback_sources).toEqual([]);
  expect(result.items.map((item) => item.game.slug)).toEqual(
    reference.items.map((item) => item.game.slug),
  );

  for (const [index, item] of result.items.entries()) {
    const expected = reference.items[index];
    expect(expected).toBeDefined();
    if (!expected) continue;
    expect(item.rank).toBe(expected.rank);
    expect(item.game).toEqual(expected.game);
    expect(item.base_ranking_score).toBe(expected.ranking_score);
    expect(item.base_components).toEqual(expected.components);
    expect(item.base_weight).toBe(1);
    expect(item.base_contribution).toBe(expected.ranking_score);
    expect(item.feedback_affinity_score).toBe(0);
    expect(item.feedback_affinity_weight).toBe(0);
    expect(item.feedback_affinity_contribution).toBe(0);
    expect(item.pre_played_score).toBe(expected.ranking_score);
    expect(item.played_factor).toBe(1);
    expect(item.played_delta).toBe(0);
    expect(item.ranking_score).toBe(expected.ranking_score);
    expect(item.adjustment_reasons).toEqual([]);
    expect(item.evidence).toEqual(expected.evidence);
    expect(item.explanation).toEqual(expected.explanation);
    expect(item.candidate_origin).toBe("content");
    expect(item.collaborative_supported).toBe(false);
    expect(item.collaborative_score).toBe(0);
    expect(item.collaborative_weight).toBe(0);
    expect(item.collaborative_contribution).toBe(0);
    expect(item.collaborative_item_support).toBeNull();
    expect(item.collaborative_source_edges).toEqual([]);
  }
}

export async function exerciseBrowserFallback(
  page: Page,
  request: APIRequestContext,
  testInfo: TestInfo,
  expectedReason: BrowserFallbackReason,
) {
  const source = SOURCE_BY_REASON[expectedReason];
  const reference = await stage4Reference(request, source.gameId);

  await page.goto("/recommendations");
  await enableSavedPersonalization(page);
  await savePreferences(page, {
    gameIds: [source.gameId],
    genreSlugs: ["strategy"],
  });
  const result = await generateSavedRecommendations(page, testInfo);
  expectExactStage4Result(result, reference, expectedReason);

  const results = page.locator(".recommendation-results");
  await expect(
    results.getByRole("heading", { name: /personalized recommendations/ }),
  ).toBeFocused();
  await expect(
    results.getByRole("heading", { name: "Saved ranking fallback" }),
  ).toBeVisible();
  await expect(results.getByText(FALLBACK_COPY[expectedReason])).toBeVisible();
  expect(
    (await results.locator(".recommendation-card h3").allTextContents()).map((title) =>
      title.trim(),
    ),
  ).toEqual(reference.items.map((item) => item.game.title));
  await expect(results.locator(".aggregate-evidence")).toHaveCount(0);
  await expect(results.getByText("Aggregate interaction", { exact: true })).toHaveCount(
    0,
  );
  expect(result.items.map((item) => item.game.slug)).not.toContain(source.slug);
  return result;
}
