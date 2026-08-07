import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "@/lib/api/client";
import { ApiClientError } from "@/lib/api/errors";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("ApiClient", () => {
  it("serializes only defined catalog parameters", async () => {
    const transport = vi.fn(async () =>
      jsonResponse({ items: [], page: 1, page_size: 20, total: 0, total_pages: 0 }),
    );
    const client = new ApiClient({
      baseUrl: "http://api.test/",
      fetch: transport,
    });

    await client.listGames({
      page: 1,
      q: "space & time",
      sort: "title",
    });

    expect(transport).toHaveBeenCalledWith(
      "http://api.test/api/v1/games?page=1&page_size=20&q=space+%26+time&sort=title",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("calls an injected fetch transport without rebinding its receiver", async () => {
    const transport = vi.fn(function (this: unknown) {
      expect(this).toBeUndefined();
      return Promise.resolve(
        jsonResponse({
          items: [],
          page: 1,
          page_size: 20,
          total: 0,
          total_pages: 0,
        }),
      );
    });
    const client = new ApiClient({ baseUrl: "http://api.test", fetch: transport });

    await client.listGames({ page: 1, sort: "popularity" });

    expect(transport).toHaveBeenCalledOnce();
  });

  it("posts typed recommendation JSON through the project client", async () => {
    const transport = vi.fn(async () =>
      jsonResponse({
        model: { name: "content", version: "1", data_fingerprint: "abc" },
        response_reason: "no_content_support",
        requested_top_k: 5,
        items: [],
      }),
    );
    const client = new ApiClient({ baseUrl: "http://api.test", fetch: transport });
    const body = { preferred_genres: ["strategy"] };

    await client.recommend(body);

    expect(transport).toHaveBeenCalledWith(
      "http://api.test/api/v1/recommendations",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(body),
        headers: expect.objectContaining({ "content-type": "application/json" }),
      }),
    );
  });

  it.each([
    [404, "not_found"],
    [422, "validation"],
    [503, "unavailable"],
    [500, "unavailable"],
  ] as const)("normalizes HTTP %s as %s", async (status, kind) => {
    const client = new ApiClient({
      baseUrl: "http://api.test",
      fetch: vi.fn(async () =>
        jsonResponse(
          { error: { code: "safe_code", message: "internal detail" } },
          status,
        ),
      ),
    });

    await expect(client.getGame(999)).rejects.toMatchObject({
      kind,
      status,
      code: "safe_code",
    });
  });

  it("rejects non-JSON and malformed JSON responses", async () => {
    const nonJson = new ApiClient({
      baseUrl: "http://api.test",
      fetch: vi.fn(async () => new Response("<html>broken</html>")),
    });
    await expect(nonJson.getGame(1)).rejects.toMatchObject({
      kind: "invalid_response",
    });

    const malformed = new ApiClient({
      baseUrl: "http://api.test",
      fetch: vi.fn(
        async () =>
          new Response("{", { headers: { "content-type": "application/json" } }),
      ),
    });
    await expect(malformed.getGame(1)).rejects.toMatchObject({
      kind: "invalid_response",
    });
  });

  it("normalizes network and abort failures", async () => {
    const networkClient = new ApiClient({
      baseUrl: "http://api.test",
      fetch: vi.fn(async () => {
        throw new TypeError("connection refused with secret detail");
      }),
    });
    await expect(networkClient.getGame(1)).rejects.toMatchObject({
      kind: "network",
      message: "We could not connect to the game catalog.",
    });

    const abortClient = new ApiClient({
      baseUrl: "http://api.test",
      fetch: vi.fn(async () => {
        throw new DOMException("Aborted", "AbortError");
      }),
    });
    await expect(abortClient.getGame(1)).rejects.toBeInstanceOf(ApiClientError);
    await expect(abortClient.getGame(1)).rejects.toMatchObject({ kind: "aborted" });
  });
});
