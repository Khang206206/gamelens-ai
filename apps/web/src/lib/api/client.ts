import type { components } from "@/lib/api/generated";
import {
  ApiClientError,
  errorFromResponse,
  normalizeRequestError,
} from "@/lib/api/errors";
import { getPublicConfig, validateApiBaseUrl } from "@/lib/config";

export type GamePage = components["schemas"]["GamePage"];
export type GameSummary = components["schemas"]["GameSummary"];
export type GameDetail = components["schemas"]["GameDetail"];
export type TaxonomyItem = components["schemas"]["TaxonomyItem"];
export type RecommendationRequest = components["schemas"]["RecommendationRequest"];
export type RecommendationResponse = components["schemas"]["RecommendationResponse"];
export type AnonymousSessionConsentRequest =
  components["schemas"]["AnonymousSessionConsentRequest"];
export type AnonymousSessionResponse = components["schemas"]["AnonymousSessionResponse"];
export type PreferenceReplaceRequest = components["schemas"]["PreferenceReplaceRequest"];
export type PreferenceResponse = components["schemas"]["PreferenceResponse"];
export type FeedbackReplaceRequest = components["schemas"]["FeedbackReplaceRequest"];
export type FeedbackResource = components["schemas"]["FeedbackResource"];
export type FeedbackPage = components["schemas"]["FeedbackPage"];
export type PersonalizedRecommendationRequest =
  components["schemas"]["PersonalizedRecommendationRequest"];
export type PersonalizedRecommendationResponse =
  components["schemas"]["PersonalizedRecommendationResponse"];

export type CatalogSort = "popularity" | "rating" | "release_date" | "title";

export interface CatalogRequest {
  page: number;
  pageSize?: number;
  q?: string;
  genre?: string;
  tag?: string;
  platform?: string;
  sort: CatalogSort;
}

export type FetchTransport = typeof fetch;

export interface ApiClientOptions {
  baseUrl?: string;
  fetch?: FetchTransport;
}

type ApiHttpMethod = "GET" | "POST" | "PUT" | "DELETE";
type ApiRequestAccess = "public" | "protected";

interface ApiRequestOptions {
  method?: ApiHttpMethod;
  access?: ApiRequestAccess;
  body?: unknown;
  csrfToken?: string;
  signal?: AbortSignal;
}

function buildQuery(values: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== "") {
      search.set(key, String(value));
    }
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly transport: FetchTransport;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = options.baseUrl
      ? validateApiBaseUrl(options.baseUrl)
      : getPublicConfig().apiBaseUrl;
    this.transport = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  async listGames(request: CatalogRequest, signal?: AbortSignal): Promise<GamePage> {
    const query = buildQuery({
      page: request.page,
      page_size: request.pageSize ?? 20,
      q: request.q,
      genre: request.genre,
      tag: request.tag,
      platform: request.platform,
      sort: request.sort,
    });
    return this.request<GamePage>(`/api/v1/games${query}`, { signal });
  }

  async getGame(gameId: number, signal?: AbortSignal): Promise<GameDetail> {
    return this.request<GameDetail>(`/api/v1/games/${gameId}`, { signal });
  }

  async listGenres(signal?: AbortSignal): Promise<TaxonomyItem[]> {
    return this.request<TaxonomyItem[]>("/api/v1/metadata/genres", { signal });
  }

  async listTags(signal?: AbortSignal): Promise<TaxonomyItem[]> {
    return this.request<TaxonomyItem[]>("/api/v1/metadata/tags", { signal });
  }

  async listPlatforms(signal?: AbortSignal): Promise<TaxonomyItem[]> {
    return this.request<TaxonomyItem[]>("/api/v1/metadata/platforms", { signal });
  }

  async recommend(
    request: RecommendationRequest,
    signal?: AbortSignal,
  ): Promise<RecommendationResponse> {
    return this.request<RecommendationResponse>("/api/v1/recommendations", {
      method: "POST",
      body: request,
      signal,
    });
  }

  async createAnonymousSession(
    body: AnonymousSessionConsentRequest,
    csrfToken?: string,
    signal?: AbortSignal,
  ): Promise<AnonymousSessionResponse> {
    return this.request<AnonymousSessionResponse>("/api/v1/anonymous-sessions", {
      method: "POST",
      access: "protected",
      body,
      csrfToken,
      signal,
    });
  }

  async getCurrentSession(signal?: AbortSignal): Promise<AnonymousSessionResponse> {
    return this.request<AnonymousSessionResponse>("/api/v1/me", {
      access: "protected",
      signal,
    });
  }

  async deleteCurrentSession(csrfToken: string, signal?: AbortSignal): Promise<void> {
    return this.request<void>("/api/v1/me", {
      method: "DELETE",
      access: "protected",
      csrfToken,
      signal,
    });
  }

  async getPreferences(signal?: AbortSignal): Promise<PreferenceResponse> {
    return this.request<PreferenceResponse>("/api/v1/me/preferences", {
      access: "protected",
      signal,
    });
  }

  async replacePreferences(
    body: PreferenceReplaceRequest,
    csrfToken: string,
    signal?: AbortSignal,
  ): Promise<PreferenceResponse> {
    return this.request<PreferenceResponse>("/api/v1/me/preferences", {
      method: "PUT",
      access: "protected",
      body,
      csrfToken,
      signal,
    });
  }

  async clearPreferences(csrfToken: string, signal?: AbortSignal): Promise<void> {
    return this.request<void>("/api/v1/me/preferences", {
      method: "DELETE",
      access: "protected",
      csrfToken,
      signal,
    });
  }

  async listFeedback(
    page = 1,
    pageSize = 50,
    signal?: AbortSignal,
  ): Promise<FeedbackPage> {
    const query = buildQuery({ page, page_size: pageSize });
    return this.request<FeedbackPage>(`/api/v1/me/feedback${query}`, {
      access: "protected",
      signal,
    });
  }

  async replaceGameFeedback(
    gameId: number,
    body: FeedbackReplaceRequest,
    csrfToken: string,
    signal?: AbortSignal,
  ): Promise<FeedbackResource | null> {
    return this.request<FeedbackResource | null>(`/api/v1/me/games/${gameId}/feedback`, {
      method: "PUT",
      access: "protected",
      body,
      csrfToken,
      signal,
    });
  }

  async clearGameFeedback(
    gameId: number,
    csrfToken: string,
    signal?: AbortSignal,
  ): Promise<void> {
    return this.request<void>(`/api/v1/me/games/${gameId}/feedback`, {
      method: "DELETE",
      access: "protected",
      csrfToken,
      signal,
    });
  }

  async recommendPersonalized(
    body: PersonalizedRecommendationRequest,
    csrfToken: string,
    signal?: AbortSignal,
  ): Promise<PersonalizedRecommendationResponse> {
    return this.request<PersonalizedRecommendationResponse>(
      "/api/v1/me/recommendations",
      {
        method: "POST",
        access: "protected",
        body,
        csrfToken,
        signal,
      },
    );
  }

  protected async request<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
    try {
      const transport = this.transport;
      const protectedRequest = options.access === "protected";
      const response = await transport(`${this.baseUrl}${path}`, {
        method: options.method ?? "GET",
        headers: {
          accept: "application/json",
          ...(options.body === undefined ? {} : { "content-type": "application/json" }),
          ...(protectedRequest && options.csrfToken !== undefined
            ? { "X-CSRF-Token": options.csrfToken }
            : {}),
        },
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        credentials: protectedRequest ? "include" : "omit",
        ...(protectedRequest ? { cache: "no-store" } : {}),
        signal: options.signal,
      });

      if (response.status === 204) {
        return undefined as T;
      }

      const contentType = response.headers.get("content-type") ?? "";
      if (!contentType.toLowerCase().includes("application/json")) {
        throw new ApiClientError({
          kind: "invalid_response",
          status: response.status,
          message: "The catalog returned an unreadable response.",
        });
      }

      let payload: unknown;
      try {
        payload = await response.json();
      } catch (error) {
        throw new ApiClientError({
          kind: "invalid_response",
          status: response.status,
          message: "The catalog returned malformed JSON.",
          cause: error,
        });
      }

      if (!response.ok) {
        throw errorFromResponse(response.status, payload);
      }
      return payload as T;
    } catch (error) {
      throw normalizeRequestError(error);
    }
  }
}

let browserClient: ApiClient | undefined;

export function getApiClient(): ApiClient {
  browserClient ??= new ApiClient();
  return browserClient;
}
