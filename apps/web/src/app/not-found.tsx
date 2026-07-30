import Link from "next/link";

import { StateNotice } from "@/components/ui/state-notice";

export default function NotFound() {
  return (
    <div className="shell route-state">
      <StateNotice
        eyebrow="404 · Uncharted route"
        title="This page is outside the catalog."
        description="The address may be incomplete, or the page may have moved."
        headingLevel={1}
        action={
          <Link className="button button--primary" href="/games">
            Return to the catalog
          </Link>
        }
      />
    </div>
  );
}
