import type { Metadata } from "next";
import { Suspense } from "react";

import { CatalogSkeleton } from "@/components/ui/loading";
import { CatalogBrowser } from "@/features/catalog/catalog-browser";

export const metadata: Metadata = {
  title: "Game catalog",
  description:
    "Search, filter, sort, and browse the current GameLens AI development catalog.",
};

export default function GamesPage() {
  return (
    <div className="catalog-page shell">
      <header className="route-heading">
        <p className="eyebrow">Explore the archive</p>
        <h1>Game catalog</h1>
        <p>
          Browse the deterministic development catalog with transparent synthetic signals
          and exact links you can reload or share.
        </p>
      </header>
      <Suspense fallback={<CatalogSkeleton />}>
        <CatalogBrowser />
      </Suspense>
    </div>
  );
}
