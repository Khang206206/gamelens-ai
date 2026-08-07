"use client";

import type { Route } from "next";
import Link from "next/link";
import {
  type Dispatch,
  type RefObject,
  type SetStateAction,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { StateNotice } from "@/components/ui/state-notice";
import {
  type GameSummary,
  getApiClient,
  type RecommendationRequest,
  type RecommendationResponse,
  type TaxonomyItem,
} from "@/lib/api/client";
import { ApiClientError } from "@/lib/api/errors";

type Step = "select" | "review" | "results";

interface OptionsState {
  loading: boolean;
  error: string | null;
  games: GameSummary[];
  genres: TaxonomyItem[];
  tags: TaxonomyItem[];
  platforms: TaxonomyItem[];
}

const emptyOptions: OptionsState = {
  loading: true,
  error: null,
  games: [],
  genres: [],
  tags: [],
  platforms: [],
};

export function RecommendationFlow() {
  const [options, setOptions] = useState<OptionsState>(emptyOptions);
  const [optionsRetry, setOptionsRetry] = useState(0);
  const [step, setStep] = useState<Step>("select");
  const [gameSearch, setGameSearch] = useState("");
  const [gameIds, setGameIds] = useState<number[]>([]);
  const [genres, setGenres] = useState<string[]>([]);
  const [tags, setTags] = useState<string[]>([]);
  const [platforms, setPlatforms] = useState<string[]>([]);
  const [result, setResult] = useState<RecommendationResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<ApiClientError | null>(null);
  const submissionKey = useRef(0);
  const submitController = useRef<AbortController | null>(null);
  const stepHeading = useRef<HTMLHeadingElement>(null);
  const previousStep = useRef<Step>(step);

  useEffect(() => {
    const controller = new AbortController();
    const client = getApiClient();
    Promise.allSettled([
      client.listGames({ page: 1, pageSize: 100, sort: "title" }, controller.signal),
      client.listGenres(controller.signal),
      client.listTags(controller.signal),
      client.listPlatforms(controller.signal),
    ])
      .then(([games, loadedGenres, loadedTags, loadedPlatforms]) => {
        if (!controller.signal.aborted) {
          const failures = [games, loadedGenres, loadedTags, loadedPlatforms].filter(
            (loaded) => loaded.status === "rejected",
          );
          const firstFailure = failures[0];
          setOptions((current) => ({
            loading: false,
            error:
              firstFailure?.status === "rejected"
                ? firstFailure.reason instanceof ApiClientError
                  ? firstFailure.reason.message
                  : "Some selection options could not be loaded."
                : null,
            games: games.status === "fulfilled" ? games.value.items : current.games,
            genres:
              loadedGenres.status === "fulfilled" ? loadedGenres.value : current.genres,
            tags: loadedTags.status === "fulfilled" ? loadedTags.value : current.tags,
            platforms:
              loadedPlatforms.status === "fulfilled"
                ? loadedPlatforms.value
                : current.platforms,
          }));
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setOptions((current) => ({
            ...current,
            loading: false,
            error:
              error instanceof ApiClientError
                ? error.message
                : "The selection options could not be loaded.",
          }));
        }
      });
    return () => controller.abort();
  }, [optionsRetry]);

  useEffect(() => () => submitController.current?.abort(), []);

  useEffect(() => {
    if (previousStep.current !== step) {
      previousStep.current = step;
      stepHeading.current?.focus();
    }
  }, [step]);

  const hasPrimaryContext = gameIds.length + genres.length + tags.length > 0;
  const visibleGames = useMemo(() => {
    const query = gameSearch.trim().toLocaleLowerCase();
    const selected = new Set(gameIds);
    const matches = options.games.filter(
      (game) =>
        selected.has(game.id) || !query || game.title.toLocaleLowerCase().includes(query),
    );
    return [
      ...matches.filter((game) => selected.has(game.id)),
      ...matches.filter((game) => !selected.has(game.id)),
    ].slice(0, 16);
  }, [gameIds, gameSearch, options.games]);

  const hasUsableOptions =
    options.games.length + options.genres.length + options.tags.length > 0;

  function retryOptions() {
    setOptions((current) => ({ ...current, loading: true }));
    setOptionsRetry((value) => value + 1);
  }

  function toggleNumber(value: number) {
    setGameIds((current) => {
      if (current.includes(value)) return current.filter((item) => item !== value);
      return current.length >= 5 ? current : [...current, value];
    });
  }

  function toggleString(
    value: string,
    setter: Dispatch<SetStateAction<string[]>>,
    limit: number,
  ) {
    setter((current) => {
      if (current.includes(value)) return current.filter((item) => item !== value);
      return current.length >= limit ? current : [...current, value];
    });
  }

  function requestBody(): RecommendationRequest {
    return {
      selected_game_ids: gameIds,
      preferred_genres: genres,
      preferred_tags: tags,
      preferred_platforms: platforms,
      top_k: 10,
    };
  }

  async function submit() {
    if (!hasPrimaryContext) return;
    submitController.current?.abort();
    const controller = new AbortController();
    submitController.current = controller;
    const key = ++submissionKey.current;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const response = await getApiClient().recommend(requestBody(), controller.signal);
      if (!controller.signal.aborted && key === submissionKey.current) {
        setResult(response);
        setStep("results");
      }
    } catch (error) {
      if (!controller.signal.aborted && key === submissionKey.current) {
        setSubmitError(
          error instanceof ApiClientError
            ? error
            : new ApiClientError({
                kind: "unexpected",
                message: "The recommendation request could not be completed.",
              }),
        );
      }
    } finally {
      if (key === submissionKey.current) setSubmitting(false);
    }
  }

  function startOver() {
    submitController.current?.abort();
    submissionKey.current += 1;
    setGameIds([]);
    setGenres([]);
    setTags([]);
    setPlatforms([]);
    setGameSearch("");
    setResult(null);
    setSubmitError(null);
    setSubmitting(false);
    setStep("select");
  }

  if (options.loading && !hasUsableOptions) {
    return (
      <div
        className="recommendation-workspace recommendation-workspace--loading"
        role="status"
      >
        Loading games and preference options…
      </div>
    );
  }

  if (options.error && !hasUsableOptions) {
    return (
      <StateNotice
        eyebrow="Catalog connection"
        title="Selections are unavailable right now."
        description={options.error}
        tone="warning"
        action={
          <button className="button button--primary" type="button" onClick={retryOptions}>
            Retry options
          </button>
        }
      />
    );
  }

  if (step === "results" && result) {
    return (
      <RecommendationResults
        headingRef={stepHeading}
        result={result}
        onAdjust={() => setStep("select")}
        onStartOver={startOver}
      />
    );
  }

  if (step === "review") {
    return (
      <section className="recommendation-workspace" aria-labelledby="review-heading">
        <Progress current={2} />
        <p className="eyebrow">Review this request</p>
        <h2 id="review-heading" ref={stepHeading} tabIndex={-1}>
          Ready for the content model
        </h2>
        <p>
          These choices stay in this mounted flow. Submitting does not create a user,
          interaction, or saved preference.
        </p>
        <SelectionSummary
          options={options}
          gameIds={gameIds}
          genres={genres}
          tags={tags}
          platforms={platforms}
        />
        {submitError ? <SubmitFailure error={submitError} onRetry={submit} /> : null}
        <div className="button-row recommendation-actions">
          <button
            className="button button--primary"
            type="button"
            disabled={submitting}
            onClick={submit}
          >
            {submitting ? "Ranking games…" : "Get recommendations"}
          </button>
          <button
            className="button button--secondary"
            type="button"
            disabled={submitting}
            onClick={() => setStep("select")}
          >
            Edit selections
          </button>
          <button className="text-button" type="button" onClick={startOver}>
            Start over
          </button>
        </div>
        <p className="recommendation-status" role="status" aria-live="polite">
          {submitting ? "The model is scoring catalog candidates." : ""}
        </p>
      </section>
    );
  }

  return (
    <section className="recommendation-workspace" aria-labelledby="selection-heading">
      <Progress current={1} />
      {options.error ? (
        <div className="inline-notice recommendation-error" role="status">
          <div>
            <strong>Some selection options are temporarily unavailable.</strong>
            <p>{options.error} Available choices remain usable.</p>
          </div>
          <button
            className="text-button"
            type="button"
            disabled={options.loading}
            onClick={retryOptions}
          >
            {options.loading ? "Retrying…" : "Retry options"}
          </button>
        </div>
      ) : null}
      <div className="recommendation-section-heading">
        <div>
          <p className="eyebrow">Build request context</p>
          <h2 id="selection-heading" ref={stepHeading} tabIndex={-1}>
            What feels worth playing?
          </h2>
        </div>
        <p>{gameIds.length}/5 games selected</p>
      </div>

      <fieldset className="preference-fieldset">
        <legend>
          Example games <span>Optional · choose up to five</span>
        </legend>
        <label className="recommendation-search">
          Search the loaded catalog
          <input
            type="search"
            value={gameSearch}
            maxLength={100}
            placeholder="Search game titles"
            onChange={(event) => setGameSearch(event.target.value)}
          />
        </label>
        <div className="choice-grid choice-grid--games">
          {visibleGames.map((game) => (
            <label className="choice-card" key={game.id}>
              <input
                type="checkbox"
                checked={gameIds.includes(game.id)}
                disabled={!gameIds.includes(game.id) && gameIds.length >= 5}
                onChange={() => toggleNumber(game.id)}
              />
              <span>
                <strong>{game.title}</strong>
                <small>{game.genres[0]?.name ?? "Genre not listed"}</small>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      <TaxonomyChoices
        legend="Preferred genres"
        hint="Choose up to five"
        values={options.genres}
        selected={genres}
        limit={5}
        onToggle={(value) => toggleString(value, setGenres, 5)}
      />
      <TaxonomyChoices
        legend="Themes and play styles"
        hint="Choose up to ten tags"
        values={options.tags}
        selected={tags}
        limit={10}
        onToggle={(value) => toggleString(value, setTags, 10)}
      />
      <TaxonomyChoices
        legend="Preferred platforms"
        hint="Optional secondary signal · choose up to six"
        values={options.platforms}
        selected={platforms}
        limit={6}
        onToggle={(value) => toggleString(value, setPlatforms, 6)}
      />

      {!hasPrimaryContext ? (
        <p className="inline-validation" role="status">
          Select at least one game, genre, or tag. Platform alone cannot form a content
          query.
        </p>
      ) : null}
      <div className="button-row recommendation-actions">
        <button
          className="button button--primary"
          type="button"
          disabled={!hasPrimaryContext}
          onClick={() => setStep("review")}
        >
          Review selections
        </button>
        <button className="text-button" type="button" onClick={startOver}>
          Clear selections
        </button>
      </div>
    </section>
  );
}

function Progress({ current }: { current: 1 | 2 }) {
  return (
    <p className="recommendation-progress" aria-label={`Step ${current} of 2`}>
      <strong>0{current}</strong> / 02 · {current === 1 ? "Select" : "Review"}
    </p>
  );
}

function TaxonomyChoices({
  legend,
  hint,
  values,
  selected,
  limit,
  onToggle,
}: {
  legend: string;
  hint: string;
  values: TaxonomyItem[];
  selected: string[];
  limit: number;
  onToggle: (value: string) => void;
}) {
  return (
    <fieldset className="preference-fieldset">
      <legend>
        {legend} <span>{hint}</span>
      </legend>
      <div className="choice-grid">
        {values.map((value) => (
          <label className="choice-pill" key={value.slug}>
            <input
              type="checkbox"
              checked={selected.includes(value.slug)}
              disabled={!selected.includes(value.slug) && selected.length >= limit}
              onChange={() => onToggle(value.slug)}
            />
            <span>{value.name}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function SelectionSummary({
  options,
  gameIds,
  genres,
  tags,
  platforms,
}: {
  options: OptionsState;
  gameIds: number[];
  genres: string[];
  tags: string[];
  platforms: string[];
}) {
  const names = (values: TaxonomyItem[], selected: string[]) =>
    values.filter((value) => selected.includes(value.slug)).map((value) => value.name);
  const groups = [
    [
      "Games",
      options.games.filter((game) => gameIds.includes(game.id)).map((game) => game.title),
    ],
    ["Genres", names(options.genres, genres)],
    ["Tags", names(options.tags, tags)],
    ["Platforms", names(options.platforms, platforms)],
  ] as const;
  return (
    <dl className="selection-summary">
      {groups.map(([label, values]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{values.length ? values.join(", ") : "None selected"}</dd>
        </div>
      ))}
    </dl>
  );
}

function SubmitFailure({
  error,
  onRetry,
}: {
  error: ApiClientError;
  onRetry: () => void;
}) {
  const modelUnavailable =
    error.code === "model_not_configured" || error.kind === "unavailable";
  return (
    <div className="inline-notice recommendation-error" role="alert">
      <div>
        <strong>
          {modelUnavailable
            ? "Recommendations are temporarily unavailable."
            : "This request needs attention."}
        </strong>
        <p>
          {error.code === "catalog_stale"
            ? "The catalog changed after this model artifact was built. Browsing still works while an updated artifact is prepared."
            : error.message}
        </p>
      </div>
      <button className="text-button" type="button" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}

function RecommendationResults({
  headingRef,
  result,
  onAdjust,
  onStartOver,
}: {
  headingRef: RefObject<HTMLHeadingElement | null>;
  result: RecommendationResponse;
  onAdjust: () => void;
  onStartOver: () => void;
}) {
  return (
    <section className="recommendation-results" aria-labelledby="results-heading">
      <div className="results-heading recommendation-results__heading">
        <div aria-live="polite" aria-atomic="true">
          <p className="eyebrow">Explained shortlist</p>
          <h2 id="results-heading" ref={headingRef} tabIndex={-1}>
            {result.items.length
              ? `${result.items.length} ranked recommendations`
              : "No content-supported candidates"}
          </h2>
        </div>
        <p>
          {result.model.name} · v{result.model.version}
        </p>
      </div>
      {result.items.length ? (
        <ol className="recommendation-list">
          {result.items.map((item) => {
            const additionalReasons = item.explanation.reasons.filter(
              (reason) => reason !== item.explanation.summary,
            );
            return (
              <li className="recommendation-card" key={item.game.id}>
                <div
                  className="recommendation-card__rank"
                  aria-label={`Rank ${item.rank}`}
                >
                  {String(item.rank).padStart(2, "0")}
                </div>
                <div className="recommendation-card__body">
                  <p className="eyebrow">Ranking score {item.ranking_score.toFixed(6)}</p>
                  <h3>
                    <Link href={`/games/${item.game.id}` as Route}>
                      {item.game.title}
                    </Link>
                  </h3>
                  <p>{item.explanation.summary}</p>
                  {additionalReasons.length ? (
                    <ul className="reason-list">
                      {additionalReasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  ) : null}
                  <details className="score-details">
                    <summary>Inspect score components</summary>
                    <dl>
                      {item.components.map((component) => (
                        <div key={component.name}>
                          <dt>{component.name}</dt>
                          <dd>
                            {component.raw_score.toFixed(6)} ×{" "}
                            {component.weight.toFixed(6)} ={" "}
                            {component.contribution.toFixed(6)}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </details>
                </div>
              </li>
            );
          })}
        </ol>
      ) : (
        <StateNotice
          eyebrow="Valid empty result"
          title="Try a broader signal mix."
          description="No remaining catalog game had positive content support after exclusions. Adjust a game, genre, or tag—platform and popularity never create a fallback list by themselves."
        />
      )}
      <div className="button-row recommendation-actions">
        <button className="button button--primary" type="button" onClick={onAdjust}>
          Adjust selections
        </button>
        <button className="button button--secondary" type="button" onClick={onStartOver}>
          Start over
        </button>
        <Link className="text-link" href="/games">
          Browse the catalog
        </Link>
      </div>
    </section>
  );
}
