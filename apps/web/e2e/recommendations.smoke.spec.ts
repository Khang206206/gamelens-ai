import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

async function tabTo(page: Page, target: Locator, limit = 100) {
  for (let step = 0; step < limit; step += 1) {
    await page.keyboard.press("Tab");
    if (await target.evaluate((element) => element === document.activeElement)) return;
  }
  throw new Error(`Keyboard focus did not reach the target within ${limit} tabs`);
}

test("keyboard user receives explained artifact-backed recommendations", async ({
  page,
}) => {
  const recommendationBodies: unknown[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith("/api/v1/recommendations")) {
      recommendationBodies.push(request.postDataJSON());
    }
  });

  await page.goto("/recommendations");
  await expect(
    page.getByRole("heading", { level: 1, name: "Shape your next shortlist" }),
  ).toBeVisible();

  const strategy = page
    .getByRole("group", { name: /Preferred genres/ })
    .getByLabel("Strategy");
  await tabTo(page, strategy);
  await page.keyboard.press("Space");
  await expect(strategy).toBeChecked();

  const linux = page
    .getByRole("group", { name: /Preferred platforms/ })
    .getByLabel("Linux");
  await tabTo(page, linux);
  await page.keyboard.press("Space");
  await expect(linux).toBeChecked();

  const review = page.getByRole("button", { name: "Review selections" });
  await tabTo(page, review);
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Ready for the content model" }),
  ).toBeFocused();
  await expect(page.getByText(/does not create a user/)).toBeVisible();

  const submit = page.getByRole("button", { name: "Get recommendations" });
  await tabTo(page, submit);
  await page.keyboard.press("Enter");

  await expect(
    page.getByRole("heading", { name: /ranked recommendations/ }),
  ).toBeFocused();
  await expect(page.getByText(/Ranking score/).first()).toBeVisible();
  expect(recommendationBodies).toEqual([
    expect.objectContaining({
      preferred_genres: ["strategy"],
      preferred_platforms: ["linux"],
    }),
  ]);

  const scoreDetails = page.getByText("Inspect score components").first();
  await tabTo(page, scoreDetails);
  await page.keyboard.press("Enter");
  await expect(scoreDetails.locator("..")).toHaveAttribute("open", "");

  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(
    accessibility.violations.filter((violation) =>
      ["serious", "critical"].includes(violation.impact ?? ""),
    ),
  ).toEqual([]);
});
