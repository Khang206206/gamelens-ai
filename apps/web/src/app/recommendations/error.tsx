"use client";

import { StateNotice } from "@/components/ui/state-notice";

export default function RecommendationsError({ reset }: { reset: () => void }) {
  return (
    <div className="route-state shell">
      <StateNotice
        eyebrow="Recommendation route"
        title="This workspace could not be opened."
        description="The game catalog remains available while you retry this page."
        tone="warning"
        action={
          <button className="button button--primary" type="button" onClick={reset}>
            Try again
          </button>
        }
      />
    </div>
  );
}
