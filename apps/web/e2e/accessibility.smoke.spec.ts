import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

async function expectNoSeriousAccessibilityViolations(page: Page) {
  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact ?? ""),
  );
  expect(serious).toEqual([]);
}

test("key routes have no serious automated accessibility violations", async ({
  page,
}) => {
  await page.goto("/");
  await expectNoSeriousAccessibilityViolations(page);

  await page.goto("/games");
  await expect(
    page.getByRole("heading", { level: 2, name: "30 games found" }),
  ).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);

  await page.locator(".game-card h2 a").first().click();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);

  await page.goto("/games/not-a-number");
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "This game identifier is not valid.",
    }),
  ).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);

  await page.goto("/recommendations");
  await expect(
    page.getByRole("button", { name: "Enable saved personalization" }),
  ).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);

  const consentResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/v1/anonymous-sessions"),
  );
  await page.getByRole("button", { name: "Enable saved personalization" }).click();
  const consent = await consentResponse;
  expect(consent.status()).toBe(201);
  await expect(
    page.getByRole("heading", { name: "Review and save your durable choices" }),
  ).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);

  await page.getByRole("textbox", { name: "Genre slugs" }).fill("strategy");
  await page.getByRole("button", { name: "Save complete preference set" }).click();
  await expect(page.getByText("Saved preferences were updated.")).toBeVisible();
  await page.getByRole("button", { name: "Generate saved recommendations" }).click();
  await expect(
    page.getByRole("heading", { name: /personalized recommendations/ }),
  ).toBeFocused();
  await expect(
    page.getByRole("heading", {
      name: /Hybrid ranking applied|Saved ranking fallback/,
    }),
  ).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);

  await page.goto("/route-that-does-not-exist");
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "This page is outside the catalog.",
    }),
  ).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);
});
