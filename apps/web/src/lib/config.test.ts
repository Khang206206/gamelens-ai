import { describe, expect, it } from "vitest";

import { validateApiBaseUrl } from "@/lib/config";

describe("validateApiBaseUrl", () => {
  it("normalizes a safe HTTP URL", () => {
    expect(validateApiBaseUrl(" http://localhost:8000/v1/ ")).toBe(
      "http://localhost:8000/v1",
    );
  });

  it.each([
    undefined,
    "",
    "localhost:8000",
    "ftp://example.com",
    "https://user:secret@example.com",
    "https://example.com?token=secret",
    "https://example.com/#fragment",
  ])("rejects unsafe or incomplete input: %s", (value) => {
    expect(() => validateApiBaseUrl(value)).toThrow(/NEXT_PUBLIC_API_URL/);
  });
});
