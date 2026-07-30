import { expect, test } from "@playwright/test";

test("URL-backed search, filter, sorting, and pagination remain shareable", async ({
  page,
}) => {
  await page.goto("/games?q=signal&sort=title");
  await expect(
    page.getByRole("heading", { level: 2, name: "2 games found" }),
  ).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "Search game titles" })).toHaveValue(
    "signal",
  );

  await page.getByLabel("Genre").selectOption("adventure");
  await expect(page).toHaveURL(/genre=adventure/);
  await expect(page).not.toHaveURL(/page=/);

  await page.getByLabel("Tag").selectOption("space");
  await expect(page).toHaveURL(/tag=space/);

  await page.getByLabel("Platform").selectOption("windows");
  await expect(page).toHaveURL(/platform=windows/);

  await page.getByLabel("Sort by").selectOption("rating");
  await expect(page).toHaveURL(/sort=rating/);
  await page.reload();
  await expect(page.getByLabel("Genre")).toHaveValue("adventure");
  await expect(page.getByLabel("Tag")).toHaveValue("space");
  await expect(page.getByLabel("Platform")).toHaveValue("windows");
  await expect(page.getByLabel("Sort by")).toHaveValue("rating");

  await page.getByRole("link", { name: "Clear all", exact: true }).click();
  await expect(page).toHaveURL(/\/games$/);
  await page.getByRole("link", { name: /Next/ }).click();
  await expect(page).toHaveURL(/page=2/);
  await expect(page.getByText("Page 2 of 2")).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/\/games$/);
  await page.goForward();
  await expect(page).toHaveURL(/page=2/);
});

test("an in-progress search draft survives filter navigation", async ({ page }) => {
  await page.goto("/games");
  const search = page.getByRole("searchbox", { name: "Search game titles" });
  await search.fill("  signal  ");

  await page.getByLabel("Genre").selectOption("adventure");
  await expect(page).toHaveURL(/genre=adventure/);
  await expect(search).toHaveValue("  signal  ");

  await page.getByRole("button", { name: "Search" }).click();
  await expect(page).toHaveURL(/q=signal/);
  await expect(page).toHaveURL(/genre=adventure/);
  await expect(search).toHaveValue("signal");
});

test("rapid filter changes compose instead of overwriting one another", async ({
  page,
}) => {
  await page.goto("/games");

  await page.getByLabel("Genre").selectOption("adventure");
  await page.getByLabel("Tag").selectOption("co-op");

  await expect(page).toHaveURL(/genre=adventure/);
  await expect(page).toHaveURL(/tag=co-op/);
});

test("every sort option remains URL backed", async ({ page }) => {
  await page.goto("/games");

  for (const sort of ["rating", "release_date", "title", "popularity"]) {
    await page.getByLabel("Sort by").selectOption(sort);
    if (sort === "popularity") {
      await expect(page).not.toHaveURL(/sort=/);
    } else {
      await expect(page).toHaveURL(new RegExp(`sort=${sort}`));
    }
  }
});

test("invalid catalog links are rejected before the API request", async ({ page }) => {
  let catalogRequests = 0;
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/games")) catalogRequests += 1;
  });

  await page.goto("/games?page=0&sort=random");
  await expect(
    page.getByRole("heading", { name: "Some URL values need attention." }),
  ).toBeVisible();
  expect(catalogRequests).toBe(0);
});

test("invalid and missing game IDs have deliberate states", async ({ page }) => {
  let detailRequests = 0;
  page.on("request", (request) => {
    if (/\/api\/v1\/games\/[^?]+$/.test(request.url())) detailRequests += 1;
  });

  await page.goto("/games/not-a-number");
  await expect(
    page.getByRole("heading", { name: "This game identifier is not valid." }),
  ).toBeVisible();
  expect(detailRequests).toBe(0);

  await page.goto("/games/999999");
  await expect(
    page.getByRole("heading", { name: "This title is not in the archive." }),
  ).toBeVisible();
});

test("catalog and metadata failures remain recoverable", async ({ page }) => {
  await page.route("**/api/v1/metadata/genres", (route) => route.abort());
  await page.goto("/games");
  await expect(
    page.getByRole("heading", { level: 2, name: "30 games found" }),
  ).toBeVisible();
  await expect(page.getByText(/Could not load genres/)).toBeVisible();

  await page.route("**/api/v1/games?*", (route) => route.abort());
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "We could not reach the catalog." }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  await page.unroute("**/api/v1/games?*");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(
    page.getByRole("heading", { level: 2, name: "30 games found" }),
  ).toBeVisible();
  await expect(page.getByText(/Catalog online/i)).toHaveCount(0);
});

test("empty, filtered-empty, and out-of-range states stay distinct", async ({ page }) => {
  await page.goto("/games?genre=taxonomy-that-does-not-exist");
  await expect(
    page.getByRole("heading", { name: "No games match this combination." }),
  ).toBeVisible();

  await page.goto("/games?page=999");
  await expect(
    page.getByRole("heading", {
      name: "There are no games this far into the catalog.",
    }),
  ).toBeVisible();

  await page.route("**/api/v1/games?*", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
      }),
    }),
  );
  await page.goto("/games");
  await expect(
    page.getByRole("heading", { name: "The catalog has not been populated yet." }),
  ).toBeVisible();
});

test("detail requests recover after a transient failure", async ({ page }) => {
  await page.route("**/api/v1/games/1", (route) => route.abort());
  await page.goto("/games/1");
  await expect(
    page.getByRole("heading", { level: 1, name: "We could not load this game." }),
  ).toBeVisible();

  await page.unroute("**/api/v1/games/1");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Emberfall Tactics" }),
  ).toBeVisible();
});
