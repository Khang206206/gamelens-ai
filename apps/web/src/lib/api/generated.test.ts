import { describe, expect, it } from "vitest";

import type { components } from "@/lib/api/generated";

type ModelStatusResponse = components["schemas"]["ModelStatusResponse"];

const legacyModelStatus = {
  status: "ready",
  active_model: {
    name: "content-recommender",
    version: "1.0.0",
    data_fingerprint: "a".repeat(64),
  },
  capabilities: {
    recommend: true,
    explanations: true,
  },
} satisfies ModelStatusResponse;

describe("generated API contract", () => {
  it("keeps Stage 4 model status consumers compatible with optional component metadata", () => {
    expect(legacyModelStatus).not.toHaveProperty("components");
    expect(legacyModelStatus.status).toBe("ready");
  });
});
