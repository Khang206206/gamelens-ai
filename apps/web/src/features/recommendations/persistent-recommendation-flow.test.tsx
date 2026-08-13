import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PersistentRecommendationFlow } from "@/features/recommendations/persistent-recommendation-flow";
import { ApiClientError } from "@/lib/api/errors";

const mockClient = vi.hoisted(() => ({
  createAnonymousSession: vi.fn(),
  getCurrentSession: vi.fn(),
  deleteCurrentSession: vi.fn(),
  getPreferences: vi.fn(),
  replacePreferences: vi.fn(),
  clearPreferences: vi.fn(),
  listFeedback: vi.fn(),
  replaceGameFeedback: vi.fn(),
  clearGameFeedback: vi.fn(),
  recommendPersonalized: vi.fn(),
}));

vi.mock("@/lib/api/client", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api/client")>();
  return { ...original, getApiClient: () => mockClient };
});

vi.mock("@/lib/config", () => ({
  getPublicConfig: () => ({
    apiBaseUrl: "http://api.test",
    consentVersion: "stage-4-v1",
  }),
}));

const session = {
  status: "active" as const,
  consent_version: "stage-4-v1",
  current_consent_version: "stage-4-v1",
  consented_at: "2026-08-12T00:00:00Z",
  expires_at: "2027-02-08T00:00:00Z",
  csrf_token: "a".repeat(64),
};

const emptyPreferences = {
  selected_games: [],
  preferred_genres: [],
  preferred_tags: [],
  preferred_platforms: [],
  stale_references: [],
};

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

function feedbackResource(gameId: number) {
  return {
    game_id: gameId,
    game_slug: `game-${gameId}`,
    game_title: `Game ${gameId}`,
    reaction: null,
    played: true,
    wishlisted: false,
    rating: null,
    latest_occurred_at: `2026-08-12T00:${String(gameId % 60).padStart(2, "0")}:00Z`,
  };
}

const personalized = {
  generation_id: "generation-1",
  model_name: "gamelens-content-tfidf",
  model_version: "1.0.0",
  data_fingerprint: "a".repeat(64),
  policy: { name: "gamelens-feedback-adjustment", version: "1.0.0" },
  response_reason: "recommendations" as const,
  requested_top_k: 10,
  positive_feedback_sources: [],
  items: [
    {
      rank: 1,
      game,
      base_ranking_score: 0.8,
      base_components: [],
      base_weight: 0.9,
      base_contribution: 0.72,
      feedback_affinity_score: 0.5,
      feedback_affinity_weight: 0.1,
      feedback_affinity_contribution: 0.05,
      pre_played_score: 0.77,
      played_factor: 1,
      played_delta: 0,
      ranking_score: 0.77,
      adjustment_reasons: ["feedback_affinity" as const],
      evidence: {
        matching_genres: [],
        matching_tags: [],
        preferred_platforms: [],
        similar_selected_games: [],
        popularity_score: 0.8,
      },
      explanation: { summary: "It fits your saved context.", reasons: [] },
    },
  ],
};

describe("PersistentRecommendationFlow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockClient.getPreferences.mockResolvedValue(emptyPreferences);
    mockClient.listFeedback.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 100,
      total: 0,
    });
    mockClient.createAnonymousSession.mockResolvedValue(session);
    mockClient.deleteCurrentSession.mockResolvedValue(undefined);
    mockClient.replacePreferences.mockResolvedValue(emptyPreferences);
    mockClient.clearPreferences.mockResolvedValue(undefined);
    mockClient.replaceGameFeedback.mockResolvedValue(null);
    mockClient.clearGameFeedback.mockResolvedValue(undefined);
    mockClient.recommendPersonalized.mockResolvedValue(personalized);
  });

  it("keeps the stateless flow usable and creates no identity before affirmation", async () => {
    const user = userEvent.setup();
    mockClient.getCurrentSession.mockRejectedValue(
      new ApiClientError({ kind: "unauthorized", message: "No session", status: 401 }),
    );

    render(
      <PersistentRecommendationFlow>
        <button type="button">Use request-only recommendations</button>
      </PersistentRecommendationFlow>,
    );

    expect(
      screen.getByRole("button", { name: "Use request-only recommendations" }),
    ).toBeEnabled();
    const enable = await screen.findByRole("button", {
      name: "Enable saved personalization",
    });
    expect(screen.getByText(/consent notice is version/i)).toHaveTextContent(
      "stage-4-v1",
    );
    expect(mockClient.createAnonymousSession).not.toHaveBeenCalled();

    enable.focus();
    await user.keyboard("{Enter}");

    await screen.findByText(/Saved personalization is active/);
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Review and save your durable choices" }),
      ).toHaveFocus(),
    );
    expect(mockClient.createAnonymousSession).toHaveBeenCalledWith(
      { consent: true, consent_version: "stage-4-v1" },
      undefined,
    );
    expect(mockClient.getPreferences).toHaveBeenCalled();
    expect(mockClient.listFeedback).toHaveBeenCalledWith(1, 100, undefined);
  });

  it("offers lifecycle retry when hydration fails after consent was acknowledged", async () => {
    const user = userEvent.setup();
    mockClient.getCurrentSession
      .mockRejectedValueOnce(
        new ApiClientError({ kind: "unauthorized", message: "No session", status: 401 }),
      )
      .mockResolvedValueOnce(session);
    mockClient.getPreferences
      .mockRejectedValueOnce(
        new ApiClientError({ kind: "network", message: "Preferences unavailable" }),
      )
      .mockResolvedValueOnce(emptyPreferences);

    render(
      <PersistentRecommendationFlow>
        <p>Request-only flow</p>
      </PersistentRecommendationFlow>,
    );

    await user.click(
      await screen.findByRole("button", { name: "Enable saved personalization" }),
    );
    expect(await screen.findByRole("button", { name: "Try again" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Clear saved data" })).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Enable saved personalization" }),
    ).toBeNull();
    expect(mockClient.createAnonymousSession).toHaveBeenCalledOnce();

    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Keep your choices on this browser" }),
      ).toHaveFocus(),
    );
    const retry = screen.getByRole("button", { name: "Try again" });
    retry.focus();
    await user.keyboard("{Enter}");
    await screen.findByText(/Saved personalization is active/);
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Review and save your durable choices" }),
      ).toHaveFocus(),
    );
    expect(mockClient.createAnonymousSession).toHaveBeenCalledOnce();
  });

  it("can clear a created session when its first hydration fails", async () => {
    const user = userEvent.setup();
    mockClient.getCurrentSession.mockRejectedValue(
      new ApiClientError({ kind: "unauthorized", message: "No session", status: 401 }),
    );
    mockClient.getPreferences.mockRejectedValue(
      new ApiClientError({ kind: "network", message: "Preferences unavailable" }),
    );
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <PersistentRecommendationFlow>
        <p>Request-only flow</p>
      </PersistentRecommendationFlow>,
    );

    await user.click(
      await screen.findByRole("button", { name: "Enable saved personalization" }),
    );
    await user.click(await screen.findByRole("button", { name: "Clear saved data" }));

    await waitFor(() =>
      expect(mockClient.deleteCurrentSession).toHaveBeenCalledWith(session.csrf_token),
    );
    expect(
      await screen.findByRole("button", { name: "Enable saved personalization" }),
    ).toBeVisible();
    expect(screen.getByText(/All saved data was cleared/)).toBeVisible();
  });

  it("requires a reload without creating identity when fresh consent copy is stale", async () => {
    const user = userEvent.setup();
    mockClient.getCurrentSession.mockRejectedValue(
      new ApiClientError({ kind: "unauthorized", message: "No session", status: 401 }),
    );
    mockClient.createAnonymousSession.mockRejectedValue(
      new ApiClientError({
        kind: "conflict",
        status: 409,
        code: "consent_version_outdated",
        message: "Consent changed",
        details: { current_consent_version: "stage-4-v2" },
      }),
    );

    render(
      <PersistentRecommendationFlow>
        <p>Request-only flow</p>
      </PersistentRecommendationFlow>,
    );

    await user.click(
      await screen.findByRole("button", { name: "Enable saved personalization" }),
    );

    expect(await screen.findByRole("link", { name: "Reload this page" })).toHaveAttribute(
      "href",
      "/recommendations",
    );
    expect(screen.getByText(/No saved session was created/)).toBeVisible();
    expect(screen.getByText(/consent version stage-4-v2/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Clear saved data" })).toBeNull();
    expect(mockClient.createAnonymousSession).toHaveBeenCalledOnce();
    expect(mockClient.getPreferences).not.toHaveBeenCalled();
  });

  it("rehydrates every feedback page instead of hiding state beyond the first 100", async () => {
    mockClient.getCurrentSession.mockResolvedValue(session);
    mockClient.listFeedback
      .mockResolvedValueOnce({
        items: Array.from({ length: 100 }, (_, index) => feedbackResource(index + 1)),
        page: 1,
        page_size: 100,
        total: 101,
      })
      .mockResolvedValueOnce({
        items: [feedbackResource(101)],
        page: 2,
        page_size: 100,
        total: 101,
      });

    render(
      <PersistentRecommendationFlow>
        <p>Request-only flow</p>
      </PersistentRecommendationFlow>,
    );

    expect(
      await screen.findByRole("group", { name: "Feedback for Game 101" }),
    ).toBeVisible();
    expect(mockClient.listFeedback).toHaveBeenNthCalledWith(
      1,
      1,
      100,
      expect.any(AbortSignal),
    );
    expect(mockClient.listFeedback).toHaveBeenNthCalledWith(
      2,
      2,
      100,
      expect.any(AbortSignal),
    );
  });

  it("continues bounded pagination when saved feedback exceeds the former 10,000-item cap", async () => {
    mockClient.getCurrentSession.mockResolvedValue(session);
    mockClient.listFeedback
      .mockResolvedValueOnce({
        items: Array.from({ length: 100 }, (_, index) => feedbackResource(index + 1)),
        page: 1,
        page_size: 100,
        total: 10_001,
      })
      .mockRejectedValueOnce(
        new ApiClientError({
          kind: "network",
          message: "Stopped after proving pagination continued.",
        }),
      );

    render(
      <PersistentRecommendationFlow>
        <p>Request-only flow</p>
      </PersistentRecommendationFlow>,
    );

    expect(await screen.findByRole("button", { name: "Try again" })).toBeVisible();
    expect(mockClient.listFeedback).toHaveBeenNthCalledWith(
      2,
      2,
      100,
      expect.any(AbortSignal),
    );
    expect(screen.getByRole("alert")).not.toHaveTextContent(
      "exceeded the safe rehydration bound",
    );
  });

  it("rehydrates, generates on the server, and saves full feedback", async () => {
    const user = userEvent.setup();
    mockClient.getCurrentSession.mockResolvedValue(session);
    mockClient.getPreferences.mockResolvedValue({
      ...emptyPreferences,
      preferred_genres: ["strategy"],
    });

    render(
      <PersistentRecommendationFlow>
        <p>Request-only flow</p>
      </PersistentRecommendationFlow>,
    );

    const generate = await screen.findByRole("button", {
      name: "Generate saved recommendations",
    });
    await user.click(generate);

    expect(
      await screen.findByRole("heading", { name: "1 personalized recommendations" }),
    ).toHaveFocus();
    expect(mockClient.recommendPersonalized).toHaveBeenCalledWith(
      { top_k: 10 },
      session.csrf_token,
    );
    await user.click(screen.getByText("Inspect personalization components"));
    expect(screen.getByText(/0.800000 × 0.900000 = 0.720000/)).toBeVisible();

    await user.selectOptions(screen.getByLabelText("Reaction"), "liked");
    await user.click(screen.getByRole("button", { name: "Save feedback" }));
    await waitFor(() => expect(mockClient.replaceGameFeedback).toHaveBeenCalledOnce());
    expect(mockClient.replaceGameFeedback).toHaveBeenCalledWith(
      1,
      { reaction: "liked", played: false, wishlisted: false, rating: null },
      session.csrf_token,
    );
    await waitFor(() =>
      expect(mockClient.recommendPersonalized).toHaveBeenCalledTimes(2),
    );
  });

  it("invalidates a rendered shortlist when its persisted context changes", async () => {
    const user = userEvent.setup();
    mockClient.getCurrentSession.mockResolvedValue(session);
    mockClient.getPreferences.mockResolvedValue({
      ...emptyPreferences,
      preferred_genres: ["strategy"],
    });
    mockClient.replacePreferences.mockResolvedValue({
      ...emptyPreferences,
      preferred_genres: ["adventure"],
    });

    render(
      <PersistentRecommendationFlow>
        <p>Request-only flow</p>
      </PersistentRecommendationFlow>,
    );

    await user.click(
      await screen.findByRole("button", { name: "Generate saved recommendations" }),
    );
    expect(
      await screen.findByRole("heading", { name: "1 personalized recommendations" }),
    ).toBeVisible();

    const genreDraft = screen.getByRole("textbox", { name: "Genre slugs" });
    await user.clear(genreDraft);
    await user.type(genreDraft, "adventure");
    await user.click(
      screen.getByRole("button", { name: "Save complete preference set" }),
    );

    await screen.findByText("Saved preferences were updated.");
    expect(
      screen.queryByRole("heading", { name: "1 personalized recommendations" }),
    ).not.toBeInTheDocument();
  });

  it("re-consents an outdated lifecycle with CSRF and clears all data accessibly", async () => {
    const user = userEvent.setup();
    const outdated = {
      ...session,
      status: "consent_outdated" as const,
      consent_version: "stage-3-v1",
    };
    mockClient.getCurrentSession.mockResolvedValue(outdated);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <PersistentRecommendationFlow>
        <p>Request-only flow</p>
      </PersistentRecommendationFlow>,
    );

    const continueButton = await screen.findByRole("button", {
      name: "Continue with saved personalization",
    });
    continueButton.focus();
    await user.keyboard("{Enter}");
    expect(mockClient.createAnonymousSession).toHaveBeenCalledWith(
      { consent: true, consent_version: "stage-4-v1" },
      outdated.csrf_token,
    );
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Review and save your durable choices" }),
      ).toHaveFocus(),
    );

    await user.click(await screen.findByRole("button", { name: "Clear all saved data" }));
    await waitFor(() =>
      expect(mockClient.deleteCurrentSession).toHaveBeenCalledWith(session.csrf_token),
    );
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Keep your choices on this browser" }),
      ).toHaveFocus(),
    );
    expect(screen.getByText(/All saved data was cleared/)).toBeVisible();
  });

  it("requires a reload when the API advertises a newer consent contract", async () => {
    const user = userEvent.setup();
    mockClient.getCurrentSession.mockResolvedValue({
      ...session,
      status: "consent_outdated" as const,
      consent_version: "stage-3-v1",
      current_consent_version: "stage-4-v2",
    });

    render(
      <PersistentRecommendationFlow>
        <p>Request-only flow</p>
      </PersistentRecommendationFlow>,
    );

    await user.click(
      await screen.findByRole("button", {
        name: "Continue with saved personalization",
      }),
    );

    expect(await screen.findByText(/older consent contract/)).toBeVisible();
    expect(mockClient.createAnonymousSession).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Try again" })).toBeVisible();
  });

  it("preserves clear-data access when consent changes during re-consent", async () => {
    const user = userEvent.setup();
    mockClient.getCurrentSession.mockResolvedValue({
      ...session,
      status: "consent_outdated" as const,
      consent_version: "stage-3-v1",
    });
    mockClient.createAnonymousSession.mockRejectedValue(
      new ApiClientError({
        kind: "conflict",
        status: 409,
        code: "consent_version_outdated",
        message: "Consent changed during review",
        details: { current_consent_version: "stage-4-v2" },
      }),
    );

    render(
      <PersistentRecommendationFlow>
        <p>Request-only flow</p>
      </PersistentRecommendationFlow>,
    );

    await user.click(
      await screen.findByRole("button", {
        name: "Continue with saved personalization",
      }),
    );

    expect(await screen.findByText(/version stage-4-v2/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Clear saved data" })).toBeVisible();
    expect(screen.queryByText(/No saved session was created/)).toBeNull();
    expect(mockClient.createAnonymousSession).toHaveBeenCalledWith(
      { consent: true, consent_version: "stage-4-v1" },
      session.csrf_token,
    );
  });

  it("removes protected route state when consent becomes outdated at runtime", async () => {
    const user = userEvent.setup();
    mockClient.getCurrentSession.mockResolvedValue(session);
    mockClient.getPreferences.mockResolvedValue({
      ...emptyPreferences,
      preferred_genres: ["strategy"],
    });
    mockClient.recommendPersonalized
      .mockResolvedValueOnce(personalized)
      .mockRejectedValueOnce(
        new ApiClientError({
          kind: "conflict",
          status: 409,
          code: "consent_version_outdated",
          message: "Consent changed",
          details: { current_consent_version: "stage-4-v2" },
        }),
      );

    render(
      <PersistentRecommendationFlow>
        <p>Request-only flow</p>
      </PersistentRecommendationFlow>,
    );

    const generate = await screen.findByRole("button", {
      name: "Generate saved recommendations",
    });
    await user.click(generate);
    await screen.findByRole("heading", { name: "1 personalized recommendations" });
    await user.click(generate);

    expect(
      await screen.findByRole("button", { name: "Continue with saved personalization" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Review and save your durable choices" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "1 personalized recommendations" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/version stage-4-v2/)).toBeVisible();
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Keep your choices on this browser" }),
      ).toHaveFocus(),
    );
  });

  it("explains an ambiguous generation without retrying or losing its correlation id", async () => {
    const user = userEvent.setup();
    mockClient.getCurrentSession.mockResolvedValue(session);
    mockClient.getPreferences.mockResolvedValue({
      ...emptyPreferences,
      preferred_genres: ["strategy"],
    });
    mockClient.recommendPersonalized.mockRejectedValue(
      new ApiClientError({
        kind: "unavailable",
        status: 503,
        code: "generation_outcome_unknown",
        message: "Commit acknowledgement was lost",
        details: { generation_id: "generation-ambiguous-1" },
      }),
    );

    render(
      <PersistentRecommendationFlow>
        <p>Request-only flow</p>
      </PersistentRecommendationFlow>,
    );

    await user.click(
      await screen.findByRole("button", { name: "Generate saved recommendations" }),
    );

    expect(
      await screen.findByText(/Generation ID: generation-ambiguous-1/),
    ).toBeVisible();
    expect(screen.getByText(/Do not retry blindly/)).toBeVisible();
    expect(mockClient.recommendPersonalized).toHaveBeenCalledOnce();
  });

  it("surfaces stale preference references and keeps the editable recovery state", async () => {
    const user = userEvent.setup();
    mockClient.getCurrentSession.mockResolvedValue(session);
    mockClient.getPreferences.mockResolvedValue({
      ...emptyPreferences,
      preferred_genres: ["retired-genre"],
    });
    mockClient.recommendPersonalized.mockRejectedValue(
      new ApiClientError({
        kind: "conflict",
        status: 409,
        code: "saved_preferences_stale",
        message: "Saved preferences are stale",
        details: { references: ["retired-genre"] },
      }),
    );

    render(
      <PersistentRecommendationFlow>
        <p>Request-only flow</p>
      </PersistentRecommendationFlow>,
    );

    await user.click(
      await screen.findByRole("button", { name: "Generate saved recommendations" }),
    );

    expect(await screen.findByText(/Affected references: retired-genre/)).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent("retired-genre");
    expect(
      screen.getByRole("heading", { name: "Review and save your durable choices" }),
    ).toBeVisible();
  });

  it("locks protected mutations and rolls a failed feedback draft back to saved state", async () => {
    const user = userEvent.setup();
    mockClient.getCurrentSession.mockResolvedValue(session);
    mockClient.getPreferences.mockResolvedValue({
      ...emptyPreferences,
      preferred_genres: ["strategy"],
    });
    let rejectFeedback!: (error: unknown) => void;
    mockClient.replaceGameFeedback.mockReturnValue(
      new Promise((_resolve, reject) => {
        rejectFeedback = reject;
      }),
    );

    render(
      <PersistentRecommendationFlow>
        <p>Request-only flow</p>
      </PersistentRecommendationFlow>,
    );

    await user.click(
      await screen.findByRole("button", { name: "Generate saved recommendations" }),
    );
    await screen.findByRole("heading", { name: "1 personalized recommendations" });
    await user.selectOptions(screen.getByLabelText("Reaction"), "liked");
    await user.click(screen.getByRole("button", { name: "Save feedback" }));

    expect(screen.getByRole("button", { name: "Clear all saved data" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Save complete preference set" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("group", { name: "Feedback for Alpha Tactics" }),
    ).toBeDisabled();

    rejectFeedback(
      new ApiClientError({ kind: "network", message: "Feedback could not be saved." }),
    );
    expect(
      await screen.findByText(/Your last saved feedback is still shown/),
    ).toBeVisible();
    await waitFor(() => expect(screen.getByLabelText("Reaction")).toHaveValue(""));
    expect(mockClient.recommendPersonalized).toHaveBeenCalledOnce();
  });
});
