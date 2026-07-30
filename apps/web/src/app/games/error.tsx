"use client";

import Link from "next/link";

import { StateNotice } from "@/components/ui/state-notice";

export default function GamesError({ reset }: { reset: () => void }) {
  return (
    <div className="shell route-state">
      <StateNotice
        eyebrow="Catalog view error"
        title="The catalog page could not be displayed."
        description="Retry the page or return to the overview. Your saved URL remains unchanged."
        headingLevel={1}
        tone="warning"
        action={
          <div className="button-row">
            <button className="button button--primary" type="button" onClick={reset}>
              Try again
            </button>
            <Link className="button button--secondary" href="/">
              Overview
            </Link>
          </div>
        }
      />
    </div>
  );
}
