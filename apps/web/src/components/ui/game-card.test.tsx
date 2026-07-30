import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GameCard } from "@/components/ui/game-card";
import type { GameSummary } from "@/lib/api/client";

const fixture: GameSummary = {
  id: 7,
  title: "Paper Kingdoms",
  slug: "paper-kingdoms",
  release_date: null,
  developer: null,
  publisher: null,
  average_rating: null,
  rating_count: 0,
  popularity_score: 70,
  genres: [],
  tags: [],
  platforms: [],
  cover_image_url: null,
};

describe("GameCard", () => {
  it("links to details and renders deliberate null fallbacks", () => {
    render(<GameCard game={fixture} />);

    expect(screen.getByRole("heading", { name: "Paper Kingdoms" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Paper Kingdoms" })).toHaveAttribute(
      "href",
      "/games/7",
    );
    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(
      screen.getByRole("img", { name: "Placeholder cover for Paper Kingdoms" }),
    ).toBeVisible();
    expect(screen.getByText("Genre not listed")).toBeVisible();
    expect(screen.getByText("Release date not listed")).toBeVisible();
    expect(screen.getByText("Studio not listed")).toBeVisible();
    expect(screen.getByLabelText("Not rated")).toBeVisible();
  });
});
