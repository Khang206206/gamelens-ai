import { expect, test, type Page } from "@playwright/test";

import type { Stage5PersonalizedRecommendationResponse } from "../src/lib/api/personalized-response";
import {
  captureSavedGeneration,
  contributionUnits,
  enableSavedPersonalization,
  generateSavedRecommendations,
  savePreferences,
  scoreUnits,
} from "./hybrid-fixture-helpers";

const SUPPORTED_GAME = { id: 1, slug: "emberfall-tactics" } as const;
const COLD_START_GAME = { id: 4, slug: "abyssal-signal" } as const;

test.skip(
  process.env.COLLABORATIVE_FIXTURE_E2E !== "1",
  "Requires the explicit project-authored collaborative fixture stack",
);

async function openSavedWorkspace(page: Page) {
  await page.goto("/recommendations");
  await expect(
    page.getByRole("button", { name: "Enable saved personalization" }),
  ).toBeVisible();
  await enableSavedPersonalization(page);
}

function expectExactReconstruction(result: Stage5PersonalizedRecommendationResponse) {
  for (const item of result.items) {
    const baseComponentUnits = item.base_components.map((component) => {
      const expected = contributionUnits(component.raw_score, component.weight);
      expect(scoreUnits(component.contribution)).toBe(expected);
      return expected;
    });
    expect(scoreUnits(item.base_ranking_score)).toBe(
      baseComponentUnits.reduce((total, value) => total + value, 0),
    );

    const baseContribution = contributionUnits(item.base_ranking_score, item.base_weight);
    const feedbackContribution = contributionUnits(
      item.feedback_affinity_score,
      item.feedback_affinity_weight,
    );
    const collaborativeContribution = contributionUnits(
      item.collaborative_score,
      item.collaborative_weight,
    );
    expect(scoreUnits(item.base_contribution)).toBe(baseContribution);
    expect(scoreUnits(item.feedback_affinity_contribution)).toBe(feedbackContribution);
    expect(scoreUnits(item.collaborative_contribution)).toBe(collaborativeContribution);

    const prePlayed = baseContribution + feedbackContribution + collaborativeContribution;
    const final = Math.floor(
      (prePlayed * scoreUnits(item.played_factor) + 500_000) / 1_000_000,
    );
    expect(scoreUnits(item.pre_played_score)).toBe(prePlayed);
    expect(scoreUnits(item.ranking_score)).toBe(final);
    expect(scoreUnits(item.played_delta)).toBe(final - prePlayed);

    if (item.collaborative_supported) {
      const edgeUnits = item.collaborative_source_edges.map((edge) =>
        scoreUnits(edge.similarity_score),
      );
      const expectedCollaborativeScore = Math.floor(
        (edgeUnits.reduce((total, value) => total + value, 0) +
          Math.floor(edgeUnits.length / 2)) /
          edgeUnits.length,
      );
      expect(scoreUnits(item.collaborative_score)).toBe(expectedCollaborativeScore);
    }
  }
}

async function expectDomMatchesServer(
  page: Page,
  result: Stage5PersonalizedRecommendationResponse,
) {
  const results = page.locator(".recommendation-results");
  await expect(
    results.getByRole("heading", { name: /personalized recommendations/ }),
  ).toBeFocused();
  await expect(
    results.getByRole("heading", { name: "Hybrid ranking applied" }),
  ).toBeVisible();
  expect(
    (await results.locator(".recommendation-card h3").allTextContents()).map((title) =>
      title.trim(),
    ),
  ).toEqual(result.items.map((item) => item.game.title));

  for (const [index, item] of result.items.entries()) {
    const card = results.locator(".recommendation-card").nth(index);
    await expect(card.locator(".recommendation-card__rank")).toHaveAttribute(
      "aria-label",
      `Rank ${item.rank}`,
    );
    await expect(
      card.getByText(`Final score ${item.ranking_score.toFixed(6)}`),
    ).toBeVisible();
    await card.getByText("Inspect personalization components").click();
    await expect(card.getByText("Base", { exact: true })).toBeVisible();
    await expect(
      card.getByText(
        `${item.base_ranking_score.toFixed(6)} × ${item.base_weight.toFixed(6)} = ${item.base_contribution.toFixed(6)}`,
        { exact: true },
      ),
    ).toBeVisible();
    await expect(
      card.getByText(
        `${item.feedback_affinity_score.toFixed(6)} × ${item.feedback_affinity_weight.toFixed(6)} = ${item.feedback_affinity_contribution.toFixed(6)}`,
        { exact: true },
      ),
    ).toBeVisible();
    await expect(
      card.getByText(
        `factor ${item.played_factor.toFixed(6)} · delta ${item.played_delta.toFixed(6)}`,
        { exact: true },
      ),
    ).toBeVisible();

    const aggregateEvidence = card.locator(".aggregate-evidence");
    if (item.collaborative_supported && item.collaborative_contribution > 0) {
      await expect(
        aggregateEvidence.getByRole("heading", {
          name: "Aggregate interaction evidence",
        }),
      ).toBeVisible();
      await expect(
        aggregateEvidence.getByText(String(item.collaborative_item_support), {
          exact: true,
        }),
      ).toBeVisible();
      await expect(aggregateEvidence.getByRole("listitem")).toHaveCount(
        item.collaborative_source_edges.length,
      );
      for (const edge of item.collaborative_source_edges) {
        const edgeRow = aggregateEvidence.getByRole("listitem").filter({
          hasText: edge.source_game_slug,
        });
        await expect(edgeRow).toContainText(
          `similarity ${edge.similarity_score.toFixed(6)} · pair support ${edge.pair_support}`,
        );
      }
      await expect(
        card.getByText(
          `${item.collaborative_score.toFixed(6)} × ${item.collaborative_weight.toFixed(6)} = ${item.collaborative_contribution.toFixed(6)}`,
          { exact: true },
        ),
      ).toBeVisible();
    } else {
      await expect(aggregateEvidence).toHaveCount(0);
      await expect(card.getByText("Aggregate interaction", { exact: true })).toHaveCount(
        0,
      );
    }
  }
}

test("supported saved sources render the exact reconstructible server-ordered hybrid response", async ({
  page,
}, testInfo) => {
  await openSavedWorkspace(page);
  await savePreferences(page, {
    gameIds: [SUPPORTED_GAME.id],
    genreSlugs: ["simulation"],
  });

  const first = await generateSavedRecommendations(page, testInfo);
  expect(first.ranking_mode).toBe("hybrid");
  expect(first.fallback_reason).toBeNull();
  expect(first.items.length).toBeGreaterThan(0);
  expect(first.items.some((item) => item.collaborative_supported)).toBe(true);
  expect(first.items.map((item) => item.game.slug)).not.toContain(SUPPORTED_GAME.slug);
  expectExactReconstruction(first);
  await expectDomMatchesServer(page, first);

  await page.reload();
  await expect(page.getByRole("textbox", { name: "Example game IDs" })).toHaveValue(
    String(SUPPORTED_GAME.id),
  );
  await expect(page.getByRole("textbox", { name: "Genre slugs" })).toHaveValue(
    "simulation",
  );
  await expect(page.locator(".recommendation-results")).toHaveCount(0);

  const afterReload = await generateSavedRecommendations(page, testInfo);
  expect(afterReload.ranking_mode).toBe("hybrid");
  expect(afterReload.items.map((item) => item.game.slug)).toEqual(
    first.items.map((item) => item.game.slug),
  );
  await expectDomMatchesServer(page, afterReload);
});

test("saved dislike exclusion and played evidence survive real hybrid regeneration", async ({
  page,
}, testInfo) => {
  await openSavedWorkspace(page);
  await savePreferences(page, {
    gameIds: [SUPPORTED_GAME.id],
    genreSlugs: ["strategy"],
  });
  const initial = await generateSavedRecommendations(page, testInfo);
  const playedTarget = initial.items[0];
  expect(playedTarget).toBeDefined();
  if (!playedTarget) return;

  const playedControls = page.getByRole("group", {
    name: `Feedback for ${playedTarget.game.title}`,
  });
  await playedControls.getByRole("checkbox", { name: "Played" }).check();
  const afterPlayed = await captureSavedGeneration(page, testInfo, async () => {
    await playedControls.getByRole("button", { name: "Save feedback" }).click();
  });
  const adjusted = afterPlayed.items.find(
    (item) => item.game.slug === playedTarget.game.slug,
  );
  expect(adjusted).toBeDefined();
  expect(adjusted?.played_factor).toBe(0.5);
  expect(adjusted?.played_delta).toBeLessThan(0);
  const adjustedCard = page.locator(".recommendation-card").filter({
    has: page.getByRole("heading", { name: playedTarget.game.title }),
  });
  await adjustedCard.getByText("Inspect personalization components").click();
  await expect(adjustedCard.getByText(/factor 0\.500000 · delta -/)).toBeVisible();

  const dislikeTarget = afterPlayed.items.find(
    (item) => item.game.slug !== playedTarget.game.slug,
  );
  expect(dislikeTarget).toBeDefined();
  if (!dislikeTarget) return;
  const dislikeControls = page.getByRole("group", {
    name: `Feedback for ${dislikeTarget.game.title}`,
  });
  await dislikeControls.getByLabel("Reaction").selectOption("disliked");
  const afterDislike = await captureSavedGeneration(page, testInfo, async () => {
    await dislikeControls.getByRole("button", { name: "Save feedback" }).click();
  });
  expect(afterDislike.ranking_mode).toBe("hybrid");
  expect(afterDislike.items.map((item) => item.game.slug)).not.toContain(
    dislikeTarget.game.slug,
  );
  expect(afterDislike.items.map((item) => item.game.slug)).not.toContain(
    SUPPORTED_GAME.slug,
  );
});

test("an unsupported saved source remains an honest cold-start fallback", async ({
  page,
}, testInfo) => {
  await openSavedWorkspace(page);
  await savePreferences(page, { gameIds: [COLD_START_GAME.id] });

  const result = await generateSavedRecommendations(page, testInfo);
  expect(result.ranking_mode).toBe("stage_4_fallback");
  expect(result.fallback_reason).toBe("no_supported_sources");
  expect(result.items.map((item) => item.game.slug)).not.toContain(COLD_START_GAME.slug);
  expect(result.items.every((item) => !item.collaborative_supported)).toBe(true);
  await expect(
    page.getByRole("heading", { name: "Saved ranking fallback" }),
  ).toBeVisible();
  await expect(
    page.getByText(/did not contain an eligible positive source|no retained aggregate/i),
  ).toBeVisible();
  await expect(page.locator(".aggregate-evidence")).toHaveCount(0);
});

test("the request-only path remains stateless and content-only beside a ready fixture", async ({
  context,
  page,
}) => {
  await page.goto("/recommendations");
  await page
    .getByRole("group", { name: /Preferred genres/ })
    .getByLabel("Strategy")
    .check();
  await page.getByRole("button", { name: "Review selections" }).click();

  const responsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/v1/recommendations"),
  );
  await page.getByRole("button", { name: "Get recommendations" }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const payload = (await response.json()) as Record<string, unknown>;
  expect(payload).not.toHaveProperty("generation_id");
  expect(payload).not.toHaveProperty("ranking_mode");
  await expect(
    page.getByRole("heading", { name: /ranked recommendations/ }),
  ).toBeFocused();
  await expect(page.getByRole("heading", { name: "Hybrid ranking applied" })).toHaveCount(
    0,
  );
  await expect(page.locator(".aggregate-evidence")).toHaveCount(0);
  expect(
    (await context.cookies()).filter((cookie) => cookie.name === "gamelens_session"),
  ).toEqual([]);
});
