import { describe, expect, it } from "vitest";

import {
  formatRating,
  formatRatingCount,
  formatReleaseDate,
  formatStudio,
} from "@/lib/format";

describe("format helpers", () => {
  it("formats reader-facing values consistently", () => {
    expect(formatReleaseDate("2024-09-20")).toBe("Sep 20, 2024");
    expect(formatRating(8.25)).toBe("8.3 / 10");
    expect(formatRatingCount(12_440)).toBe("12,440 ratings");
  });

  it("renders intentional null fallbacks", () => {
    expect(formatReleaseDate(null)).toBe("Release date not listed");
    expect(formatReleaseDate("not-a-date")).toBe("Release date not listed");
    expect(formatRating(null)).toBe("Not rated");
    expect(formatStudio(null)).toBe("Not listed");
  });
});
