import { describe, expect, it } from "vitest";

import { catalogHref, parseCatalogQuery, parseGameId } from "@/lib/routes";

describe("parseCatalogQuery", () => {
  it("normalizes the default query", () => {
    expect(parseCatalogQuery(new URLSearchParams())).toEqual({
      ok: true,
      value: { q: undefined, page: 1, sort: "popularity" },
    });
  });

  it("parses shareable catalog state", () => {
    const result = parseCatalogQuery(
      new URLSearchParams(
        "q=space+crew&genre=adventure&tag=co-op&platform=windows&sort=rating&page=2",
      ),
    );
    expect(result).toEqual({
      ok: true,
      value: {
        q: "space crew",
        genre: "adventure",
        tag: "co-op",
        platform: "windows",
        sort: "rating",
        page: 2,
      },
    });
  });

  it.each([
    "page=0",
    "page=1.5",
    "page=1000001",
    "sort=random",
    "genre=Action",
    "tag=two--words",
    `q=${"x".repeat(201)}`,
  ])("rejects invalid state without issuing a request: %s", (query) => {
    expect(parseCatalogQuery(new URLSearchParams(query)).ok).toBe(false);
  });

  it("omits defaults and encodes reserved search characters", () => {
    expect(
      catalogHref({
        q: "rpg & puzzles",
        sort: "popularity",
        page: 1,
      }),
    ).toBe("/games?q=rpg+%26+puzzles");
  });
});

describe("parseGameId", () => {
  it.each([
    ["1", 1],
    ["2147483647", 2_147_483_647],
    ["0", null],
    ["-1", null],
    ["01", null],
    ["1.5", null],
    ["game", null],
    ["2147483648", null],
  ])("maps %s to %s", (value, expected) => {
    expect(parseGameId(value)).toBe(expected);
  });
});
