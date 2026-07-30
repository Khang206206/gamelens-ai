"use client";

import Link from "next/link";

import { StateNotice } from "@/components/ui/state-notice";

export default function RootError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="shell route-state">
      <StateNotice
        eyebrow="Application error"
        title="This view could not be assembled."
        description="Try the page again. If the problem continues, return to the catalog."
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
