import { expect, test, type BrowserContext, type Page } from "@playwright/test";

const SESSION_COOKIE_NAME = "gamelens_session";

interface ConsoleDiagnostic {
  text: string;
  url: string;
}

interface PageDiagnostics {
  consoleErrors: ConsoleDiagnostic[];
  pageErrors: string[];
  allowedConsoleErrors: Array<(diagnostic: ConsoleDiagnostic) => boolean>;
}

const diagnosticsByPage = new WeakMap<Page, PageDiagnostics>();

function watchPageDiagnostics(page: Page): PageDiagnostics {
  const existing = diagnosticsByPage.get(page);
  if (existing) return existing;
  const diagnostics: PageDiagnostics = {
    consoleErrors: [],
    pageErrors: [],
    allowedConsoleErrors: [],
  };
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    diagnostics.consoleErrors.push({
      text: message.text(),
      url: message.location().url,
    });
  });
  page.on("pageerror", (error) => diagnostics.pageErrors.push(error.message));
  diagnosticsByPage.set(page, diagnostics);
  return diagnostics;
}

function allowConsoleError(
  page: Page,
  predicate: (diagnostic: ConsoleDiagnostic) => boolean,
) {
  watchPageDiagnostics(page).allowedConsoleErrors.push(predicate);
}

function expectCleanPageDiagnostics(page: Page) {
  const diagnostics = watchPageDiagnostics(page);
  const unexpectedConsoleErrors = diagnostics.consoleErrors.filter(
    (entry) =>
      !(
        entry.url.endsWith("/api/v1/me") &&
        /status of 401|401 \(Unauthorized\)/i.test(entry.text)
      ) && !diagnostics.allowedConsoleErrors.some((predicate) => predicate(entry)),
  );
  expect(unexpectedConsoleErrors).toEqual([]);
  expect(diagnostics.pageErrors).toEqual([]);
}

test.beforeEach(({ page }) => {
  watchPageDiagnostics(page);
});

test.afterEach(({ page }) => {
  expectCleanPageDiagnostics(page);
});

async function openStatelessRecommendations(page: Page) {
  watchPageDiagnostics(page);
  await page.goto("/recommendations");
  await expect(
    page.getByRole("button", { name: "Enable saved personalization" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Build a shortlist without saving it" }),
  ).toBeVisible();
}

async function enableSavedPersonalization(page: Page) {
  const consentResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/v1/anonymous-sessions"),
  );
  await page.getByRole("button", { name: "Enable saved personalization" }).click();
  expect((await consentResponse).status()).toBe(201);
  await expect(
    page.getByRole("heading", { name: "Review and save your durable choices" }),
  ).toBeVisible();
}

async function saveGenrePreference(page: Page, genre: string) {
  const genreInput = page.getByRole("textbox", { name: "Genre slugs" });
  await genreInput.fill(genre);
  await genreInput.press("Tab");
  await page.getByRole("button", { name: "Save complete preference set" }).click();
  await expect(page.getByText("Saved preferences were updated.")).toBeVisible();
}

async function sessionCookies(context: BrowserContext) {
  return (await context.cookies())
    .filter((cookie) => cookie.name === SESSION_COOKIE_NAME)
    .map(({ name, domain, path, httpOnly, secure, sameSite }) => ({
      name,
      domain,
      path,
      httpOnly,
      secure,
      sameSite,
    }));
}

test("a fresh browser stays stateless until the user explicitly opts in", async ({
  context,
  page,
}) => {
  const sessionMutations: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      request.url().endsWith("/api/v1/anonymous-sessions")
    ) {
      sessionMutations.push(request.url());
    }
  });

  await openStatelessRecommendations(page);

  expect(sessionMutations).toEqual([]);
  expect(await sessionCookies(context)).toEqual([]);
  await page
    .getByRole("group", { name: /Preferred genres/ })
    .getByLabel("Strategy")
    .check();
  await page.getByRole("button", { name: "Review selections" }).click();
  await expect(
    page.getByRole("heading", { name: "Ready for the content model" }),
  ).toBeFocused();
  expect(sessionMutations).toEqual([]);
  expect(await sessionCookies(context)).toEqual([]);
});

test("keyboard opt-in moves focus to the durable workspace", async ({ page }) => {
  await openStatelessRecommendations(page);
  const enable = page.getByRole("button", { name: "Enable saved personalization" });
  for (let index = 0; index < 30; index += 1) {
    await page.keyboard.press("Tab");
    if (await enable.evaluate((element) => element === document.activeElement)) break;
  }
  await expect(enable).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Review and save your durable choices" }),
  ).toBeFocused();
});

test("explicit opt-in persists preferences across a full reload", async ({
  context,
  page,
}) => {
  await openStatelessRecommendations(page);
  await enableSavedPersonalization(page);
  expect(await sessionCookies(context)).toHaveLength(1);

  await saveGenrePreference(page, "strategy");
  await page.reload();

  await expect(page.getByText(/Saved personalization is active until/)).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Genre slugs" })).toHaveValue(
    "strategy",
  );
  await expect(page.getByRole("button", { name: "Review selections" })).toBeDisabled();
  await expect(
    page.getByRole("group", { name: /Preferred genres/ }).getByLabel("Strategy"),
  ).not.toBeChecked();
  expect(
    await page.evaluate(() => ({
      local: Object.keys(localStorage),
      session: Object.keys(sessionStorage).filter(
        (key) => !key.startsWith("__next_debug_channel:"),
      ),
    })),
  ).toEqual({ local: [], session: [] });
});

test("an outdated lifecycle can re-consent through the public session endpoint", async ({
  page,
}) => {
  await openStatelessRecommendations(page);
  const initialConsent = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/v1/anonymous-sessions"),
  );
  await page.getByRole("button", { name: "Enable saved personalization" }).click();
  const initialResponse = await initialConsent;
  expect(initialResponse.status()).toBe(201);
  const lifecycle = (await initialResponse.json()) as Record<string, unknown>;
  await expect(
    page.getByRole("heading", { name: "Review and save your durable choices" }),
  ).toBeVisible();

  await page.route("**/api/v1/me", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ...lifecycle,
        status: "consent_outdated",
        consent_version: "stage-3-v1",
      }),
    });
  });
  await page.reload();

  const continueButton = page.getByRole("button", {
    name: "Continue with saved personalization",
  });
  await expect(continueButton).toBeVisible();
  const renewedConsent = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/v1/anonymous-sessions"),
  );
  await continueButton.click();
  expect((await renewedConsent).status()).toBe(200);
  await expect(
    page.getByRole("heading", { name: "Review and save your durable choices" }),
  ).toBeVisible();
});

test("saved dislike feedback survives reload and excludes the game from later results", async ({
  page,
}) => {
  await openStatelessRecommendations(page);
  await enableSavedPersonalization(page);
  await saveGenrePreference(page, "strategy");

  await page.getByRole("button", { name: "Generate saved recommendations" }).click();
  const results = page.locator(".recommendation-results");
  await expect(
    results.getByRole("heading", { name: /personalized recommendations/ }),
  ).toBeFocused();

  const firstCard = results.locator(".recommendation-card").first();
  const dislikedTitle = (
    await firstCard.getByRole("heading", { level: 3 }).innerText()
  ).trim();
  const feedback = firstCard.getByRole("group", {
    name: `Feedback for ${dislikedTitle}`,
  });
  await feedback.getByLabel("Reaction").selectOption("disliked");
  const saveFeedback = feedback.getByRole("button", { name: "Save feedback" });
  await saveFeedback.focus();
  await expect(saveFeedback).toBeFocused();
  await page.keyboard.press("Enter");

  await expect(
    page.getByText("Feedback saved and recommendations refreshed."),
  ).toBeVisible();
  await expect(
    results.getByRole("heading", { name: /personalized recommendations/ }),
  ).toBeFocused();
  await expect(results.getByRole("heading", { name: dislikedTitle })).toHaveCount(0);

  await page.reload();
  await expect(page.getByText(/Saved personalization is active until/)).toBeVisible();
  const rehydratedFeedback = page.getByRole("group", {
    name: `Feedback for ${dislikedTitle}`,
  });
  await expect(rehydratedFeedback.getByLabel("Reaction")).toHaveValue("disliked");

  const refreshedResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/v1/me/recommendations"),
  );
  await page.getByRole("button", { name: "Generate saved recommendations" }).click();
  expect((await refreshedResponse).status()).toBe(200);
  await expect(
    results.getByRole("heading", { name: /personalized recommendations/ }),
  ).toBeVisible();
  await expect(results.getByRole("heading", { name: dislikedTitle })).toHaveCount(0);
});

test("anonymous contexts remain isolated and clearing one removes only its cookie", async ({
  browser,
}, testInfo) => {
  const baseURL = testInfo.project.use.baseURL;
  if (typeof baseURL !== "string") throw new Error("This test requires a string baseURL");
  const contextA = await browser.newContext({ baseURL });
  const contextB = await browser.newContext({ baseURL });
  const pageA = await contextA.newPage();
  const pageB = await contextB.newPage();

  try {
    await Promise.all([
      openStatelessRecommendations(pageA),
      openStatelessRecommendations(pageB),
    ]);
    await Promise.all([
      enableSavedPersonalization(pageA),
      enableSavedPersonalization(pageB),
    ]);
    await Promise.all([
      saveGenrePreference(pageA, "strategy"),
      saveGenrePreference(pageB, "adventure"),
    ]);

    await Promise.all([pageA.reload(), pageB.reload()]);
    await expect(pageA.getByRole("textbox", { name: "Genre slugs" })).toHaveValue(
      "strategy",
    );
    await expect(pageB.getByRole("textbox", { name: "Genre slugs" })).toHaveValue(
      "adventure",
    );
    expect(await sessionCookies(contextA)).toHaveLength(1);
    expect(await sessionCookies(contextB)).toHaveLength(1);

    pageA.once("dialog", (dialog) => void dialog.accept());
    const clearAll = pageA.getByRole("button", { name: "Clear all saved data" });
    await clearAll.focus();
    await expect(clearAll).toBeFocused();
    await pageA.keyboard.press("Enter");
    await expect(pageA.getByText(/All saved data was cleared/)).toBeVisible();
    await expect(
      pageA.getByRole("heading", { name: "Keep your choices on this browser" }),
    ).toBeFocused();
    await expect(
      pageA.getByRole("button", { name: "Enable saved personalization" }),
    ).toBeVisible();
    expect(await sessionCookies(contextA)).toEqual([]);

    await pageB.reload();
    await expect(pageB.getByRole("textbox", { name: "Genre slugs" })).toHaveValue(
      "adventure",
    );
    expect(await sessionCookies(contextB)).toHaveLength(1);
  } finally {
    expectCleanPageDiagnostics(pageA);
    expectCleanPageDiagnostics(pageB);
    await Promise.all([contextA.close(), contextB.close()]);
  }
});

test("a transient lifecycle failure exposes a retry and recovers without hidden opt-in", async ({
  context,
  page,
}) => {
  const lifecycleUrl = "**/api/v1/me";
  allowConsoleError(
    page,
    ({ text, url }) =>
      url.endsWith("/api/v1/me") && /ERR_FAILED|Failed to fetch/i.test(text),
  );
  await page.route(lifecycleUrl, (route) => route.abort("failed"));
  await page.goto("/recommendations");

  await expect(
    page.getByRole("alert").getByText("Saved personalization could not be checked."),
  ).toBeVisible();
  expect(await sessionCookies(context)).toEqual([]);

  await page.unroute(lifecycleUrl);
  const retry = page.getByRole("button", { name: "Try again" });
  await retry.focus();
  await expect(retry).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("button", { name: "Enable saved personalization" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Keep your choices on this browser" }),
  ).toBeFocused();
  expect(await sessionCookies(context)).toEqual([]);

  await enableSavedPersonalization(page);
  expect(await sessionCookies(context)).toHaveLength(1);
});

test("an invalid session cookie is cleared and requires fresh affirmative consent", async ({
  context,
  page,
}) => {
  await context.addCookies([
    {
      name: SESSION_COOKIE_NAME,
      value: "x".repeat(43),
      domain: "gamelens.test",
      path: "/api/v1",
      httpOnly: true,
      sameSite: "Lax",
      secure: false,
    },
  ]);

  await page.goto("/recommendations");

  await expect(
    page.getByRole("button", { name: "Enable saved personalization" }),
  ).toBeVisible();
  expect(await sessionCookies(context)).toEqual([]);
  await enableSavedPersonalization(page);
  expect(await sessionCookies(context)).toHaveLength(1);
});

test("a rejected CSRF write preserves the draft and succeeds after an explicit retry", async ({
  context,
  page,
}) => {
  allowConsoleError(
    page,
    ({ text, url }) =>
      url.endsWith("/api/v1/me/preferences") &&
      /status of 403|403 \(Forbidden\)/i.test(text),
  );
  await openStatelessRecommendations(page);
  await enableSavedPersonalization(page);

  let strippedCsrf = false;
  await page.route("**/api/v1/me/preferences", async (route) => {
    if (!strippedCsrf && route.request().method() === "PUT") {
      strippedCsrf = true;
      const headers = { ...route.request().headers() };
      delete headers["x-csrf-token"];
      await route.continue({ headers });
      return;
    }
    await route.continue();
  });

  const genreInput = page.getByRole("textbox", { name: "Genre slugs" });
  await genreInput.fill("strategy");
  const rejectedWrite = page.waitForResponse(
    (response) =>
      response.request().method() === "PUT" &&
      response.url().endsWith("/api/v1/me/preferences"),
  );
  await page.getByRole("button", { name: "Save complete preference set" }).click();
  expect((await rejectedWrite).status()).toBe(403);
  await expect(genreInput).toHaveValue("strategy");
  await expect(
    page.getByRole("button", { name: "Save complete preference set" }),
  ).toBeEnabled();
  expect(await sessionCookies(context)).toHaveLength(1);

  await page.unroute("**/api/v1/me/preferences");
  await page.getByRole("button", { name: "Save complete preference set" }).click();
  await expect(page.getByText("Saved preferences were updated.")).toBeVisible();
});

test("an exact rejected Origin on an unsafe write preserves a recoverable draft", async ({
  page,
}) => {
  allowConsoleError(
    page,
    ({ text, url }) =>
      (url.endsWith("/api/v1/me/preferences") &&
        /status of 403|403 \(Forbidden\)|ERR_FAILED/i.test(text)) ||
      /blocked by CORS policy|Cross-Origin Request Blocked/i.test(text),
  );
  await openStatelessRecommendations(page);
  await enableSavedPersonalization(page);
  await saveGenrePreference(page, "strategy");

  let rejectedOriginRequests = 0;
  let realRejection: { status: number; payload: unknown } | undefined;
  await page.route("**/api/v1/me/preferences", async (route) => {
    if (route.request().method() !== "PUT") {
      await route.continue();
      return;
    }
    rejectedOriginRequests += 1;
    const response = await route.fetch({
      headers: {
        ...route.request().headers(),
        origin: "https://untrusted.example",
      },
    });
    realRejection = {
      status: response.status(),
      payload: await response.json(),
    };
    await route.fulfill({
      response,
      headers: {
        ...response.headers(),
        "access-control-allow-credentials": "true",
        "access-control-allow-origin": "http://gamelens.test:3000",
      },
    });
  });

  const genreInput = page.getByRole("textbox", { name: "Genre slugs" });
  await genreInput.fill("adventure");
  const rejectedWrite = page.waitForResponse(
    (response) =>
      response.request().method() === "PUT" &&
      response.url().endsWith("/api/v1/me/preferences"),
  );
  await page.getByRole("button", { name: "Save complete preference set" }).click();
  expect((await rejectedWrite).status()).toBe(403);
  expect(realRejection).toEqual({
    status: 403,
    payload: {
      error: {
        code: "origin_not_allowed",
        message: "The request Origin is not allowed",
      },
    },
  });
  expect(rejectedOriginRequests).toBe(1);
  await expect(genreInput).toHaveValue("adventure");
  await expect(
    page.getByRole("button", { name: "Save complete preference set" }),
  ).toBeEnabled();
  await expect(
    page.getByText(/protected request was not permitted|could not connect/i),
  ).toBeVisible();

  await page.unroute("**/api/v1/me/preferences");
  await page.getByRole("button", { name: "Save complete preference set" }).click();
  await expect(page.getByText("Saved preferences were updated.")).toBeVisible();
});

test("a rapid double preference action creates only one in-flight mutation", async ({
  page,
}) => {
  await openStatelessRecommendations(page);
  await enableSavedPersonalization(page);

  let releaseRequest: () => void = () => undefined;
  const requestGate = new Promise<void>((resolve) => {
    releaseRequest = resolve;
  });
  let mutationRequests = 0;
  await page.route("**/api/v1/me/preferences", async (route) => {
    if (route.request().method() !== "PUT") {
      await route.continue();
      return;
    }
    mutationRequests += 1;
    await requestGate;
    await route.continue();
  });

  await page.getByRole("textbox", { name: "Genre slugs" }).fill("strategy");
  const save = page.getByRole("button", {
    name: /Save complete preference set|Saving…/,
  });
  await save.dblclick();
  await expect(save).toBeDisabled();
  await expect.poll(() => mutationRequests).toBe(1);
  releaseRequest();
  await expect(page.getByText("Saved preferences were updated.")).toBeVisible();
  expect(mutationRequests).toBe(1);
});

test("played feedback is persisted and its score adjustment is visible", async ({
  page,
}) => {
  await openStatelessRecommendations(page);
  await enableSavedPersonalization(page);
  await saveGenrePreference(page, "strategy");
  await page.getByRole("button", { name: "Generate saved recommendations" }).click();

  const results = page.locator(".recommendation-results");
  const firstCard = results.locator(".recommendation-card").first();
  const playedTitle = (
    await firstCard.getByRole("heading", { level: 3 }).innerText()
  ).trim();
  const feedback = firstCard.getByRole("group", {
    name: `Feedback for ${playedTitle}`,
  });
  await feedback.getByRole("checkbox", { name: "Played" }).check();
  const refreshedResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/v1/me/recommendations"),
  );
  await feedback.getByRole("button", { name: "Save feedback" }).click();
  expect((await refreshedResponse).status()).toBe(200);
  await expect(
    page.getByText("Feedback saved and recommendations refreshed."),
  ).toBeVisible();

  const adjustedCard = results.locator(".recommendation-card").filter({
    has: page.getByRole("heading", { name: playedTitle }),
  });
  await expect(adjustedCard).toBeVisible();
  await adjustedCard.getByText("Inspect personalization components").click();
  await expect(adjustedCard.getByText(/factor 0\.500000/)).toBeVisible();

  await page.reload();
  await expect(page.getByText(/Saved personalization is active until/)).toBeVisible();
  const rehydratedFeedback = page.getByRole("group", {
    name: `Feedback for ${playedTitle}`,
  });
  await expect(
    rehydratedFeedback.getByRole("checkbox", { name: "Played" }),
  ).toBeChecked();
});
