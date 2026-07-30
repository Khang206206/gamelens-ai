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
    return this.request<GamePage>(`/api/v1/games${query}`, signal);
  }

  async getGame(gameId: number, signal?: AbortSignal): Promise<GameDetail> {
    return this.request<GameDetail>(`/api/v1/games/${gameId}`, signal);
  }

  async listGenres(signal?: AbortSignal): Promise<TaxonomyItem[]> {
    return this.request<TaxonomyItem[]>("/api/v1/metadata/genres", signal);
  }

  async listTags(signal?: AbortSignal): Promise<TaxonomyItem[]> {
    return this.request<TaxonomyItem[]>("/api/v1/metadata/tags", signal);
  }

  async listPlatforms(signal?: AbortSignal): Promise<TaxonomyItem[]> {
    return this.request<TaxonomyItem[]>("/api/v1/metadata/platforms", signal);
  }

  private async request<T>(path: string, signal?: AbortSignal): Promise<T> {
    try {
      const transport = this.transport;
      const response = await transport(`${this.baseUrl}${path}`, {
        method: "GET",
        headers: { accept: "application/json" },
        signal,
      });

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
