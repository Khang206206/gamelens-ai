import { appendFileSync, mkdirSync } from "node:fs";
import path from "node:path";

import { expect, type Page, type TestInfo } from "@playwright/test";

import {
  parseStage5PersonalizedRecommendationResponse,
  type Stage5PersonalizedRecommendationResponse,
} from "../src/lib/api/personalized-response";

const FIXTURE_EVIDENCE_DIRECTORY = process.env.STAGE5_EVENT_EVIDENCE_DIR;
const SCORE_SCALE = 1_000_000;

export async function enableSavedPersonalization(page: Page) {
  const responsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/v1/anonymous-sessions"),
  );
  await page.getByRole("button", { name: "Enable saved personalization" }).click();
  expect((await responsePromise).status()).toBe(201);
  await expect(
    page.getByRole("heading", { name: "Review and save your durable choices" }),
  ).toBeVisible();
}

export async function savePreferences(
  page: Page,
  {
    gameIds,
    genreSlugs = [],
  }: { gameIds: readonly number[]; genreSlugs?: readonly string[] },
) {
  const input = page.getByRole("textbox", { name: "Example game IDs" });
  await input.fill(gameIds.join(", "));
  await input.press("Tab");
  const genres = page.getByRole("textbox", { name: "Genre slugs" });
  await genres.fill(genreSlugs.join(", "));
  await genres.press("Tab");
  const responsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "PUT" &&
      response.url().endsWith("/api/v1/me/preferences"),
  );
  await page.getByRole("button", { name: "Save complete preference set" }).click();
  expect((await responsePromise).status()).toBe(200);
  await expect(page.getByText("Saved preferences were updated.")).toBeVisible();
}

export async function captureSavedGeneration(
  page: Page,
  testInfo: TestInfo,
  trigger: () => Promise<void>,
): Promise<Stage5PersonalizedRecommendationResponse> {
  const responsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/v1/me/recommendations"),
  );
  await trigger();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const result = parseStage5PersonalizedRecommendationResponse(await response.json());
  recordCommittedGeneration(result, testInfo);
  return result;
}

export async function generateSavedRecommendations(page: Page, testInfo: TestInfo) {
  return captureSavedGeneration(page, testInfo, async () => {
    await page.getByRole("button", { name: "Generate saved recommendations" }).click();
  });
}

export function scoreUnits(score: number): number {
  return Math.round(score * SCORE_SCALE);
}

export function contributionUnits(rawScore: number, weight: number): number {
  return Math.floor(
    (scoreUnits(rawScore) * scoreUnits(weight) + SCORE_SCALE / 2) / SCORE_SCALE,
  );
}

export async function expectNoPageOverflow(page: Page) {
  const diagnostics = await page.evaluate(() => {
    const viewportWidth = document.documentElement.clientWidth;
    return {
      overflow: document.documentElement.scrollWidth > viewportWidth,
      offenders: Array.from(document.body.querySelectorAll("*"))
        .filter((element) => element.getBoundingClientRect().right > viewportWidth + 0.5)
        .slice(0, 5)
        .map((element) => ({
          tag: element.tagName.toLowerCase(),
          className: element.getAttribute("class"),
          right: Math.round(element.getBoundingClientRect().right),
          text: element.textContent?.trim().slice(0, 80),
        })),
    };
  });
  expect(diagnostics.overflow, JSON.stringify(diagnostics.offenders)).toBe(false);
}

function recordCommittedGeneration(
  result: Stage5PersonalizedRecommendationResponse,
  testInfo: TestInfo,
) {
  if (!FIXTURE_EVIDENCE_DIRECTORY) {
    throw new Error("STAGE5_EVENT_EVIDENCE_DIR is required for fixture browser tests");
  }
  mkdirSync(FIXTURE_EVIDENCE_DIRECTORY, { recursive: true });
  const projectName = testInfo.project.name.replace(/[^a-z0-9._-]/gi, "-").toLowerCase();
  const evidencePath = path.join(
    FIXTURE_EVIDENCE_DIRECTORY,
    `${projectName}-${testInfo.workerIndex}-${process.pid}.jsonl`,
  );
  appendFileSync(
    evidencePath,
    `${JSON.stringify({
      generation_id: result.generation_id,
      ranking_mode: result.ranking_mode,
    })}\n`,
    { encoding: "utf8", flag: "a" },
  );
}
