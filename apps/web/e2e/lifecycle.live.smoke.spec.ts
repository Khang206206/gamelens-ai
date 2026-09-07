import { chmodSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

import {
  expect,
  test,
  type Browser,
  type BrowserContext,
  type Page,
  type TestInfo,
} from "@playwright/test";

import { parseStage5PersonalizedRecommendationResponse } from "../src/lib/api/personalized-response";
import { expectExactStage4Result, stage4Reference } from "./fallback-fixture-helpers";
import {
  captureSavedGeneration,
  enableSavedPersonalization,
  generateSavedRecommendations,
  savePreferences,
} from "./hybrid-fixture-helpers";

type LifecycleScenario =
  | "preference-removal"
  | "feedback-removal"
  | "contribution-withdrawal"
  | "clear-data"
  | "reconsent";
type LifecyclePhase =
  "prepare" | "ready" | "previous" | "transition" | "reconsent" | "restart";
type Role = "contributor" | "observer";

const SESSION_COOKIE_NAME = "gamelens_session";
const EVIDENCE_DIRECTORY = process.env.STAGE8G_EVIDENCE_DIR;

test.skip(
  process.env.COLLABORATIVE_LIFECYCLE_E2E !== "1",
  "Requires the explicit disposable live-source lifecycle stack",
);

function requiredScenario(): LifecycleScenario {
  const value = process.env.STAGE8G_SCENARIO;
  if (
    value !== "preference-removal" &&
    value !== "feedback-removal" &&
    value !== "contribution-withdrawal" &&
    value !== "clear-data" &&
    value !== "reconsent"
  ) {
    throw new Error(`Unsupported Stage 8G scenario: ${value ?? "missing"}`);
  }
  return value;
}

function requiredPhase(): LifecyclePhase {
  const value = process.env.STAGE8G_PHASE;
  if (
    value !== "prepare" &&
    value !== "ready" &&
    value !== "previous" &&
    value !== "transition" &&
    value !== "reconsent" &&
    value !== "restart"
  ) {
    throw new Error(`Unsupported Stage 8G phase: ${value ?? "missing"}`);
  }
  return value;
}

function evidencePath(name: string) {
  if (!EVIDENCE_DIRECTORY) throw new Error("STAGE8G_EVIDENCE_DIR is required");
  mkdirSync(EVIDENCE_DIRECTORY, { recursive: true });
  return path.join(EVIDENCE_DIRECTORY, name);
}

function statePath(role: Role) {
  return evidencePath(`.stage8g-${role}-state.json`);
}

function recordGeneration(
  phase: LifecyclePhase,
  role: Role,
  result: ReturnType<typeof parseStage5PersonalizedRecommendationResponse>,
) {
  const record = {
    phase,
    role,
    generation_id: result.generation_id,
    ranking_mode: result.ranking_mode,
    fallback_reason: result.fallback_reason,
  };
  writeFileSync(
    evidencePath("stage8g-browser-evidence.jsonl"),
    `${JSON.stringify(record)}\n`,
    {
      encoding: "utf8",
      flag: "a",
    },
  );
}

function writeScenarioMetadata(value: Record<string, unknown>) {
  const target = evidencePath("stage8g-scenario.json");
  writeFileSync(target, JSON.stringify(value), { encoding: "utf8", flag: "w" });
  chmodSync(target, 0o660);
}

async function openRole(
  browser: Browser,
  testInfo: TestInfo,
  role: Role,
): Promise<{ context: BrowserContext; page: Page }> {
  const baseURL = testInfo.project.use.baseURL;
  if (typeof baseURL !== "string") throw new Error("Lifecycle E2E requires a base URL");
  const context = await browser.newContext({ baseURL, storageState: statePath(role) });
  const page = await context.newPage();
  await page.goto("/recommendations");
  return { context, page };
}

async function createRole(
  browser: Browser,
  testInfo: TestInfo,
  role: Role,
  gameIds: readonly number[],
) {
  const baseURL = testInfo.project.use.baseURL;
  if (typeof baseURL !== "string") throw new Error("Lifecycle E2E requires a base URL");
  const context = await browser.newContext({ baseURL });
  const page = await context.newPage();
  await page.goto("/recommendations");
  await enableSavedPersonalization(page);
  await savePreferences(page, { gameIds, genreSlugs: ["strategy"] });
  return { context, page };
}

async function saveRoleState(context: BrowserContext, role: Role) {
  const target = statePath(role);
  await context.storageState({ path: target });
  chmodSync(target, 0o660);
  const state = JSON.parse(readFileSync(target, "utf8")) as {
    cookies?: Array<{ name?: string; domain?: string }>;
  };
  expect(
    state.cookies?.filter(
      (cookie) =>
        cookie.name === SESSION_COOKIE_NAME && cookie.domain === "gamelens.test",
    ),
  ).toHaveLength(1);
}

async function prepare(
  browser: Browser,
  testInfo: TestInfo,
  scenario: LifecycleScenario,
) {
  const contributor = await createRole(browser, testInfo, "contributor", [1, 2, 3]);
  let feedbackGameId: number | null = null;
  try {
    if (scenario === "feedback-removal") {
      const initial = await generateSavedRecommendations(contributor.page, testInfo);
      const target = initial.items[0];
      expect(target).toBeDefined();
      if (!target) throw new Error("Feedback scenario needs one content candidate");
      feedbackGameId = target.game.id;
      const controls = contributor.page.getByRole("group", {
        name: `Feedback for ${target.game.title}`,
      });
      await controls.getByLabel("Reaction").selectOption("liked");
      const feedbackResponse = contributor.page.waitForResponse(
        (response) =>
          response.request().method() === "PUT" &&
          response.url().endsWith(`/api/v1/me/games/${target.game.id}/feedback`),
      );
      const refreshed = contributor.page.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          response.url().endsWith("/api/v1/me/recommendations"),
      );
      await controls.getByRole("button", { name: "Save feedback" }).click();
      expect((await feedbackResponse).status()).toBe(200);
      expect((await refreshed).status()).toBe(200);
      await expect(contributor.page.getByText("Feedback saved.")).toBeVisible();
    }
    await saveRoleState(contributor.context, "contributor");
  } finally {
    await contributor.context.close();
  }

  const observer = await createRole(browser, testInfo, "observer", [1]);
  try {
    await saveRoleState(observer.context, "observer");
  } finally {
    await observer.context.close();
  }
  writeScenarioMetadata({ scenario, feedback_game_id: feedbackGameId });
}

async function generateForRole(
  browser: Browser,
  testInfo: TestInfo,
  phase: LifecyclePhase,
  role: Role,
) {
  const opened = await openRole(browser, testInfo, role);
  try {
    await expect(
      opened.page.getByRole("heading", { name: "Review and save your durable choices" }),
    ).toBeVisible();
    const result = await generateSavedRecommendations(opened.page, testInfo);
    recordGeneration(phase, role, result);
    return result;
  } finally {
    await opened.context.close();
  }
}

async function expectObserverFallback(
  browser: Browser,
  request: Parameters<typeof stage4Reference>[0],
  testInfo: TestInfo,
  phase: LifecyclePhase,
) {
  const reference = await stage4Reference(request, 1);
  const opened = await openRole(browser, testInfo, "observer");
  try {
    const result = await generateSavedRecommendations(opened.page, testInfo);
    recordGeneration(phase, "observer", result);
    expectExactStage4Result(result, reference, "privacy_invalid");
    await expect(
      opened.page.getByRole("heading", { name: "Saved ranking fallback" }),
    ).toBeVisible();
    await expect(opened.page.getByText(/no longer eligible for use/i)).toBeVisible();
    await expect(opened.page.locator(".aggregate-evidence")).toHaveCount(0);
  } finally {
    await opened.context.close();
  }
}

async function transitionContributor(
  browser: Browser,
  testInfo: TestInfo,
  scenario: LifecycleScenario,
) {
  if (scenario === "contribution-withdrawal" || scenario === "reconsent") return;
  const opened = await openRole(browser, testInfo, "contributor");
  try {
    if (scenario === "preference-removal") {
      const removed = opened.page.waitForResponse(
        (response) =>
          response.request().method() === "DELETE" &&
          response.url().endsWith("/api/v1/me/preferences"),
      );
      await opened.page.getByRole("button", { name: "Clear saved preferences" }).click();
      expect((await removed).status()).toBe(204);
      await expect(
        opened.page.getByText("Saved preferences were cleared."),
      ).toBeVisible();
      return;
    }
    if (scenario === "feedback-removal") {
      const removed = opened.page.waitForResponse(
        (response) =>
          response.request().method() === "DELETE" &&
          /\/api\/v1\/me\/games\/\d+\/feedback$/.test(response.url()),
      );
      const result = await captureSavedGeneration(opened.page, testInfo, async () => {
        await opened.page.getByRole("button", { name: "Clear feedback" }).first().click();
      });
      expect((await removed).status()).toBe(204);
      expect(result.ranking_mode).toBe("stage_4_fallback");
      expect(result.fallback_reason).toBe("privacy_invalid");
      recordGeneration("transition", "contributor", result);
      return;
    }

    opened.page.once("dialog", (dialog) => void dialog.accept());
    const removed = opened.page.waitForResponse(
      (response) =>
        response.request().method() === "DELETE" && response.url().endsWith("/api/v1/me"),
    );
    await opened.page.getByRole("button", { name: "Clear all saved data" }).click();
    expect((await removed).status()).toBe(204);
    await expect(opened.page.getByText(/All saved data was cleared/)).toBeVisible();
    await expect(
      opened.page.getByRole("button", { name: "Enable saved personalization" }),
    ).toBeVisible();
    expect(
      (await opened.context.cookies()).filter(
        (cookie) => cookie.name === SESSION_COOKIE_NAME,
      ),
    ).toEqual([]);
  } finally {
    await opened.context.close();
  }
}

async function exerciseReconsent(
  browser: Browser,
  testInfo: TestInfo,
  scenario: LifecycleScenario,
  phase: "transition" | "reconsent",
) {
  const opened = await openRole(browser, testInfo, "contributor");
  try {
    const continueButton = opened.page.getByRole("button", {
      name: "Continue with saved personalization",
    });
    await expect(continueButton).toBeVisible();
    await expect(
      opened.page.getByRole("heading", { name: "Review and save your durable choices" }),
    ).toHaveCount(0);
    await expect(opened.page.locator(".recommendation-results")).toHaveCount(0);
    const renewed = opened.page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().endsWith("/api/v1/anonymous-sessions"),
    );
    await continueButton.click();
    expect((await renewed).status()).toBe(200);
    await expect(
      opened.page.getByRole("heading", { name: "Review and save your durable choices" }),
    ).toBeVisible();
    await saveRoleState(opened.context, "contributor");

    if (scenario === "preference-removal" && phase === "reconsent") {
      await expect(
        opened.page.getByRole("button", { name: "Generate saved recommendations" }),
      ).toBeDisabled();
      await expect(opened.page.locator(".recommendation-results")).toHaveCount(0);
      return;
    }

    const result = await generateSavedRecommendations(opened.page, testInfo);
    recordGeneration(phase, "contributor", result);
    expect(result.ranking_mode).toBe("stage_4_fallback");
    expect(result.fallback_reason).toBe("privacy_invalid");
    await expect(
      opened.page.getByRole("heading", { name: "Saved ranking fallback" }),
    ).toBeVisible();
  } finally {
    await opened.context.close();
  }
}

test("serialized live lifecycle phase", async ({ browser, request }, testInfo) => {
  const scenario = requiredScenario();
  const phase = requiredPhase();

  if (phase === "prepare") {
    await prepare(browser, testInfo, scenario);
    return;
  }
  if (phase === "ready" || phase === "previous") {
    const result = await generateForRole(browser, testInfo, phase, "observer");
    expect(result.ranking_mode).toBe("hybrid");
    expect(result.fallback_reason).toBeNull();
    expect(result.items.some((item) => item.collaborative_supported)).toBe(true);
    return;
  }
  if (phase === "reconsent") {
    await exerciseReconsent(browser, testInfo, scenario, phase);
    await expectObserverFallback(browser, request, testInfo, phase);
    return;
  }
  if (phase === "transition") {
    if (scenario === "reconsent") {
      await exerciseReconsent(browser, testInfo, scenario, phase);
    } else {
      await transitionContributor(browser, testInfo, scenario);
    }
    await expectObserverFallback(browser, request, testInfo, phase);
    return;
  }
  await expectObserverFallback(browser, request, testInfo, phase);
});
