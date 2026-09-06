import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

import { captureSavedGeneration, expectNoPageOverflow } from "./hybrid-fixture-helpers";

test.skip(
  process.env.COLLABORATIVE_FIXTURE_E2E !== "1",
  "Requires the explicit project-authored collaborative fixture stack",
);

async function tabTo(page: Page, target: Locator, limit = 100) {
  for (let step = 0; step < limit; step += 1) {
    await page.keyboard.press("Tab");
    if (await target.evaluate((element) => element === document.activeElement)) return;
  }
  throw new Error(`Keyboard focus did not reach the target within ${limit} tabs`);
}

test("the project-authored synthetic fixture gives functional hybrid evidence without a quality claim", async ({
  page,
}, testInfo) => {
  await page.goto("/recommendations");
  const enable = page.getByRole("button", { name: "Enable saved personalization" });
  await tabTo(page, enable);
  const consentResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/v1/anonymous-sessions"),
  );
  await page.keyboard.press("Enter");
  expect((await consentResponse).status()).toBe(201);
  await expect(
    page.getByRole("heading", { name: "Review and save your durable choices" }),
  ).toBeVisible();

  const gameIds = page.getByRole("textbox", { name: "Example game IDs" });
  await tabTo(page, gameIds);
  await gameIds.fill("1");
  await page.keyboard.press("Tab");
  const save = page.getByRole("button", { name: "Save complete preference set" });
  await tabTo(page, save);
  const savedResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "PUT" &&
      response.url().endsWith("/api/v1/me/preferences"),
  );
  await page.keyboard.press("Enter");
  expect((await savedResponse).status()).toBe(200);
  await expect(page.getByText("Saved preferences were updated.")).toBeVisible();

  const generate = page.getByRole("button", {
    name: "Generate saved recommendations",
  });
  await tabTo(page, generate);
  const result = await captureSavedGeneration(page, testInfo, async () => {
    await page.keyboard.press("Enter");
  });
  expect(result.ranking_mode).toBe("hybrid");
  expect(result.items.some((item) => item.collaborative_supported)).toBe(true);
  await expect(
    page.getByRole("heading", { name: /personalized recommendations/ }),
  ).toBeFocused();
  await expect(
    page.getByRole("heading", { name: "Hybrid ranking applied" }),
  ).toBeVisible();
  await expect(
    page.getByText(/This is ranking evidence, not a quality claim or social proof/),
  ).toBeVisible();

  const evidence = page.locator(".aggregate-evidence").first();
  await expect(
    evidence.getByRole("heading", { name: "Aggregate interaction evidence" }),
  ).toBeVisible();
  await expect(
    evidence.getByText(/individual identities are not included here/),
  ).toBeVisible();

  const disclosure = page
    .locator(".recommendation-card")
    .first()
    .getByText("Inspect personalization components");
  await tabTo(page, disclosure);
  await page.keyboard.press("Enter");
  await expect(disclosure.locator("..")).toHaveAttribute("open", "");

  for (const viewport of [
    { width: 320, height: 720 },
    { width: 768, height: 900 },
    { width: 1440, height: 900 },
  ]) {
    await page.setViewportSize(viewport);
    await expectNoPageOverflow(page);
  }

  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(
    accessibility.violations.filter((violation) =>
      ["serious", "critical"].includes(violation.impact ?? ""),
    ),
  ).toEqual([]);
});
