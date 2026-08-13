import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "@/lib/api/client";
import { ApiClientError } from "@/lib/api/errors";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

class RequestHarnessClient extends ApiClient {
  protectedGet(signal?: AbortSignal): Promise<{ status: string }> {
    return this.request<{ status: string }>("/api/v1/me", {
      access: "protected",
      signal,
    });
  }

  protectedPost(body: unknown): Promise<{ status: string }> {
    return this.request<{ status: string }>("/api/v1/anonymous-sessions", {
      method: "POST",
      access: "protected",
      body,
    });
  }

  protectedPut(body: unknown, csrfToken: string): Promise<{ status: string }> {
    return this.request<{ status: string }>("/api/v1/me/preferences", {
      method: "PUT",
      access: "protected",
      body,
      csrfToken,
    });
  }

  protectedDelete(csrfToken: string): Promise<void> {
    return this.request<void>("/api/v1/me", {
      method: "DELETE",
      access: "protected",
      csrfToken,
    });
  }
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
      expect.objectContaining({ method: "GET", credentials: "omit" }),
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
    const body = { preferred_genres: ["strategy"], top_k: 10 };

    await client.recommend(body);

    expect(transport).toHaveBeenCalledWith(
      "http://api.test/api/v1/recommendations",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(body),
        credentials: "omit",
        headers: expect.objectContaining({ "content-type": "application/json" }),
      }),
    );
  });

  it("uses credentialed no-store transport for protected GET and bootstrap POST", async () => {
    const transport = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      void input;
      void init;
      return jsonResponse({ status: "active" });
    });
    const client = new RequestHarnessClient({
      baseUrl: "http://api.test",
      fetch: transport,
    });

    await client.protectedGet();
    await client.protectedPost({ consent: true, consent_version: "stage-4-v1" });

    expect(transport).toHaveBeenNthCalledWith(
      1,
      "http://api.test/api/v1/me",
      expect.objectContaining({
        method: "GET",
        credentials: "include",
        cache: "no-store",
      }),
    );
    expect(transport).toHaveBeenNthCalledWith(
      2,
      "http://api.test/api/v1/anonymous-sessions",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        cache: "no-store",
        body: JSON.stringify({ consent: true, consent_version: "stage-4-v1" }),
      }),
    );
    expect(transport.mock.calls[0]?.[1]?.headers).not.toHaveProperty("X-CSRF-Token");
    expect(transport.mock.calls[1]?.[1]?.headers).not.toHaveProperty("X-CSRF-Token");
  });

  it("sends protected PUT JSON with CSRF without exposing it on public calls", async () => {
    const transport = vi.fn(async () => jsonResponse({ status: "saved" }));
    const client = new RequestHarnessClient({
      baseUrl: "http://api.test",
      fetch: transport,
    });
    const body = { preferred_genres: ["strategy"] };

    await client.protectedPut(body, "csrf-value");

    expect(transport).toHaveBeenCalledWith(
      "http://api.test/api/v1/me/preferences",
      expect.objectContaining({
        method: "PUT",
        credentials: "include",
        cache: "no-store",
        body: JSON.stringify(body),
        headers: expect.objectContaining({
          "content-type": "application/json",
          "X-CSRF-Token": "csrf-value",
        }),
      }),
    );
  });

  it("accepts a protected DELETE 204 response without requiring JSON", async () => {
    const transport = vi.fn(async () => new Response(null, { status: 204 }));
    const client = new RequestHarnessClient({
      baseUrl: "http://api.test",
      fetch: transport,
    });

    await expect(client.protectedDelete("csrf-value")).resolves.toBeUndefined();
    expect(transport).toHaveBeenCalledWith(
      "http://api.test/api/v1/me",
      expect.objectContaining({
        method: "DELETE",
        credentials: "include",
        cache: "no-store",
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-value" }),
      }),
    );
  });

  it("routes every typed persistence method through the protected transport", async () => {
    const transport = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) =>
      init?.method === "DELETE" ? new Response(null, { status: 204 }) : jsonResponse({}),
    );
    const client = new ApiClient({ baseUrl: "http://api.test", fetch: transport });
    const csrf = "csrf-value";

    await client.createAnonymousSession({ consent: true, consent_version: "stage-4-v1" });
    await client.getCurrentSession();
    await client.getPreferences();
    await client.replacePreferences({ preferred_genres: ["strategy"] }, csrf);
    await client.clearPreferences(csrf);
    await client.listFeedback(2, 25);
    await client.replaceGameFeedback(
      7,
      { reaction: "liked", played: true, wishlisted: false, rating: 8.5 },
      csrf,
    );
    await client.clearGameFeedback(7, csrf);
    await client.recommendPersonalized({ top_k: 10 }, csrf);
    await client.deleteCurrentSession(csrf);

    expect(transport.mock.calls.map(([input]) => input)).toEqual([
      "http://api.test/api/v1/anonymous-sessions",
      "http://api.test/api/v1/me",
      "http://api.test/api/v1/me/preferences",
      "http://api.test/api/v1/me/preferences",
      "http://api.test/api/v1/me/preferences",
      "http://api.test/api/v1/me/feedback?page=2&page_size=25",
      "http://api.test/api/v1/me/games/7/feedback",
      "http://api.test/api/v1/me/games/7/feedback",
      "http://api.test/api/v1/me/recommendations",
      "http://api.test/api/v1/me",
    ]);
    expect(
      transport.mock.calls.every(([, init]) => init?.credentials === "include"),
    ).toBe(true);
    expect(transport.mock.calls[0]?.[1]?.headers).not.toHaveProperty("X-CSRF-Token");
    for (const call of [3, 4, 6, 7, 8, 9]) {
      expect(transport.mock.calls[call]?.[1]?.headers).toHaveProperty(
        "X-CSRF-Token",
        csrf,
      );
    }
  });

  it.each([
    [401, "unauthorized"],
    [403, "forbidden"],
    [404, "not_found"],
    [409, "conflict"],
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

  it("preserves domain error details for recovery and correlation", async () => {
    const details = { generation_id: "generation-ambiguous-1" };
    const client = new ApiClient({
      baseUrl: "http://api.test",
      fetch: vi.fn(async () =>
        jsonResponse(
          {
            error: {
              code: "generation_outcome_unknown",
              message: "Commit acknowledgement was lost",
              details,
            },
          },
          503,
        ),
      ),
    });

    await expect(client.getGame(1)).rejects.toMatchObject({
      kind: "unavailable",
      status: 503,
      code: "generation_outcome_unknown",
      details,
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
