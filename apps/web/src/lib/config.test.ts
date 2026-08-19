import { describe, expect, it } from "vitest";

import {
  resolveConsentVersion,
  validateApiBaseUrl,
  validateConsentVersion,
} from "@/lib/config";

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

describe("validateConsentVersion", () => {
  it("normalizes a configured version", () => {
    expect(validateConsentVersion(" stage-4-v1 ")).toBe("stage-4-v1");
  });

  it.each([undefined, "", "   ", "x".repeat(101)])("rejects invalid input", (value) => {
    expect(() => validateConsentVersion(value)).toThrow(/NEXT_PUBLIC_CONSENT_VERSION/);
  });

  it("uses the reviewed default outside production only", () => {
    expect(resolveConsentVersion(undefined, "development")).toBe("stage-4-v1");
    expect(resolveConsentVersion(undefined, "test")).toBe("stage-4-v1");
    expect(() => resolveConsentVersion(undefined, "production")).toThrow(
      /NEXT_PUBLIC_CONSENT_VERSION/,
    );
  });
});
