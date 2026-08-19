"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ConsentPanel,
  type ConsentPanelState,
} from "@/features/recommendations/consent-panel";
import { FeedbackControls } from "@/features/recommendations/feedback-controls";
import {
  type ApiClient,
  type AnonymousSessionResponse,
  type FeedbackReplaceRequest,
  type FeedbackResource,
  getApiClient,
  type PersonalizedRecommendationResponse,
  type PreferenceReplaceRequest,
  type PreferenceResponse,
} from "@/lib/api/client";
import { ApiClientError } from "@/lib/api/errors";
import { getPublicConfig } from "@/lib/config";

interface PersistentRecommendationFlowProps {
  children: React.ReactNode;
}

interface DurableState {
  session: AnonymousSessionResponse;
  preferences: PreferenceResponse;
  feedback: FeedbackResource[];
}

const EMPTY_PREFERENCE_DRAFT: PreferenceReplaceRequest = {
  selected_game_ids: [],
  preferred_genres: [],
  preferred_tags: [],
  preferred_platforms: [],
};

const FEEDBACK_PAGE_SIZE = 100;
const MAX_REHYDRATED_FEEDBACK_ITEMS = 100_000;

function errorDetails(error: unknown): Record<string, unknown> | null {
  if (
    !(error instanceof ApiClientError) ||
    !error.details ||
    typeof error.details !== "object"
  ) {
    return null;
  }
  return error.details as Record<string, unknown>;
}

function errorDetailString(error: unknown, key: string): string | null {
  const value = errorDetails(error)?.[key];
  return typeof value === "string" && value.length > 0 && value.length <= 128
    ? value
    : null;
}

function errorDetailStrings(error: unknown, key: string): string[] {
  const value = errorDetails(error)?.[key];
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is string => typeof item === "string")
    .filter((item) => item.length > 0 && item.length <= 100)
    .slice(0, 100);
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiClientError && error.code === "generation_outcome_unknown") {
    const generationId = errorDetailString(error, "generation_id");
    const correlation = generationId ? ` Generation ID: ${generationId}.` : "";
    return `The recommendation outcome could not be confirmed and may already have been committed.${correlation} Do not retry blindly; reload the saved state before deciding whether to try again.`;
  }
  if (error instanceof ApiClientError && error.code === "saved_preferences_stale") {
    const references = errorDetailStrings(error, "references");
    const affected = references.length
      ? ` Affected references: ${references.join(", ")}.`
      : "";
    return `Some saved preferences no longer exist in the current catalog.${affected} Review or clear them, then save the complete preference set again.`;
  }
  return error instanceof ApiClientError
    ? error.message
    : "The saved personalization request could not be completed.";
}

async function loadAllFeedback(
  client: Pick<ApiClient, "listFeedback">,
  signal: AbortSignal | undefined,
  isCurrent: () => boolean,
): Promise<FeedbackResource[] | null> {
  const firstPage = await client.listFeedback(1, FEEDBACK_PAGE_SIZE, signal);
  if (signal?.aborted || !isCurrent()) return null;
  if (
    !Number.isSafeInteger(firstPage.total) ||
    firstPage.total < 0 ||
    firstPage.total > MAX_REHYDRATED_FEEDBACK_ITEMS
  ) {
    throw new ApiClientError({
      kind: "invalid_response",
      message: "The saved feedback response exceeded the safe rehydration bound.",
    });
  }

  const expectedPages = Math.max(1, Math.ceil(firstPage.total / FEEDBACK_PAGE_SIZE));
  const feedbackByGame = new Map<number, FeedbackResource>();
  const appendPage = (
    page: Awaited<ReturnType<ApiClient["listFeedback"]>>,
    pageNumber: number,
  ) => {
    if (
      page.page !== pageNumber ||
      page.page_size !== FEEDBACK_PAGE_SIZE ||
      page.total !== firstPage.total ||
      page.items.length > FEEDBACK_PAGE_SIZE
    ) {
      throw new ApiClientError({
        kind: "invalid_response",
        message: "The saved feedback pages changed while they were being rehydrated.",
      });
    }
    for (const item of page.items) feedbackByGame.set(item.game_id, item);
  };

  appendPage(firstPage, 1);
  for (let pageNumber = 2; pageNumber <= expectedPages; pageNumber += 1) {
    if (signal?.aborted || !isCurrent()) return null;
    const page = await client.listFeedback(pageNumber, FEEDBACK_PAGE_SIZE, signal);
    if (signal?.aborted || !isCurrent()) return null;
    appendPage(page, pageNumber);
  }
  if (feedbackByGame.size !== firstPage.total) {
    throw new ApiClientError({
      kind: "invalid_response",
      message: "The saved feedback response was incomplete; try checking it again.",
    });
  }
  return [...feedbackByGame.values()];
}

export function PersistentRecommendationFlow({
  children,
}: PersistentRecommendationFlowProps) {
  const [sessionState, setSessionState] = useState<ConsentPanelState>("bootstrapping");
  const [lifecycle, setLifecycle] = useState<AnonymousSessionResponse | null>(null);
  const [requiredConsentVersion, setRequiredConsentVersion] = useState(
    () => getPublicConfig().consentVersion,
  );
  const [durable, setDurable] = useState<DurableState | null>(null);
  const [preferenceDraft, setPreferenceDraft] =
    useState<PreferenceReplaceRequest>(EMPTY_PREFERENCE_DRAFT);
  const [personalized, setPersonalized] =
    useState<PersonalizedRecommendationResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [feedbackPending, setFeedbackPending] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<Record<number, string>>({});
  const epoch = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const consentHeading = useRef<HTMLHeadingElement>(null);
  const savedContextHeading = useRef<HTMLHeadingElement>(null);
  const personalizedHeading = useRef<HTMLHeadingElement>(null);
  const consentVersion = getPublicConfig().consentVersion;
  const mutationPending = busy || feedbackPending !== null;

  const focusSessionDestination = useCallback(
    (status: AnonymousSessionResponse["status"]) => {
      requestAnimationFrame(() => {
        if (status === "active") savedContextHeading.current?.focus();
        else consentHeading.current?.focus();
      });
    },
    [],
  );

  const clearRouteMemory = useCallback(() => {
    epoch.current += 1;
    controller.current?.abort();
    setDurable(null);
    setLifecycle(null);
    setPreferenceDraft(EMPTY_PREFERENCE_DRAFT);
    setPersonalized(null);
    setFeedbackPending(null);
    setFeedbackMessage({});
    setBusy(false);
  }, []);

  const handleSessionFailure = useCallback(
    (error: unknown, fallback: ConsentPanelState = "error") => {
      if (error instanceof ApiClientError && error.kind === "unauthorized") {
        clearRouteMemory();
        setSessionState("stateless");
        setMessage(
          "The saved session is unavailable. You can opt in again deliberately.",
        );
        return;
      }
      if (error instanceof ApiClientError && error.code === "consent_version_outdated") {
        const currentConsentVersion = errorDetailString(error, "current_consent_version");
        setDurable(null);
        setPreferenceDraft(EMPTY_PREFERENCE_DRAFT);
        setPersonalized(null);
        setFeedbackPending(null);
        setFeedbackMessage({});
        if (currentConsentVersion) setRequiredConsentVersion(currentConsentVersion);
        if (fallback === "stateless") {
          setSessionState("consent_contract_mismatch");
          setMessage(
            "No saved session was created. Reload to review the current consent notice.",
          );
          requestAnimationFrame(() => consentHeading.current?.focus());
          return;
        }
        setLifecycle((current) =>
          current
            ? {
                ...current,
                status: "consent_outdated",
                current_consent_version:
                  currentConsentVersion ?? current.current_consent_version,
              }
            : current,
        );
        setSessionState("consent_outdated");
        setMessage("Your saved session needs renewed permission.");
        requestAnimationFrame(() => consentHeading.current?.focus());
        return;
      }
      if (error instanceof ApiClientError && error.code === "saved_preferences_stale") {
        const staleReferences = errorDetailStrings(error, "references");
        setPersonalized(null);
        if (staleReferences.length) {
          setDurable((current) =>
            current
              ? {
                  ...current,
                  preferences: {
                    ...current.preferences,
                    stale_references: staleReferences,
                  },
                }
              : current,
          );
        }
        setSessionState("active");
        setMessage(errorMessage(error));
        return;
      }
      setSessionState(fallback);
      setMessage(errorMessage(error));
    },
    [clearRouteMemory],
  );

  const rehydrate = useCallback(
    async (session: AnonymousSessionResponse, signal?: AbortSignal) => {
      setLifecycle(session);
      setRequiredConsentVersion(session.current_consent_version);
      if (session.status === "consent_outdated") {
        setDurable(null);
        setPreferenceDraft(EMPTY_PREFERENCE_DRAFT);
        setPersonalized(null);
        setFeedbackPending(null);
        setFeedbackMessage({});
        setSessionState("consent_outdated");
        return;
      }
      const client = getApiClient();
      const requestEpoch = epoch.current;
      const [preferences, feedback] = await Promise.all([
        client.getPreferences(signal),
        loadAllFeedback(client, signal, () => requestEpoch === epoch.current),
      ]);
      if (signal?.aborted || requestEpoch !== epoch.current || feedback === null) return;
      setDurable({ session, preferences, feedback });
      setPersonalized(null);
      setFeedbackPending(null);
      setFeedbackMessage({});
      setPreferenceDraft({
        selected_game_ids: preferences.selected_games.map((game) => game.id),
        preferred_genres: preferences.preferred_genres,
        preferred_tags: preferences.preferred_tags,
        preferred_platforms: preferences.preferred_platforms,
      });
      setSessionState("active");
    },
    [],
  );

  const bootstrap = useCallback(
    async (restoreFocus = false) => {
      controller.current?.abort();
      const nextController = new AbortController();
      controller.current = nextController;
      const requestEpoch = ++epoch.current;
      setBusy(true);
      setMessage(null);
      setSessionState("bootstrapping");
      try {
        const session = await getApiClient().getCurrentSession(nextController.signal);
        if (nextController.signal.aborted || requestEpoch !== epoch.current) return;
        await rehydrate(session, nextController.signal);
        if (restoreFocus && requestEpoch === epoch.current) {
          focusSessionDestination(session.status);
        }
      } catch (error) {
        if (!nextController.signal.aborted && requestEpoch === epoch.current) {
          handleSessionFailure(error);
          if (restoreFocus) requestAnimationFrame(() => consentHeading.current?.focus());
        }
      } finally {
        if (requestEpoch === epoch.current) setBusy(false);
      }
    },
    [focusSessionDestination, handleSessionFailure, rehydrate],
  );

  useEffect(() => {
    void bootstrap();
    return () => controller.current?.abort();
  }, [bootstrap]);

  async function consent(csrfToken?: string) {
    if (mutationPending) return;
    setBusy(true);
    setMessage(null);
    const requestEpoch = epoch.current;
    let session: AnonymousSessionResponse;
    try {
      session = await getApiClient().createAnonymousSession(
        { consent: true, consent_version: consentVersion },
        csrfToken,
      );
    } catch (error) {
      if (requestEpoch === epoch.current) {
        handleSessionFailure(
          error,
          csrfToken === undefined ? "stateless" : "consent_outdated",
        );
      }
      if (requestEpoch === epoch.current) setBusy(false);
      return;
    }
    if (requestEpoch !== epoch.current) return;
    try {
      await rehydrate(session);
      setMessage("Saved personalization is ready.");
      focusSessionDestination(session.status);
    } catch (error) {
      if (requestEpoch === epoch.current) {
        setLifecycle(session);
        setSessionState("error");
        setMessage(
          `${errorMessage(error)} The saved session was created; try checking it again.`,
        );
        requestAnimationFrame(() => consentHeading.current?.focus());
      }
    } finally {
      if (requestEpoch === epoch.current) setBusy(false);
    }
  }

  function reconsent() {
    if (
      lifecycle?.current_consent_version &&
      lifecycle.current_consent_version !== consentVersion
    ) {
      setSessionState("error");
      setMessage(
        "This page has an older consent contract. Reload before reviewing and continuing.",
      );
      requestAnimationFrame(() => consentHeading.current?.focus());
      return;
    }
    void consent(lifecycle?.csrf_token);
  }

  async function clearAllData() {
    const session = lifecycle;
    if (!session || mutationPending) return;
    if (!window.confirm("Clear this anonymous session and all saved GameLens data?"))
      return;
    const requestEpoch = ++epoch.current;
    controller.current?.abort();
    setBusy(true);
    setMessage(null);
    try {
      await getApiClient().deleteCurrentSession(session.csrf_token);
      if (requestEpoch !== epoch.current) return;
      clearRouteMemory();
      setSessionState("stateless");
      setMessage(
        "All saved data was cleared. Request-only recommendations remain available.",
      );
      requestAnimationFrame(() => consentHeading.current?.focus());
    } catch (error) {
      if (requestEpoch === epoch.current) handleSessionFailure(error, sessionState);
    } finally {
      if (requestEpoch === epoch.current) setBusy(false);
    }
  }

  async function savePreferences() {
    if (!durable || mutationPending) return;
    const requestEpoch = epoch.current;
    setBusy(true);
    setMessage(null);
    try {
      const preferences = await getApiClient().replacePreferences(
        preferenceDraft,
        durable.session.csrf_token,
      );
      if (requestEpoch !== epoch.current) return;
      setDurable((current) => (current ? { ...current, preferences } : current));
      setPersonalized(null);
      setMessage("Saved preferences were updated.");
    } catch (error) {
      if (requestEpoch === epoch.current) handleSessionFailure(error, "active");
    } finally {
      if (requestEpoch === epoch.current) setBusy(false);
    }
  }

  async function clearPreferences() {
    if (!durable || mutationPending) return;
    const requestEpoch = epoch.current;
    setBusy(true);
    setMessage(null);
    try {
      await getApiClient().clearPreferences(durable.session.csrf_token);
      if (requestEpoch !== epoch.current) return;
      setDurable((current) =>
        current
          ? {
              ...current,
              preferences: {
                selected_games: [],
                preferred_genres: [],
                preferred_tags: [],
                preferred_platforms: [],
                stale_references: [],
              },
            }
          : current,
      );
      setPreferenceDraft(EMPTY_PREFERENCE_DRAFT);
      setPersonalized(null);
      setMessage("Saved preferences were cleared.");
    } catch (error) {
      if (requestEpoch === epoch.current) handleSessionFailure(error, "active");
    } finally {
      if (requestEpoch === epoch.current) setBusy(false);
    }
  }

  async function refreshFeedback(requestEpoch: number) {
    if (!durable) return;
    const feedback = await loadAllFeedback(
      getApiClient(),
      undefined,
      () => requestEpoch === epoch.current,
    );
    if (requestEpoch !== epoch.current || feedback === null) return;
    setDurable((current) => (current ? { ...current, feedback } : current));
  }

  async function saveFeedback(gameId: number, feedback: FeedbackReplaceRequest) {
    if (!durable || mutationPending) return;
    const requestEpoch = epoch.current;
    setFeedbackPending(gameId);
    setFeedbackMessage((current) => ({ ...current, [gameId]: "Saving feedback…" }));
    try {
      await getApiClient().replaceGameFeedback(
        gameId,
        feedback,
        durable.session.csrf_token,
      );
      if (requestEpoch !== epoch.current) return;
      setPersonalized(null);
      await refreshFeedback(requestEpoch);
      if (requestEpoch !== epoch.current) return;
      setFeedbackMessage((current) => ({ ...current, [gameId]: "Feedback saved." }));
      await generatePersonalized(
        "Feedback saved and recommendations refreshed.",
        requestEpoch,
      );
    } catch (error) {
      if (requestEpoch === epoch.current) {
        handleSessionFailure(error, "active");
        setFeedbackMessage((current) => ({
          ...current,
          [gameId]: `${errorMessage(error)} Your last saved feedback is still shown.`,
        }));
      }
    } finally {
      if (requestEpoch === epoch.current) setFeedbackPending(null);
    }
  }

  async function clearFeedback(gameId: number) {
    if (!durable || mutationPending) return;
    const requestEpoch = epoch.current;
    setFeedbackPending(gameId);
    try {
      await getApiClient().clearGameFeedback(gameId, durable.session.csrf_token);
      if (requestEpoch !== epoch.current) return;
      setPersonalized(null);
      await refreshFeedback(requestEpoch);
      if (requestEpoch !== epoch.current) return;
      setFeedbackMessage((current) => ({ ...current, [gameId]: "Feedback cleared." }));
      await generatePersonalized(
        "Feedback cleared and recommendations refreshed.",
        requestEpoch,
      );
    } catch (error) {
      if (requestEpoch === epoch.current) {
        handleSessionFailure(error, "active");
        setFeedbackMessage((current) => ({ ...current, [gameId]: errorMessage(error) }));
      }
    } finally {
      if (requestEpoch === epoch.current) setFeedbackPending(null);
    }
  }

  async function generatePersonalized(successMessage?: string, chainedEpoch?: number) {
    if (!durable || (chainedEpoch === undefined && mutationPending)) return;
    const requestEpoch = chainedEpoch ?? epoch.current;
    if (chainedEpoch === undefined) setBusy(true);
    setMessage(null);
    try {
      const result = await getApiClient().recommendPersonalized(
        { top_k: 10 },
        durable.session.csrf_token,
      );
      if (requestEpoch !== epoch.current) return;
      setPersonalized(result);
      setMessage(successMessage ?? "Personalized recommendations are ready.");
      requestAnimationFrame(() => personalizedHeading.current?.focus());
    } catch (error) {
      if (requestEpoch === epoch.current) handleSessionFailure(error, "active");
    } finally {
      if (chainedEpoch === undefined && requestEpoch === epoch.current) setBusy(false);
    }
  }

  const feedbackByGame = useMemo(
    () => new Map(durable?.feedback.map((item) => [item.game_id, item])),
    [durable?.feedback],
  );
  const hasSavedContext = Boolean(
    durable &&
    (durable.preferences.selected_games.length ||
      durable.preferences.preferred_genres.length ||
      durable.preferences.preferred_tags.length),
  );

  return (
    <>
      <ConsentPanel
        state={sessionState}
        busy={mutationPending}
        message={message}
        currentConsentVersion={
          lifecycle?.current_consent_version ?? requiredConsentVersion
        }
        expiresAt={lifecycle?.expires_at}
        canClear={lifecycle !== null}
        headingRef={consentHeading}
        onEnable={() => void consent()}
        onReconsent={reconsent}
        onRetry={() => void bootstrap(true)}
        onClear={() => void clearAllData()}
      />

      {durable && sessionState === "active" ? (
        <section
          className="persistence-workspace"
          aria-labelledby="saved-context-heading"
        >
          <p className="eyebrow">Saved recommendation context</p>
          <h2 id="saved-context-heading" ref={savedContextHeading} tabIndex={-1}>
            Review and save your durable choices
          </h2>
          <p>
            Use comma-separated catalog IDs or stable taxonomy slugs. Saving replaces the
            complete stored context; it never changes the request-only form below.
          </p>
          <PreferenceEditor draft={preferenceDraft} onChange={setPreferenceDraft} />
          {durable.preferences.stale_references.length ? (
            <div className="inline-notice recommendation-error" role="alert">
              <div>
                <strong>Some saved references are no longer in the catalog.</strong>
                <p>{durable.preferences.stale_references.join(", ")}</p>
              </div>
            </div>
          ) : null}
          <div className="button-row recommendation-actions">
            <button
              className="button button--primary"
              type="button"
              disabled={mutationPending}
              onClick={() => void savePreferences()}
            >
              {busy ? "Saving…" : "Save complete preference set"}
            </button>
            <button
              className="button button--secondary"
              type="button"
              disabled={mutationPending || !hasSavedContext}
              onClick={() => void generatePersonalized()}
            >
              Generate saved recommendations
            </button>
            <button
              className="text-button"
              type="button"
              disabled={mutationPending}
              onClick={() => void clearPreferences()}
            >
              Clear saved preferences
            </button>
          </div>
          {durable.feedback.length ? (
            <section className="saved-feedback" aria-labelledby="saved-feedback-heading">
              <p className="eyebrow">Current saved feedback</p>
              <h3 id="saved-feedback-heading">Review feedback that survives reload</h3>
              <ul className="saved-feedback__list">
                {durable.feedback.map((feedback) => (
                  <li key={feedback.game_id}>
                    <FeedbackControls
                      key={`${feedback.game_id}:${feedback.latest_occurred_at}:${feedbackPending === feedback.game_id ? "pending" : "idle"}`}
                      gameId={feedback.game_id}
                      gameTitle={feedback.game_title}
                      saved={feedback}
                      disabled={mutationPending}
                      pending={feedbackPending === feedback.game_id}
                      message={feedbackMessage[feedback.game_id]}
                      onSave={(gameId, value) => void saveFeedback(gameId, value)}
                      onClear={(gameId) => void clearFeedback(gameId)}
                    />
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </section>
      ) : null}

      {personalized ? (
        <section
          className="recommendation-results"
          aria-labelledby="personalized-heading"
        >
          <div className="results-heading recommendation-results__heading">
            <div aria-live="polite" aria-atomic="true">
              <p className="eyebrow">Feedback-aware shortlist</p>
              <h2 id="personalized-heading" ref={personalizedHeading} tabIndex={-1}>
                {personalized.items.length
                  ? `${personalized.items.length} personalized recommendations`
                  : "No eligible personalized candidates"}
              </h2>
            </div>
            <p>
              {personalized.policy.name} · v{personalized.policy.version}
            </p>
          </div>
          {personalized.items.length ? (
            <ol className="recommendation-list">
              {personalized.items.map((item) => (
                <li
                  className="recommendation-card recommendation-card--feedback"
                  key={item.game.id}
                >
                  <div
                    className="recommendation-card__rank"
                    aria-label={`Rank ${item.rank}`}
                  >
                    {String(item.rank).padStart(2, "0")}
                  </div>
                  <div className="recommendation-card__body">
                    <p className="eyebrow">Final score {item.ranking_score.toFixed(6)}</p>
                    <h3>
                      <Link href={`/games/${item.game.id}`}>{item.game.title}</Link>
                    </h3>
                    <p>{item.explanation.summary}</p>
                    <details className="score-details">
                      <summary>Inspect personalization components</summary>
                      <dl>
                        <div>
                          <dt>Base</dt>
                          <dd>
                            {item.base_ranking_score.toFixed(6)} ×{" "}
                            {item.base_weight.toFixed(6)} ={" "}
                            {item.base_contribution.toFixed(6)}
                          </dd>
                        </div>
                        <div>
                          <dt>Feedback</dt>
                          <dd>
                            {item.feedback_affinity_score.toFixed(6)} ×{" "}
                            {item.feedback_affinity_weight.toFixed(6)} ={" "}
                            {item.feedback_affinity_contribution.toFixed(6)}
                          </dd>
                        </div>
                        <div>
                          <dt>Played</dt>
                          <dd>
                            factor {item.played_factor.toFixed(6)} · delta{" "}
                            {item.played_delta.toFixed(6)}
                          </dd>
                        </div>
                      </dl>
                    </details>
                    <FeedbackControls
                      key={`${item.game.id}:${feedbackByGame.get(item.game.id)?.latest_occurred_at ?? "none"}:${feedbackPending === item.game.id ? "pending" : "idle"}`}
                      gameId={item.game.id}
                      gameTitle={item.game.title}
                      saved={feedbackByGame.get(item.game.id)}
                      disabled={mutationPending}
                      pending={feedbackPending === item.game.id}
                      message={feedbackMessage[item.game.id]}
                      onSave={(gameId, feedback) => void saveFeedback(gameId, feedback)}
                      onClear={(gameId) => void clearFeedback(gameId)}
                    />
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p>
              No remaining catalog game has positive content support after exclusions.
            </p>
          )}
        </section>
      ) : null}

      <section
        className="stateless-recommendation-section"
        aria-labelledby="request-only-heading"
      >
        <div className="stateless-recommendation-section__heading">
          <p className="eyebrow">Request-only alternative</p>
          <h2 id="request-only-heading">Build a shortlist without saving it</h2>
          <p>
            This existing path remains available before, during, and after consent. Its
            selections are used only for one stateless recommendation request.
          </p>
        </div>
        {children}
      </section>
    </>
  );
}

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function PreferenceEditor({
  draft,
  onChange,
}: {
  draft: PreferenceReplaceRequest;
  onChange: (draft: PreferenceReplaceRequest) => void;
}) {
  return (
    <div className="preference-editor">
      <CommaListInput
        key={`games:${(draft.selected_game_ids ?? []).join(",")}`}
        label="Example game IDs"
        value={(draft.selected_game_ids ?? []).map(String)}
        inputMode="numeric"
        onCommit={(values) =>
          onChange({
            ...draft,
            selected_game_ids: values.filter((value) => /^\d+$/.test(value)).map(Number),
          })
        }
      />
      <CommaListInput
        key={`genres:${(draft.preferred_genres ?? []).join(",")}`}
        label="Genre slugs"
        value={draft.preferred_genres ?? []}
        onCommit={(values) => onChange({ ...draft, preferred_genres: values })}
      />
      <CommaListInput
        key={`tags:${(draft.preferred_tags ?? []).join(",")}`}
        label="Tag slugs"
        value={draft.preferred_tags ?? []}
        onCommit={(values) => onChange({ ...draft, preferred_tags: values })}
      />
      <CommaListInput
        key={`platforms:${(draft.preferred_platforms ?? []).join(",")}`}
        label="Platform slugs"
        value={draft.preferred_platforms ?? []}
        onCommit={(values) => onChange({ ...draft, preferred_platforms: values })}
      />
    </div>
  );
}

function CommaListInput({
  label,
  value,
  inputMode,
  onCommit,
}: {
  label: string;
  value: string[];
  inputMode?: "numeric";
  onCommit: (value: string[]) => void;
}) {
  const canonical = value.join(", ");
  const [draft, setDraft] = useState(canonical);

  return (
    <label>
      {label}
      <input
        type="text"
        inputMode={inputMode}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => onCommit(splitList(draft))}
      />
    </label>
  );
}
