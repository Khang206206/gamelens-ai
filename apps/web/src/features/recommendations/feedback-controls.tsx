"use client";

import { useState } from "react";

import type { FeedbackReplaceRequest, FeedbackResource } from "@/lib/api/client";

export const EMPTY_FEEDBACK: FeedbackReplaceRequest = {
  reaction: null,
  played: false,
  wishlisted: false,
  rating: null,
};

interface FeedbackControlsProps {
  gameId: number;
  gameTitle: string;
  saved?: FeedbackResource;
  disabled?: boolean;
  pending: boolean;
  message?: string;
  onSave: (gameId: number, feedback: FeedbackReplaceRequest) => void;
  onClear: (gameId: number) => void;
}

function feedbackFromResource(saved?: FeedbackResource): FeedbackReplaceRequest {
  if (!saved) return EMPTY_FEEDBACK;
  return {
    reaction: saved.reaction,
    played: saved.played,
    wishlisted: saved.wishlisted,
    rating: saved.rating,
  };
}

export function FeedbackControls({
  gameId,
  gameTitle,
  saved,
  disabled = false,
  pending,
  message,
  onSave,
  onClear,
}: FeedbackControlsProps) {
  const [draft, setDraft] = useState<FeedbackReplaceRequest>(() =>
    feedbackFromResource(saved),
  );

  return (
    <fieldset className="feedback-controls" disabled={disabled || pending}>
      <legend>Feedback for {gameTitle}</legend>
      <div className="feedback-controls__grid">
        <label>
          Reaction
          <select
            value={draft.reaction ?? ""}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                reaction:
                  event.target.value === "liked" || event.target.value === "disliked"
                    ? event.target.value
                    : null,
              }))
            }
          >
            <option value="">No reaction</option>
            <option value="liked">Liked</option>
            <option value="disliked">Disliked</option>
          </select>
        </label>
        <label>
          Rating
          <select
            value={draft.rating === null ? "" : String(draft.rating)}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                rating: event.target.value === "" ? null : Number(event.target.value),
              }))
            }
          >
            <option value="">No rating</option>
            {Array.from({ length: 21 }, (_, index) => index / 2).map((rating) => (
              <option key={rating} value={rating}>
                {rating.toFixed(1)} / 10
              </option>
            ))}
          </select>
        </label>
        <label className="feedback-controls__check">
          <input
            type="checkbox"
            checked={draft.played}
            onChange={(event) =>
              setDraft((current) => ({ ...current, played: event.target.checked }))
            }
          />
          Played
        </label>
        <label className="feedback-controls__check">
          <input
            type="checkbox"
            checked={draft.wishlisted}
            onChange={(event) =>
              setDraft((current) => ({ ...current, wishlisted: event.target.checked }))
            }
          />
          Wishlist
        </label>
      </div>
      <div className="button-row feedback-controls__actions">
        <button
          className="button button--secondary"
          type="button"
          onClick={() => onSave(gameId, draft)}
        >
          {pending ? "Saving feedback…" : "Save feedback"}
        </button>
        {saved ? (
          <button className="text-button" type="button" onClick={() => onClear(gameId)}>
            Clear feedback
          </button>
        ) : null}
      </div>
      <p className="persistence-status" role="status" aria-live="polite">
        {message ?? ""}
      </p>
    </fieldset>
  );
}
