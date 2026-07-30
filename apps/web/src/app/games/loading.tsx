import { CatalogSkeleton } from "@/components/ui/loading";

export default function GamesLoading() {
  return (
    <div className="catalog-page shell">
      <div className="route-heading">
        <p className="eyebrow">Explore the archive</p>
        <h1>Game catalog</h1>
      </div>
      <CatalogSkeleton />
    </div>
  );
}
