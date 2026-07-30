import type { Route } from "next";
import Link from "next/link";

import { CoverPlaceholder } from "@/components/ui/cover-placeholder";
import type { GameSummary } from "@/lib/api/client";
import { formatRating, formatRatingCount, formatReleaseDate } from "@/lib/format";

interface GameCardProps {
  game: GameSummary;
}

export function GameCard({ game }: GameCardProps) {
  const href = `/games/${game.id}` as Route;
  return (
    <article className="game-card">
      <div className="game-card__cover">
        <CoverPlaceholder gameId={game.id} title={game.title} />
      </div>
      <div className="game-card__body">
        <div className="game-card__meta">
          <span>{game.genres[0]?.name ?? "Genre not listed"}</span>
          <span aria-hidden="true">·</span>
          <span>{formatReleaseDate(game.release_date)}</span>
        </div>
        <h2>
          <Link href={href}>{game.title}</Link>
        </h2>
        <p className="game-card__studio">
          {game.developer?.trim() || "Studio not listed"}
        </p>
        <div className="game-card__footer">
          <span className="rating-pill" aria-label={formatRating(game.average_rating)}>
            {game.average_rating === null ? "—" : game.average_rating.toFixed(1)}
          </span>
          <span>{formatRatingCount(game.rating_count)}</span>
          <span className="game-card__arrow" aria-hidden="true">
            ↗
          </span>
        </div>
      </div>
    </article>
  );
}
