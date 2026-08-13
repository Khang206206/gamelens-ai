import type { Metadata } from "next";
import Link from "next/link";

import { PersistentRecommendationFlow } from "@/features/recommendations/persistent-recommendation-flow";
import { RecommendationFlow } from "@/features/recommendations/recommendation-flow";

export const metadata: Metadata = {
  title: "Game recommendations",
  description:
    "Choose request-only recommendations or explicitly opt in to anonymous saved personalization and feedback.",
};

export default function RecommendationsPage() {
  return (
    <div className="recommendation-page shell">
      <header className="route-heading">
        <p className="eyebrow">Anonymous content model</p>
        <h1>Shape your next shortlist</h1>
        <p>
          Start with a request-only shortlist, or explicitly choose anonymous saved
          personalization to rehydrate preferences and manage feedback on this browser.
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
      <PersistentRecommendationFlow>
        <RecommendationFlow />
      </PersistentRecommendationFlow>
    </div>
  );
}
