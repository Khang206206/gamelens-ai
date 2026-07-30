import { expect, test } from "@playwright/test";

test("anonymous user can browse from landing to a game and back", async ({ page }) => {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/");
  await expect(
    page.getByRole("heading", { level: 1, name: /Find your next world/ }),
  ).toBeVisible();
  await page.getByRole("link", { name: /Explore the catalog/ }).click();

  await expect(page).toHaveURL(/\/games$/);
  await expect(
    page.getByRole("heading", { level: 2, name: "30 games found" }),
  ).toBeVisible();

  const firstGame = page.locator(".game-card h2 a").first();
  const gameTitle = await firstGame.textContent();
  await firstGame.click();
  await expect(page).toHaveURL(/\/games\/\d+$/);
  await expect(
    page.getByRole("heading", { level: 1, name: gameTitle ?? "" }),
  ).toBeVisible();

  await page.getByRole("button", { name: /Back to previous view/ }).click();
  await expect(page).toHaveURL(/\/games$/);
  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});

test("the shell navigation remains visible and keyboard reachable on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto("/");

  await expect(page.getByRole("link", { name: "GameLens AI home" })).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Primary navigation" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Overview" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Game catalog" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Explore the catalog/ })).toBeVisible();

  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "GameLens AI home" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Overview" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Game catalog" })).toBeFocused();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(overflow).toBe(false);
});

test("catalog and detail layouts do not overflow representative viewports", async ({
  page,
}) => {
  for (const viewport of [
    { width: 320, height: 720 },
    { width: 768, height: 900 },
    { width: 1440, height: 900 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/games");
    await expect(
      page.getByRole("heading", { level: 2, name: "30 games found" }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
      ),
    ).toBe(false);

    await page.goto("/games/1");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
      ),
    ).toBe(false);
  }
});
