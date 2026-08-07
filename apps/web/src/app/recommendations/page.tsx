import type { Metadata } from "next";
import Link from "next/link";

import { RecommendationFlow } from "@/features/recommendations/recommendation-flow";

export const metadata: Metadata = {
  title: "Game recommendations",
  description:
    "Choose request-scoped game and taxonomy preferences to receive explained content recommendations.",
};

export default function RecommendationsPage() {
  return (
    <div className="recommendation-page shell">
      <header className="route-heading">
        <p className="eyebrow">Anonymous content model</p>
        <h1>Shape your next shortlist</h1>
        <p>
          Pick games or themes you enjoy. Your choices are used for this request only and
          are not saved to an account or treated as feedback.
        </p>
      </header>
      <noscript>
        <div className="inline-notice recommendation-error">
          <div>
            <strong>Recommendations require JavaScript.</strong>
            <p>
              This request-scoped flow runs in the browser. The game catalog remains
              available without creating an account or saving preferences.
            </p>
          </div>
          <Link className="text-link" href="/games">
            Browse the catalog
          </Link>
        </div>
      </noscript>
      <RecommendationFlow />
    </div>
  );
}
