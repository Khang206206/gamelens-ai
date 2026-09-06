import { test } from "@playwright/test";

import {
  exerciseBrowserFallback,
  expectedBrowserFallbackReason,
} from "./fallback-fixture-helpers";

test.skip(
  process.env.COLLABORATIVE_FALLBACK_E2E !== "1",
  "Requires an explicitly selected disposable fallback fixture stack",
);

test("an absent or invalid optional artifact preserves the exact Stage 4 browser result", async ({
  page,
  request,
}, testInfo) => {
  await exerciseBrowserFallback(page, request, testInfo, expectedBrowserFallbackReason());
});
