import type { Route } from "next";
import Link from "next/link";
import type { RefObject } from "react";

import { FeedbackControls } from "@/features/recommendations/feedback-controls";
import type {
  FeedbackReplaceRequest,
  FeedbackResource,
  PersonalizedRecommendationResponse,
} from "@/lib/api/client";

type FallbackReason = NonNullable<PersonalizedRecommendationResponse["fallback_reason"]>;

export type PersonalizedResultsState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; result: PersonalizedRecommendationResponse };

interface PersonalizedRecommendationResultsProps {
  state: PersonalizedResultsState;
  headingRef: RefObject<HTMLHeadingElement | null>;
  feedbackByGame: ReadonlyMap<number, FeedbackResource>;
  feedbackPending: number | null;
  feedbackMessage: Readonly<Record<number, string>>;
  mutationPending: boolean;
  onRetry: () => void;
  onSaveFeedback: (gameId: number, feedback: FeedbackReplaceRequest) => void;
  onClearFeedback: (gameId: number) => void;
}

const FALLBACK_COPY: Record<FallbackReason, string> = {
  not_configured: "The optional aggregate interaction component is not configured.",
  fixture_not_allowed:
    "A test-only aggregate interaction component is not enabled in this environment.",
  insufficient_data:
    "There was not enough eligible aggregate interaction data for this request.",
  artifact_missing:
    "The optional aggregate interaction component was not available to the server.",
  artifact_corrupt:
    "The optional aggregate interaction component could not be read safely.",
  artifact_incompatible:
    "The optional aggregate interaction component was not compatible with this server.",
  artifact_stale:
    "The optional aggregate interaction component did not match the current saved-data state.",
  privacy_invalid:
    "The optional aggregate interaction component was no longer eligible for use.",
  artifact_expired:
    "The optional aggregate interaction component passed its validity window.",
  catalog_stale:
    "The optional aggregate interaction component did not match the current catalog.",
  artifact_retired: "The optional aggregate interaction component was retired.",
  no_query_sources:
    "Your saved context did not contain an eligible positive source for aggregate matching.",
  no_supported_sources:
    "Your saved positive sources had no retained aggregate interaction support.",
  no_candidate_edges: "No eligible candidate had retained aggregate interaction support.",
  no_eligible_candidates:
    "No aggregate interaction candidate remained after the request exclusions.",
};

const EMPTY_COPY: Record<PersonalizedRecommendationResponse["response_reason"], string> =
  {
    recommendations: "The server returned no eligible item for this saved request.",
    no_content_support:
      "No remaining catalog game had positive content support after the saved exclusions.",
    no_eligible_candidates:
      "No candidate remained after the saved sources, dislikes, and other exclusions were applied.",
  };

function candidateOriginLabel(
  origin: PersonalizedRecommendationResponse["items"][number]["candidate_origin"],
): string {
  if (origin === "both") return "Content + aggregate candidate";
  if (origin === "collaborative") return "Aggregate interaction candidate";
  return "Content candidate";
}

function sourceKindLabel(
  kind: PersonalizedRecommendationResponse["items"][number]["collaborative_source_edges"][number]["source_kind"],
): string {
  if (kind === "saved_game") return "saved game";
  if (kind === "rating") return "positive rating";
  return "liked game";
}

export function PersonalizedRecommendationResults({
  state,
  headingRef,
  feedbackByGame,
  feedbackPending,
  feedbackMessage,
  mutationPending,
  onRetry,
  onSaveFeedback,
  onClearFeedback,
}: PersonalizedRecommendationResultsProps) {
  if (state.status === "idle") return null;

  if (state.status === "loading") {
    return (
      <section
        className="recommendation-results recommendation-results--saved-status"
        aria-labelledby="personalized-heading"
      >
        <div role="status" aria-live="polite" aria-atomic="true">
          <p className="eyebrow">Saved recommendation request</p>
          <h2 id="personalized-heading" ref={headingRef} tabIndex={-1}>
            Generating saved recommendations
          </h2>
          <p>The server is preparing an ordered shortlist from your saved context.</p>
        </div>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section
        className="recommendation-results recommendation-results--saved-status"
        aria-labelledby="personalized-heading"
      >
        <div className="inline-notice recommendation-error" role="alert">
          <div>
            <p className="eyebrow">Saved results unavailable</p>
            <h2 id="personalized-heading" ref={headingRef} tabIndex={-1}>
              Saved recommendations need attention
            </h2>
            <p>{state.message}</p>
          </div>
          <button className="text-button" type="button" onClick={onRetry}>
            Try saved recommendations again
          </button>
        </div>
      </section>
    );
  }

  const { result } = state;
  const fallbackReason = result.fallback_reason;

  return (
    <section className="recommendation-results" aria-labelledby="personalized-heading">
      <div className="results-heading recommendation-results__heading">
        <div aria-live="polite" aria-atomic="true">
          <p className="eyebrow">Feedback-aware shortlist</p>
          <h2 id="personalized-heading" ref={headingRef} tabIndex={-1}>
            {result.items.length
              ? `${result.items.length} personalized recommendations`
              : "No eligible personalized candidates"}
          </h2>
        </div>
        <p>
          {result.policy.name} · v{result.policy.version}
        </p>
      </div>

      {result.ranking_mode === "hybrid" ? (
        <section
          className="ranking-mode-notice ranking-mode-notice--hybrid"
          aria-labelledby="ranking-mode-heading"
        >
          <p className="eyebrow">Ranking mode</p>
          <h3 id="ranking-mode-heading">Hybrid ranking applied</h3>
          <p>
            The server combined available content and saved-feedback signals with a
            bounded aggregate interaction signal. This is ranking evidence, not a quality
            claim or social proof.
          </p>
        </section>
      ) : (
        <section
          className="ranking-mode-notice ranking-mode-notice--fallback"
          aria-labelledby="ranking-mode-heading"
        >
          <p className="eyebrow">Ranking mode</p>
          <h3 id="ranking-mode-heading">Saved ranking fallback</h3>
          <p>
            The optional aggregate interaction signal was not applied. The server kept the
            established content and saved-feedback ranking path available.
          </p>
          {fallbackReason ? <p>{FALLBACK_COPY[fallbackReason]}</p> : null}
        </section>
      )}

      {result.items.length ? (
        <ol className="recommendation-list">
          {result.items.map((item) => {
            const aggregateApplied =
              result.ranking_mode === "hybrid" &&
              item.collaborative_supported &&
              item.collaborative_contribution > 0;
            const evidenceHeadingId = `aggregate-evidence-${item.game.id}`;
            return (
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
                  <div className="recommendation-card__signals">
                    <p className="eyebrow">Final score {item.ranking_score.toFixed(6)}</p>
                    <p>{candidateOriginLabel(item.candidate_origin)}</p>
                  </div>
                  <h3>
                    <Link href={`/games/${item.game.id}` as Route}>
                      {item.game.title}
                    </Link>
                  </h3>
                  <p>{item.explanation.summary}</p>
                  {aggregateApplied ? (
                    <section
                      className="aggregate-evidence"
                      aria-labelledby={evidenceHeadingId}
                    >
                      <p className="eyebrow">Applied signal</p>
                      <h4 id={evidenceHeadingId}>Aggregate interaction evidence</h4>
                      <p>
                        Bounded relationships to your explicit positive sources
                        contributed to this item. Similarity is a ranking signal, not a
                        probability, popularity measure, or quality score; individual
                        identities are not included here.
                      </p>
                      <dl>
                        <div>
                          <dt>Aggregate item support</dt>
                          <dd>{item.collaborative_item_support}</dd>
                        </div>
                        <div>
                          <dt>Retained source relationships</dt>
                          <dd>{item.collaborative_source_edges.length}</dd>
                        </div>
                      </dl>
                      <ul>
                        {item.collaborative_source_edges.map((edge) => (
                          <li key={edge.source_game_slug}>
                            <span>
                              <code>{edge.source_game_slug}</code> ·{" "}
                              {sourceKindLabel(edge.source_kind)}
                            </span>
                            <span>
                              similarity {edge.similarity_score.toFixed(6)} · pair support{" "}
                              {edge.pair_support}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </section>
                  ) : null}
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
                      {aggregateApplied ? (
                        <div>
                          <dt>Aggregate interaction</dt>
                          <dd>
                            {item.collaborative_score.toFixed(6)} ×{" "}
                            {item.collaborative_weight.toFixed(6)} ={" "}
                            {item.collaborative_contribution.toFixed(6)}
                          </dd>
                        </div>
                      ) : null}
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
                    onSave={onSaveFeedback}
                    onClear={onClearFeedback}
                  />
                </div>
              </li>
            );
          })}
        </ol>
      ) : (
        <div className="personalized-empty" role="status">
          <p className="eyebrow">Valid empty result</p>
          <h3>No ranked item was returned</h3>
          <p>{EMPTY_COPY[result.response_reason]}</p>
          <p>Your saved context remains available to review or adjust.</p>
        </div>
      )}
    </section>
  );
}
