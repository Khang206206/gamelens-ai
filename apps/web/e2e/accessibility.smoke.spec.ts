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

  await page.goto("/route-that-does-not-exist");
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: "This page is outside the catalog.",
    }),
  ).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);
});
