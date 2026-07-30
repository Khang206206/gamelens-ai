"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { CoverPlaceholder } from "@/components/ui/cover-placeholder";
import { DetailSkeleton } from "@/components/ui/loading";
import { StateNotice } from "@/components/ui/state-notice";
import { type GameDetail, getApiClient, type TaxonomyItem } from "@/lib/api/client";
import { ApiClientError } from "@/lib/api/errors";
import {
  formatRating,
  formatRatingCount,
  formatReleaseDate,
  formatStudio,
} from "@/lib/format";
import { parseGameId } from "@/lib/routes";

type DetailState =
  | { status: "loading"; requestKey: string }
  | { status: "ready"; requestKey: string; game: GameDetail }
  | { status: "not_found"; requestKey: string }
  | { status: "error"; requestKey: string; error: ApiClientError };

export function GameDetailView({ rawGameId }: { rawGameId: string }) {
  const router = useRouter();
  const gameId = parseGameId(rawGameId);
  const [state, setState] = useState<DetailState>({
    status: "loading",
    requestKey: "",
  });
  const [retry, setRetry] = useState(0);
  const requestKey = `${gameId ?? "invalid"}:${retry}`;
  const visibleState: DetailState =
    state.requestKey === requestKey ? state : { status: "loading", requestKey };

  useEffect(() => {
    if (gameId === null) return;
    const controller = new AbortController();
    getApiClient()
      .getGame(gameId, controller.signal)
      .then((game) => {
        if (!controller.signal.aborted) {
          setState({ status: "ready", requestKey, game });
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        if (error instanceof ApiClientError && error.kind === "not_found") {
          setState({ status: "not_found", requestKey });
          return;
        }
        setState({
          status: "error",
          requestKey,
          error:
            error instanceof ApiClientError
              ? error
              : new ApiClientError({
                  kind: "unexpected",
                  message: "The game details could not be loaded.",
                  cause: error,
                }),
        });
      });
    return () => controller.abort();
  }, [gameId, requestKey]);

  if (gameId === null) {
    return (
      <StateNotice
        eyebrow="Invalid game address"
        title="This game identifier is not valid."
        description="Game addresses use a positive whole number. No catalog request was sent."
        headingLevel={1}
        tone="warning"
        action={
          <Link className="button button--primary" href="/games">
            Return to the catalog
          </Link>
        }
      />
    );
  }

  if (visibleState.status === "loading") return <DetailSkeleton />;

  if (visibleState.status === "not_found") {
    return (
      <StateNotice
        eyebrow="Game not found"
        title="This title is not in the archive."
        description="It may have been removed, or the link may point to an ID that has never existed."
        headingLevel={1}
        action={
          <Link className="button button--primary" href="/games">
            Browse available games
          </Link>
        }
      />
    );
  }

  if (visibleState.status === "error") {
    return (
      <StateNotice
        eyebrow="Detail connection"
        title={
          visibleState.error.kind === "unavailable"
            ? "Game details are temporarily unavailable."
            : "We could not load this game."
        }
        description={visibleState.error.message}
        headingLevel={1}
        tone="warning"
        live
        action={
          <div className="button-row">
            <button
              className="button button--primary"
              type="button"
              onClick={() => setRetry((value) => value + 1)}
            >
              Try again
            </button>
            <Link className="button button--secondary" href="/games">
              Open catalog
            </Link>
          </div>
        }
      />
    );
  }

  const { game } = visibleState;
  return (
    <>
      <div className="detail-toolbar">
        <button className="text-button" type="button" onClick={() => router.back()}>
          <span aria-hidden="true">←</span> Back to previous view
        </button>
        <Link href="/games">All games</Link>
      </div>
      <article className="detail-layout">
        <div className="detail-cover-column">
          <CoverPlaceholder gameId={game.id} title={game.title} variant="detail" />
          <p>
            Cover artwork is intentionally unavailable in the project-authored catalog.
          </p>
        </div>
        <div className="detail-copy">
          <p className="eyebrow">
            {game.genres.map((genre) => genre.name).join(" · ") || "Genre not listed"}
          </p>
          <h1>{game.title}</h1>
          <p className="detail-copy__description">{game.description}</p>

          <dl className="detail-facts">
            <div>
              <dt>Released</dt>
              <dd>
                {game.release_date ? (
                  <time dateTime={game.release_date}>
                    {formatReleaseDate(game.release_date)}
                  </time>
                ) : (
                  formatReleaseDate(null)
                )}
              </dd>
            </div>
            <div>
              <dt>Developer</dt>
              <dd>{formatStudio(game.developer)}</dd>
            </div>
            <div>
              <dt>Publisher</dt>
              <dd>{formatStudio(game.publisher)}</dd>
            </div>
            <div>
              <dt>Community signal</dt>
              <dd>
                {formatRating(game.average_rating)}
                <small>{formatRatingCount(game.rating_count)}</small>
              </dd>
            </div>
          </dl>

          <TaxonomySection title="Platforms" items={game.platforms} />
          <TaxonomySection title="Tags" items={game.tags} />
        </div>
      </article>
      <aside className="detail-disclosure">
        <span>Data note</span>
        <p>
          Ratings and popularity values are synthetic development signals. They are not
          recommendation evidence or real market data.
        </p>
      </aside>
    </>
  );
}

function TaxonomySection({ title, items }: { title: string; items: TaxonomyItem[] }) {
  return (
    <section className="taxonomy-section">
      <h2>{title}</h2>
      {items.length > 0 ? (
        <ul>
          {items.map((item) => (
            <li key={item.slug}>{item.name}</li>
          ))}
        </ul>
      ) : (
        <p>Not listed</p>
      )}
    </section>
  );
}
