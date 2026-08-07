import { expect, test, type Page } from "@playwright/test";

async function expectNoPageOverflow(page: Page) {
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

test("recommendation layout does not overflow representative viewports", async ({
  page,
}) => {
  for (const viewport of [
    { width: 320, height: 720 },
    { width: 768, height: 900 },
    { width: 1440, height: 900 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/recommendations");
    await expect(page.getByRole("button", { name: "Review selections" })).toBeVisible();
    await expectNoPageOverflow(page);

    await page
      .getByRole("group", { name: /Preferred genres/ })
      .getByLabel("Strategy")
      .check();
    await page.getByRole("button", { name: "Review selections" }).click();
    await expect(
      page.getByRole("heading", { name: "Ready for the content model" }),
    ).toBeFocused();
    await expectNoPageOverflow(page);

    await page.getByRole("button", { name: "Get recommendations" }).click();
    await expect(
      page.getByRole("heading", { name: /ranked recommendations/ }),
    ).toBeFocused();
    await expectNoPageOverflow(page);
  }
});
