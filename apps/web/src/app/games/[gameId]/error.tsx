"use client";

import Link from "next/link";

import { StateNotice } from "@/components/ui/state-notice";

export default function GameDetailError({ reset }: { reset: () => void }) {
  return (
    <div className="shell route-state">
      <StateNotice
        eyebrow="Detail view error"
        title="This game view could not be displayed."
        description="Retry the route or return to the catalog."
        headingLevel={1}
        tone="warning"
        action={
          <div className="button-row">
            <button className="button button--primary" type="button" onClick={reset}>
              Try again
            </button>
            <Link className="button button--secondary" href="/games">
              Open catalog
            </Link>
          </div>
        }
      />
    </div>
  );
}
