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

test("saved personalization remains usable without overflow at representative viewports", async ({
  page,
}) => {
  await page.goto("/recommendations");
  const consentResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith("/api/v1/anonymous-sessions"),
  );
  await page.getByRole("button", { name: "Enable saved personalization" }).click();
  expect((await consentResponse).status()).toBe(201);
  await page.getByRole("textbox", { name: "Genre slugs" }).fill("strategy");
  await page.getByRole("button", { name: "Save complete preference set" }).click();
  await expect(page.getByText("Saved preferences were updated.")).toBeVisible();

  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.getByRole("button", { name: "Generate saved recommendations" }).click();
  await expect(
    page.getByRole("heading", { name: /personalized recommendations/ }),
  ).toBeVisible();

  for (const viewport of [
    { width: 320, height: 720 },
    { width: 768, height: 900 },
    { width: 1440, height: 900 },
  ]) {
    await page.setViewportSize(viewport);
    await expectNoPageOverflow(page);
  }
  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});
