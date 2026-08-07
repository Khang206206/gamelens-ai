import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RecommendationFlow } from "@/features/recommendations/recommendation-flow";
import { ApiClientError } from "@/lib/api/errors";

const mockClient = vi.hoisted(() => ({
  listGames: vi.fn(),
  listGenres: vi.fn(),
  listTags: vi.fn(),
  listPlatforms: vi.fn(),
  recommend: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, getApiClient: () => mockClient };
});

const game = {
  id: 1,
  title: "Alpha Tactics",
  slug: "alpha-tactics",
  release_date: "2026-01-01",
  developer: "Fixture Studio",
  publisher: "Fixture Works",
  average_rating: 8,
  rating_count: 100,
  popularity_score: 50,
  genres: [{ id: 1, name: "Strategy", slug: "strategy" }],
  tags: [{ id: 1, name: "Tactical", slug: "tactical" }],
  platforms: [{ id: 1, name: "PC", slug: "pc" }],
  cover_image_url: null,
};

describe("RecommendationFlow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockClient.listGames.mockResolvedValue({
      items: [game],
      page: 1,
      page_size: 100,
      total: 1,
      total_pages: 1,
    });
    mockClient.listGenres.mockResolvedValue([
      { id: 1, name: "Strategy", slug: "strategy" },
    ]);
    mockClient.listTags.mockResolvedValue([
      { id: 1, name: "Tactical", slug: "tactical" },
    ]);
    mockClient.listPlatforms.mockResolvedValue([{ id: 1, name: "PC", slug: "pc" }]);
    mockClient.recommend.mockResolvedValue({
      model: {
        name: "gamelens-content-tfidf",
        version: "1.0.0",
        data_fingerprint: "abc",
      },
      response_reason: "recommendations",
      requested_top_k: 10,
      items: [
        {
          rank: 1,
          ranking_score: 0.72,
          game,
          components: [
            {
              name: "content",
              raw_score: 0.8,
              weight: 0.8,
              contribution: 0.64,
            },
            {
              name: "platform",
              raw_score: 0,
              weight: 0.1,
              contribution: 0,
            },
            {
              name: "popularity",
              raw_score: 0.8,
              weight: 0.1,
              contribution: 0.08,
            },
          ],
          evidence: {
            matching_genres: [{ name: "Strategy", slug: "strategy" }],
            matching_tags: [],
            preferred_platforms: [],
            similar_selected_games: [],
            popularity_score: 0.8,
          },
          explanation: {
            summary: "It matches your preferred genres: Strategy.",
            reasons: ["It matches your preferred genres: Strategy."],
          },
        },
      ],
    });
  });

  it("requires a primary content signal", async () => {
    render(<RecommendationFlow />);
    const review = await screen.findByRole("button", { name: "Review selections" });
    expect(review).toBeDisabled();
    expect(screen.getByText(/Platform alone cannot form a content query/)).toBeVisible();
  });

  it("keeps successful option groups usable and retries a partial failure", async () => {
    const user = userEvent.setup();
    let completeRetry!: () => void;
    const retry = new Promise<Array<{ id: number; name: string; slug: string }>>(
      (resolve) => {
        completeRetry = () => resolve([{ id: 1, name: "Tactical", slug: "tactical" }]);
      },
    );
    mockClient.listTags
      .mockRejectedValueOnce(
        new ApiClientError({
          kind: "unavailable",
          message: "Tags are temporarily unavailable.",
        }),
      )
      .mockReturnValueOnce(retry);

    render(<RecommendationFlow />);

    expect(await screen.findByRole("checkbox", { name: "Strategy" })).toBeVisible();
    expect(
      screen.getByText("Some selection options are temporarily unavailable."),
    ).toBeVisible();
    await user.click(screen.getByRole("checkbox", { name: "Strategy" }));
    expect(screen.getByRole("button", { name: "Review selections" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Retry options" }));
    expect(screen.getByRole("button", { name: "Retrying…" })).toBeDisabled();
    completeRetry();
    await waitFor(() => expect(mockClient.listTags).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(
        screen.queryByText("Some selection options are temporarily unavailable."),
      ).not.toBeInTheDocument(),
    );
  });

  it("keeps selected games visible ahead of the display cap", async () => {
    const user = userEvent.setup();
    const games = Array.from({ length: 17 }, (_, index) => ({
      ...game,
      id: index + 1,
      title: index === 16 ? "Wild Current" : `Catalog Game ${index + 1}`,
      slug: index === 16 ? "wild-current" : `catalog-game-${index + 1}`,
    }));
    mockClient.listGames.mockResolvedValue({
      items: games,
      page: 1,
      page_size: 100,
      total: games.length,
      total_pages: 1,
    });

    render(<RecommendationFlow />);

    const search = await screen.findByRole("searchbox", {
      name: "Search the loaded catalog",
    });
    await user.type(search, "Wild Current");
    const selectedGame = screen.getByRole("checkbox", { name: /Wild Current/ });
    await user.click(selectedGame);
    await user.clear(search);

    expect(screen.getByRole("checkbox", { name: /Wild Current/ })).toBeChecked();
  });

  it("reviews, submits, and renders API order without recalculating", async () => {
    const user = userEvent.setup();
    render(<RecommendationFlow />);
    await user.click(await screen.findByRole("checkbox", { name: "Strategy" }));
    await user.click(screen.getByRole("button", { name: "Review selections" }));
    const reviewHeading = screen.getByRole("heading", {
      name: "Ready for the content model",
    });
    expect(reviewHeading).toBeVisible();
    expect(reviewHeading).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "Get recommendations" }));
    await waitFor(() => expect(mockClient.recommend).toHaveBeenCalledOnce());
    expect(mockClient.recommend).toHaveBeenCalledWith(
      expect.objectContaining({ preferred_genres: ["strategy"] }),
      expect.any(AbortSignal),
    );
    expect(
      await screen.findByRole("heading", { name: "1 ranked recommendations" }),
    ).toHaveFocus();
    expect(await screen.findByText("01")).toBeVisible();
    expect(screen.getByText("Ranking score 0.720000")).toBeVisible();
    expect(screen.getByText("It matches your preferred genres: Strategy.")).toBeVisible();
    expect(
      screen.getAllByText("It matches your preferred genres: Strategy."),
    ).toHaveLength(1);
  });
});
