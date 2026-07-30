import type { CatalogSort } from "@/lib/api/client";

export const MAX_CATALOG_PAGE = 1_000_000;
export const MAX_GAME_ID = 2_147_483_647;
export const MAX_SEARCH_LENGTH = 200;
export const DEFAULT_CATALOG_SORT: CatalogSort = "popularity";

const SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const SORT_VALUES: readonly CatalogSort[] = [
  "popularity",
  "rating",
  "release_date",
  "title",
];

interface SearchParamsReader {
  get(name: string): string | null;
}

export interface CatalogQuery {
  q?: string;
  genre?: string;
  tag?: string;
  platform?: string;
  sort: CatalogSort;
  page: number;
}

export type CatalogQueryField = "q" | "genre" | "tag" | "platform" | "sort" | "page";

export interface CatalogQueryIssue {
  field: CatalogQueryField;
  message: string;
}

export type CatalogQueryResult =
  { ok: true; value: CatalogQuery } | { ok: false; issues: CatalogQueryIssue[] };

export function parseCatalogQuery(params: SearchParamsReader): CatalogQueryResult {
  const issues: CatalogQueryIssue[] = [];
  const rawSearch = params.get("q");
  const q = rawSearch?.trim() || undefined;

  if (q && q.length > MAX_SEARCH_LENGTH) {
    issues.push({
      field: "q",
      message: `Search must be ${MAX_SEARCH_LENGTH} characters or fewer.`,
    });
  }

  const pageValue = params.get("page");
  let page = 1;
  if (pageValue !== null) {
    if (!/^[1-9]\d*$/.test(pageValue)) {
      issues.push({ field: "page", message: "Page must be a positive integer." });
    } else {
      page = Number(pageValue);
      if (page > MAX_CATALOG_PAGE) {
        issues.push({
          field: "page",
          message: `Page cannot be greater than ${MAX_CATALOG_PAGE.toLocaleString("en-US")}.`,
        });
      }
    }
  }

  const rawSort = params.get("sort");
  const sort = (rawSort ?? DEFAULT_CATALOG_SORT) as CatalogSort;
  if (rawSort !== null && !SORT_VALUES.includes(sort)) {
    issues.push({
      field: "sort",
      message: "Sort must be popularity, rating, release date, or title.",
    });
  }

  const taxonomies = {
    genre: params.get("genre") || undefined,
    tag: params.get("tag") || undefined,
    platform: params.get("platform") || undefined,
  };
  for (const [field, value] of Object.entries(taxonomies)) {
    if (value && !SLUG_PATTERN.test(value)) {
      issues.push({
        field: field as "genre" | "tag" | "platform",
        message: `${field[0].toUpperCase()}${field.slice(1)} must be a valid catalog slug.`,
      });
    }
  }

  if (issues.length > 0) {
    return { ok: false, issues };
  }
  return {
    ok: true,
    value: {
      q,
      ...taxonomies,
      sort,
      page,
    },
  };
}

export function catalogQueryToSearchParams(query: CatalogQuery): URLSearchParams {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  if (query.genre) params.set("genre", query.genre);
  if (query.tag) params.set("tag", query.tag);
  if (query.platform) params.set("platform", query.platform);
  if (query.sort !== DEFAULT_CATALOG_SORT) params.set("sort", query.sort);
  if (query.page > 1) params.set("page", String(query.page));
  return params;
}

export function catalogHref(query: CatalogQuery): "/games" | `/games?${string}` {
  const search = catalogQueryToSearchParams(query).toString();
  return search ? `/games?${search}` : "/games";
}

export function parseGameId(value: string): number | null {
  if (!/^[1-9]\d*$/.test(value)) {
    return null;
  }
  const gameId = Number(value);
  return Number.isSafeInteger(gameId) && gameId <= MAX_GAME_ID ? gameId : null;
}
