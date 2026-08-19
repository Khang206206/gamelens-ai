"use client";

import type { RefObject } from "react";

export type ConsentPanelState =
  | "bootstrapping"
  | "stateless"
  | "active"
  | "consent_outdated"
  | "consent_contract_mismatch"
  | "error";

interface ConsentPanelProps {
  state: ConsentPanelState;
  busy: boolean;
  message?: string | null;
  currentConsentVersion?: string;
  expiresAt?: string;
  canClear: boolean;
  headingRef: RefObject<HTMLHeadingElement | null>;
  onEnable: () => void;
  onReconsent: () => void;
  onRetry: () => void;
  onClear: () => void;
}

export function ConsentPanel({
  state,
  busy,
  message,
  currentConsentVersion,
  expiresAt,
  canClear,
  headingRef,
  onEnable,
  onReconsent,
  onRetry,
  onClear,
}: ConsentPanelProps) {
  const expiryText = expiresAt
    ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(
        new Date(expiresAt),
      )
    : null;

  return (
    <section className="persistence-panel" aria-labelledby="persistence-heading">
      <div className="persistence-panel__heading">
        <div>
          <p className="eyebrow">Optional saved personalization</p>
          <h2 id="persistence-heading" ref={headingRef} tabIndex={-1}>
            Keep your choices on this browser
          </h2>
        </div>
        {state === "active" ? <span className="status-chip">Active</span> : null}
      </div>
      <p>
        With your permission, GameLens stores an anonymous session cookie, your saved
        selections, feedback, and personalized recommendation events. This consent notice
        is version{" "}
        <strong>{currentConsentVersion ?? "the current server version"}</strong>. Access
        is time-limited to a fixed expiry shown immediately after opt-in, and eligible
        data is removed by the next cleanup run. You can clear everything at any time.
      </p>
      <p>
        You can also skip this option and use the request-only recommender below. That
        path does not save selections or feedback.
      </p>

      {state === "bootstrapping" ? (
        <p className="persistence-status" role="status" aria-live="polite">
          Checking for an existing saved session…
        </p>
      ) : null}

      {state === "stateless" ? (
        <div className="persistence-actions">
          <button
            className="button button--primary"
            type="button"
            disabled={busy}
            onClick={onEnable}
          >
            {busy ? "Enabling…" : "Enable saved personalization"}
          </button>
        </div>
      ) : null}

      {state === "error" ? (
        <div className="inline-notice recommendation-error" role="alert">
          <div>
            <strong>Saved personalization could not be checked.</strong>
            <p>{message ?? "The saved session service is temporarily unavailable."}</p>
          </div>
          <div className="button-row">
            <button
              className="text-button"
              type="button"
              disabled={busy}
              onClick={onRetry}
            >
              {busy ? "Checking…" : "Try again"}
            </button>
            {canClear ? (
              <button
                className="text-button"
                type="button"
                disabled={busy}
                onClick={onClear}
              >
                Clear saved data
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {state === "consent_contract_mismatch" ? (
        <div className="inline-notice recommendation-error" role="alert">
          <div>
            <strong>This page has an older consent notice.</strong>
            <p>
              No saved session was created. Reload this page to receive consent version{" "}
              {currentConsentVersion ?? "the current server version"} before choosing
              whether to opt in.
            </p>
          </div>
          <a className="text-button" href="/recommendations">
            Reload this page
          </a>
        </div>
      ) : null}

      {state === "consent_outdated" ? (
        <div className="inline-notice recommendation-error" role="alert">
          <div>
            <strong>Your saved choices need renewed permission.</strong>
            <p>
              Review this storage description, then explicitly continue with consent
              version {currentConsentVersion ?? "the current version"}. Your existing
              saved state remains unavailable until then.
            </p>
          </div>
          <div className="button-row">
            <button
              className="button button--primary"
              type="button"
              disabled={busy}
              onClick={onReconsent}
            >
              {busy ? "Updating permission…" : "Continue with saved personalization"}
            </button>
            <button
              className="button button--secondary"
              type="button"
              disabled={busy}
              onClick={onClear}
            >
              Clear saved data
            </button>
          </div>
        </div>
      ) : null}

      {state === "active" ? (
        <div className="persistence-session-summary">
          <p className="persistence-status" role="status">
            Saved personalization is active
            {expiryText ? ` until ${expiryText}` : " for this anonymous session"}.
          </p>
          <button className="text-button" type="button" disabled={busy} onClick={onClear}>
            Clear all saved data
          </button>
        </div>
      ) : null}

      {message &&
      state !== "error" &&
      state !== "consent_contract_mismatch" &&
      state !== "consent_outdated" ? (
        <p className="persistence-status" role="status" aria-live="polite">
          {message}
        </p>
      ) : null}
    </section>
  );
}
