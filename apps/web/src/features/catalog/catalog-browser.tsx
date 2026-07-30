"use client";

import type { Route } from "next";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { GameCard } from "@/components/ui/game-card";
import { CatalogSkeleton } from "@/components/ui/loading";
import { StateNotice } from "@/components/ui/state-notice";
import {
  type CatalogSort,
  type GamePage,
  getApiClient,
  type TaxonomyItem,
} from "@/lib/api/client";
import { ApiClientError } from "@/lib/api/errors";
import {
  catalogHref,
  type CatalogQuery,
  DEFAULT_CATALOG_SORT,
  MAX_SEARCH_LENGTH,
  parseCatalogQuery,
} from "@/lib/routes";

interface MetadataState {
  requestKey: number;
  loading: boolean;
  genres: TaxonomyItem[];
  tags: TaxonomyItem[];
  platforms: TaxonomyItem[];
  failedLabels: string[];
}

interface SearchDraftState {
  committedValue: string;
  value: string;
}

type CatalogState =
  | { status: "loading"; requestKey: string }
  | { status: "ready"; requestKey: string; data: GamePage }
  | { status: "error"; requestKey: string; error: ApiClientError };

const sortOptions: { value: CatalogSort; label: string }[] = [
  { value: "popularity", label: "Catalog popularity" },
  { value: "rating", label: "Rating" },
  { value: "release_date", label: "Release date" },
  { value: "title", label: "Title A–Z" },
];

const defaultQuery: CatalogQuery = {
  page: 1,
  sort: DEFAULT_CATALOG_SORT,
};

function selectedFallback(
  options: TaxonomyItem[],
  selected: string | undefined,
): TaxonomyItem[] {
  if (!selected || options.some((item) => item.slug === selected)) return options;
  return [{ id: -1, name: selected.replaceAll("-", " "), slug: selected }, ...options];
}

export function CatalogBrowser() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const serializedSearch = searchParams.toString();
  const queryResult = useMemo(
    () => parseCatalogQuery(new URLSearchParams(serializedSearch)),
    [serializedSearch],
  );
  const query = queryResult.ok ? queryResult.value : defaultQuery;
  const latestQueryRef = useRef(query);
  const pendingHrefRef = useRef<string | null>(null);
  const committedSearch = query.q ?? "";
  const [searchDraftState, setSearchDraftState] = useState<SearchDraftState>({
    committedValue: committedSearch,
    value: committedSearch,
  });
  const searchDraft =
    searchDraftState.committedValue === committedSearch
      ? searchDraftState.value
      : committedSearch;
  const [catalog, setCatalog] = useState<CatalogState>({
    status: "loading",
    requestKey: "",
  });
  const [catalogRetry, setCatalogRetry] = useState(0);
  const [metadataRetry, setMetadataRetry] = useState(0);
  const [metadata, setMetadata] = useState<MetadataState>({
    requestKey: -1,
    loading: true,
    genres: [],
    tags: [],
    platforms: [],
    failedLabels: [],
  });
  const catalogRequestKey = `${serializedSearch}:${catalogRetry}`;
  const visibleCatalog: CatalogState =
    catalog.requestKey === catalogRequestKey
      ? catalog
      : { status: "loading", requestKey: catalogRequestKey };
  const visibleMetadata: MetadataState =
    metadata.requestKey === metadataRetry
      ? metadata
      : { ...metadata, loading: true, failedLabels: [] };

  useEffect(() => {
    const currentHref = catalogHref(query);
    if (pendingHrefRef.current && pendingHrefRef.current !== currentHref) return;

    pendingHrefRef.current = null;
    latestQueryRef.current = query;
  }, [query]);

  useEffect(() => {
    const controller = new AbortController();

    async function loadMetadata() {
      const client = getApiClient();
      const [genres, tags, platforms] = await Promise.allSettled([
        client.listGenres(controller.signal),
        client.listTags(controller.signal),
        client.listPlatforms(controller.signal),
      ]);
      if (controller.signal.aborted) return;

      const failedLabels: string[] = [];
      if (genres.status === "rejected") failedLabels.push("genres");
      if (tags.status === "rejected") failedLabels.push("tags");
      if (platforms.status === "rejected") failedLabels.push("platforms");
      setMetadata((current) => ({
        requestKey: metadataRetry,
        loading: false,
        genres: genres.status === "fulfilled" ? genres.value : current.genres,
        tags: tags.status === "fulfilled" ? tags.value : current.tags,
        platforms: platforms.status === "fulfilled" ? platforms.value : current.platforms,
        failedLabels,
      }));
    }

    loadMetadata().catch(() => {
      if (!controller.signal.aborted) {
        setMetadata((current) => ({
          ...current,
          requestKey: metadataRetry,
          loading: false,
          failedLabels: ["genres", "tags", "platforms"],
        }));
      }
    });
    return () => controller.abort();
  }, [metadataRetry]);

  useEffect(() => {
    if (!queryResult.ok) return;
    const controller = new AbortController();

    getApiClient()
      .listGames(queryResult.value, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setCatalog({ status: "ready", requestKey: catalogRequestKey, data });
        }
      })
      .catch((error: unknown) => {
        if (
          !controller.signal.aborted &&
          !(error instanceof ApiClientError && error.kind === "aborted")
        ) {
          setCatalog({
            status: "error",
            requestKey: catalogRequestKey,
            error:
              error instanceof ApiClientError
                ? error
                : new ApiClientError({
                    kind: "unexpected",
                    message: "The catalog request could not be completed.",
                    cause: error,
                  }),
          });
        }
      });

    return () => controller.abort();
  }, [queryResult, catalogRequestKey]);

  function navigate(patch: Partial<CatalogQuery>, options: { keepPage?: boolean } = {}) {
    const current = latestQueryRef.current;
    const next: CatalogQuery = {
      ...current,
      ...patch,
      page: options.keepPage ? (patch.page ?? current.page) : 1,
    };
    const href = catalogHref(next);
    latestQueryRef.current = next;
    pendingHrefRef.current = href;
    router.push(href as Route, { scroll: false });
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = searchDraft.trim();
    setSearchDraftState({
      committedValue: committedSearch,
      value: normalized,
    });
    navigate({ q: normalized || undefined });
  }

  const hasFilters = Boolean(query.q || query.genre || query.tag || query.platform);

  if (!queryResult.ok) {
    return (
      <div className="catalog-content">
        <StateNotice
          eyebrow="Invalid catalog link"
          title="Some URL values need attention."
          description={queryResult.issues.map((issue) => issue.message).join(" ")}
          tone="warning"
          action={
            <Link className="button button--primary" href="/games">
              Reset catalog filters
            </Link>
          }
        />
      </div>
    );
  }

  const genreOptions = selectedFallback(visibleMetadata.genres, query.genre);
  const tagOptions = selectedFallback(visibleMetadata.tags, query.tag);
  const platformOptions = selectedFallback(visibleMetadata.platforms, query.platform);

  return (
    <>
      <section className="catalog-controls" aria-labelledby="catalog-tools-heading">
        <h2 className="sr-only" id="catalog-tools-heading">
          Search and filter games
        </h2>
        <form className="catalog-search" onSubmit={submitSearch} role="search">
          <label htmlFor="catalog-search-input">Search game titles</label>
          <div className="catalog-search__row">
            <input
              id="catalog-search-input"
              name="q"
              type="search"
              value={searchDraft}
              onChange={(event) =>
                setSearchDraftState({
                  committedValue: committedSearch,
                  value: event.target.value,
                })
              }
              maxLength={MAX_SEARCH_LENGTH}
              placeholder="Try “space” or “tactics”"
            />
            <button className="button button--primary" type="submit">
              Search
            </button>
          </div>
          <p>Title search only · up to {MAX_SEARCH_LENGTH} characters</p>
        </form>

        <div className="filter-grid">
          <label>
            Genre
            <select
              value={query.genre ?? ""}
              disabled={visibleMetadata.loading && genreOptions.length === 0}
              onChange={(event) => navigate({ genre: event.target.value || undefined })}
            >
              <option value="">All genres</option>
              {genreOptions.map((item) => (
                <option key={item.slug} value={item.slug}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Tag
            <select
              value={query.tag ?? ""}
              disabled={visibleMetadata.loading && tagOptions.length === 0}
              onChange={(event) => navigate({ tag: event.target.value || undefined })}
            >
              <option value="">All tags</option>
              {tagOptions.map((item) => (
                <option key={item.slug} value={item.slug}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Platform
            <select
              value={query.platform ?? ""}
              disabled={visibleMetadata.loading && platformOptions.length === 0}
              onChange={(event) =>
                navigate({ platform: event.target.value || undefined })
              }
            >
              <option value="">All platforms</option>
              {platformOptions.map((item) => (
                <option key={item.slug} value={item.slug}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Sort by
            <select
              value={query.sort}
              onChange={(event) => navigate({ sort: event.target.value as CatalogSort })}
            >
              {sortOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="filter-summary">
          <span>
            Filters use <strong>all selected values</strong>
          </span>
          {hasFilters || query.sort !== DEFAULT_CATALOG_SORT || query.page > 1 ? (
            <Link href="/games">Clear all</Link>
          ) : (
            <span>Showing the complete catalog</span>
          )}
        </div>
      </section>

      <div className="catalog-content">
        {visibleMetadata.failedLabels.length > 0 ? (
          <div className="inline-notice" role="status">
            <div>
              <strong>Some filter options are unavailable.</strong>
              <p>
                Could not load {visibleMetadata.failedLabels.join(", ")}. Catalog results
                remain available.
              </p>
            </div>
            <button
              className="text-button"
              type="button"
              onClick={() => setMetadataRetry((value) => value + 1)}
            >
              Retry options
            </button>
          </div>
        ) : null}

        {visibleCatalog.status === "loading" ? <CatalogSkeleton /> : null}

        {visibleCatalog.status === "error" ? (
          <StateNotice
            eyebrow="Catalog connection"
            title={
              visibleCatalog.error.kind === "unavailable"
                ? "The catalog is taking a short break."
                : "We could not reach the catalog."
            }
            description={visibleCatalog.error.message}
            tone="warning"
            live
            action={
              <div className="button-row">
                <button
                  className="button button--primary"
                  type="button"
                  onClick={() => setCatalogRetry((value) => value + 1)}
                >
                  Try again
                </button>
                <Link className="button button--secondary" href="/">
                  Return home
                </Link>
              </div>
            }
          />
        ) : null}

        {visibleCatalog.status === "ready" ? (
          <CatalogResults
            data={visibleCatalog.data}
            query={query}
            hasFilters={hasFilters}
            pathname={pathname}
          />
        ) : null}
      </div>
    </>
  );
}

function CatalogResults({
  data,
  query,
  hasFilters,
  pathname,
}: {
  data: GamePage;
  query: CatalogQuery;
  hasFilters: boolean;
  pathname: string;
}) {
  if (data.items.length === 0 && query.page > 1) {
    const availablePage = Math.max(data.total_pages, 1);
    return (
      <StateNotice
        eyebrow="Page outside results"
        title="There are no games this far into the catalog."
        description={
          data.total_pages > 0
            ? `The last available page is ${data.total_pages}.`
            : "These filters currently return no games."
        }
        action={
          <Link
            className="button button--primary"
            href={catalogHref({ ...query, page: availablePage })}
          >
            Go to page {availablePage}
          </Link>
        }
      />
    );
  }

  if (data.items.length === 0) {
    return (
      <StateNotice
        eyebrow={hasFilters ? "No matches" : "Empty catalog"}
        title={
          hasFilters
            ? "No games match this combination."
            : "The catalog has not been populated yet."
        }
        description={
          hasFilters
            ? "Try removing one filter or using a shorter title search."
            : "Run the documented seed command, then retry this page."
        }
        action={
          hasFilters ? (
            <Link className="button button--primary" href="/games">
              Clear all filters
            </Link>
          ) : null
        }
      />
    );
  }

  return (
    <>
      <div className="results-heading">
        <div aria-live="polite" aria-atomic="true">
          <p className="eyebrow">Catalog results</p>
          <h2>
            {data.total} game{data.total === 1 ? "" : "s"} found
          </h2>
        </div>
        <p>
          Page {data.page} of {data.total_pages}
        </p>
      </div>
      <div className="game-grid">
        {data.items.map((game) => (
          <GameCard game={game} key={game.id} />
        ))}
      </div>
      <CatalogPagination data={data} query={query} pathname={pathname} />
    </>
  );
}

function CatalogPagination({
  data,
  query,
  pathname,
}: {
  data: GamePage;
  query: CatalogQuery;
  pathname: string;
}) {
  const previous = catalogHref({ ...query, page: Math.max(1, data.page - 1) });
  const next = catalogHref({
    ...query,
    page: Math.min(data.total_pages, data.page + 1),
  });

  return (
    <nav className="pagination" aria-label="Catalog pages">
      {data.page > 1 ? (
        <Link href={previous} scroll={false}>
          <span aria-hidden="true">←</span> Previous
        </Link>
      ) : (
        <span aria-disabled="true">
          <span aria-hidden="true">←</span> Previous
        </span>
      )}
      <span aria-current="page">
        {pathname === "/games" ? "Page" : "Catalog page"} {data.page} / {data.total_pages}
      </span>
      {data.page < data.total_pages ? (
        <Link href={next} scroll={false}>
          Next <span aria-hidden="true">→</span>
        </Link>
      ) : (
        <span aria-disabled="true">
          Next <span aria-hidden="true">→</span>
        </span>
      )}
    </nav>
  );
}
