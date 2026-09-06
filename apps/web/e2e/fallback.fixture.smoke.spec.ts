import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import {
  exerciseBrowserFallback,
  expectedBrowserFallbackReason,
} from "./fallback-fixture-helpers";
import { expectNoPageOverflow } from "./hybrid-fixture-helpers";

test.skip(
  process.env.COLLABORATIVE_FALLBACK_E2E !== "1",
  "Requires an explicitly selected disposable fallback fixture stack",
);

test("cold start remains an accessible exact fallback across browsers", async ({
  page,
  request,
}, testInfo) => {
  const reason = expectedBrowserFallbackReason();
  expect(reason).toBe("no_supported_sources");
  await exerciseBrowserFallback(page, request, testInfo, reason);

  await page.setViewportSize({ width: 320, height: 720 });
  await expectNoPageOverflow(page);
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(
    accessibility.violations.filter((violation) =>
      ["serious", "critical"].includes(violation.impact ?? ""),
    ),
  ).toEqual([]);
});
