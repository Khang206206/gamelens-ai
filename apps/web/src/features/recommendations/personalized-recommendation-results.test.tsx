import { createRef } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  PersonalizedRecommendationResults,
  type PersonalizedResultsState,
} from "@/features/recommendations/personalized-recommendation-results";
import type { PersonalizedRecommendationResponse } from "@/lib/api/client";

type PersonalizedItem = PersonalizedRecommendationResponse["items"][number];

function recommendationItem(overrides: Partial<PersonalizedItem> = {}): PersonalizedItem {
  return {
    rank: 1,
    game: {
      id: 7,
      title: "Lower Score First",
      slug: "lower-score-first",
      release_date: null,
      developer: "Fixture Studio",
      publisher: null,
      average_rating: 8.5,
      rating_count: 12,
      popularity_score: 0.599117,
      genres: [],
      tags: [],
      platforms: [],
      cover_image_url: null,
    },
    base_ranking_score: 0.159912,
    base_components: [
      { name: "content", raw_score: 0, weight: 0.8, contribution: 0 },
      { name: "platform", raw_score: 1, weight: 0.1, contribution: 0.1 },
      {
        name: "popularity",
        raw_score: 0.599117,
        weight: 0.1,
        contribution: 0.059912,
      },
    ],
    base_weight: 0.8,
    base_contribution: 0.12793,
    feedback_affinity_score: 0,
    feedback_affinity_weight: 0.1,
    feedback_affinity_contribution: 0,
    pre_played_score: 0.170787,
    played_factor: 1,
    played_delta: 0,
    ranking_score: 0.170787,
    adjustment_reasons: ["feedback_affinity", "collaborative_similarity"],
    evidence: {
      matching_genres: [],
      matching_tags: [],
      preferred_platforms: [],
      similar_selected_games: [],
      popularity_score: 0.599117,
    },
    explanation: {
      summary: "Aggregate interaction evidence contributed to this ranking.",
      reasons: ["The result has bounded aggregate source support."],
    },
    candidate_origin: "collaborative",
    collaborative_supported: true,
    collaborative_score: 0.428571,
    collaborative_weight: 0.1,
    collaborative_contribution: 0.042857,
    collaborative_item_support: 12,
    collaborative_source_edges: [
      {
        source_game_slug: "emberfall-tactics",
        source_kind: "liked",
        similarity_score: 0.428571,
        pair_support: 3,
      },
    ],
    ...overrides,
  };
}

function hybridResponse(): PersonalizedRecommendationResponse {
  return {
    generation_id: "1".repeat(32),
    model_name: "content-recommender",
    model_version: "1.0.0",
    data_fingerprint: "a".repeat(64),
    policy: { name: "gamelens-feedback-adjustment", version: "1.0.0" },
    response_reason: "recommendations",
    requested_top_k: 10,
    positive_feedback_sources: [{ game_slug: "emberfall-tactics", kind: "liked" }],
    items: [
      recommendationItem(),
      recommendationItem({
        rank: 2,
        game: {
          id: 8,
          title: "Higher Score Second",
          slug: "higher-score-second",
          release_date: null,
          developer: null,
          publisher: null,
          average_rating: null,
          rating_count: 0,
          popularity_score: 0.9,
          genres: [],
          tags: [],
          platforms: [],
          cover_image_url: null,
        },
        ranking_score: 0.9,
        candidate_origin: "content",
        collaborative_supported: false,
        collaborative_score: 0,
        collaborative_contribution: 0,
        collaborative_item_support: null,
        collaborative_source_edges: [],
        adjustment_reasons: ["feedback_affinity"],
        explanation: { summary: "Content evidence determined this rank.", reasons: [] },
      }),
    ],
    ranking_mode: "hybrid",
    fallback_reason: null,
    hybrid_policy: { name: "gamelens-hybrid-ranking", version: "1.0.0" },
    collaborative_model: {
      name: "item-item-cosine",
      version: "1.0.0",
      interaction_fingerprint: "b".repeat(64),
      scoring_policy: {
        name: "gamelens-collaborative-scoring",
        version: "1.0.0",
      },
    },
  };
}

function fallbackResponse(): PersonalizedRecommendationResponse {
  const response = hybridResponse();
  return {
    ...response,
    ranking_mode: "stage_4_fallback",
    fallback_reason: "artifact_stale",
    hybrid_policy: null,
    collaborative_model: null,
    items: [
      recommendationItem({
        candidate_origin: "content",
        collaborative_supported: false,
        collaborative_score: 0,
        collaborative_weight: 0,
        collaborative_contribution: 0,
        collaborative_item_support: null,
        collaborative_source_edges: [],
        adjustment_reasons: ["feedback_affinity"],
        explanation: {
          summary: "The established saved ranking path remained available.",
          reasons: [],
        },
      }),
    ],
  };
}

function renderResults(state: PersonalizedResultsState) {
  const onRetry = vi.fn();
  const view = render(
    <PersonalizedRecommendationResults
      state={state}
      headingRef={createRef<HTMLHeadingElement>()}
      feedbackByGame={new Map()}
      feedbackPending={null}
      feedbackMessage={{}}
      mutationPending={false}
      onRetry={onRetry}
      onSaveFeedback={vi.fn()}
      onClearFeedback={vi.fn()}
    />,
  );
  return { ...view, onRetry };
}

describe("PersonalizedRecommendationResults", () => {
  it("renders server order and only the aggregate contribution that was applied", async () => {
    const user = userEvent.setup();
    const { container } = renderResults({ status: "ready", result: hybridResponse() });

    expect(screen.getByRole("heading", { name: "Hybrid ranking applied" })).toBeVisible();
    expect(screen.getByText(/not a quality claim or social proof/i)).toBeVisible();
    expect(screen.getAllByRole("link").map((link) => link.textContent)).toEqual([
      "Lower Score First",
      "Higher Score Second",
    ]);
    expect(screen.getByText("Final score 0.170787")).toBeVisible();
    expect(screen.getByText("Final score 0.900000")).toBeVisible();

    const evidence = screen.getByRole("region", {
      name: "Aggregate interaction evidence",
    });
    expect(within(evidence).getByText("12")).toBeVisible();
    expect(within(evidence).getByText(/pair support 3/i)).toBeVisible();
    expect(screen.getAllByText("Aggregate interaction evidence")).toHaveLength(1);

    await user.click(screen.getAllByText("Inspect personalization components")[0]);
    expect(screen.getByText("Aggregate interaction")).toBeVisible();
    expect(screen.getByText(/0.428571 × 0.100000 = 0.042857/)).toBeVisible();
    expect(container).not.toHaveTextContent(/users like you|popular with players/i);
    expect(container).not.toHaveTextContent("item-item-cosine");
    expect(container).not.toHaveTextContent("b".repeat(64));
  });

  it("presents typed fallback as usable and omits aggregate evidence", async () => {
    const user = userEvent.setup();
    renderResults({ status: "ready", result: fallbackResponse() });

    expect(screen.getByRole("heading", { name: "Saved ranking fallback" })).toBeVisible();
    expect(screen.getByText(/did not match the current saved-data state/i)).toBeVisible();
    expect(
      screen.getByText(/kept the established content and saved-feedback/i),
    ).toBeVisible();
    expect(screen.queryByText("Aggregate interaction evidence")).toBeNull();
    expect(screen.queryByText("artifact_stale")).toBeNull();

    await user.click(screen.getByText("Inspect personalization components"));
    expect(screen.queryByText("Aggregate interaction")).toBeNull();
    expect(screen.getByText("Feedback")).toBeVisible();
  });

  it("announces a valid empty saved result without discarding saved context", () => {
    const result: PersonalizedRecommendationResponse = {
      ...fallbackResponse(),
      response_reason: "no_eligible_candidates",
      items: [],
    };
    renderResults({ status: "ready", result });

    expect(
      screen.getByRole("heading", { name: "No eligible personalized candidates" }),
    ).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent(
      "No candidate remained after the saved sources, dislikes, and other exclusions",
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Your saved context remains available",
    );
  });

  it("exposes live loading and keyboard-retry error states", async () => {
    const user = userEvent.setup();
    const loading = renderResults({ status: "loading" });
    expect(screen.getByRole("status")).toHaveTextContent(
      "Generating saved recommendations",
    );
    loading.unmount();

    const error = renderResults({
      status: "error",
      message: "The saved ranking service is temporarily unavailable.",
    });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "The saved ranking service is temporarily unavailable.",
    );
    const retry = screen.getByRole("button", {
      name: "Try saved recommendations again",
    });
    retry.focus();
    await user.keyboard("{Enter}");
    expect(error.onRetry).toHaveBeenCalledOnce();
  });
});
