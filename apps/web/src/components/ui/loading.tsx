export function CatalogSkeleton() {
  return (
    <div className="game-grid" aria-label="Loading catalog" aria-busy="true">
      {Array.from({ length: 8 }, (_, index) => (
        <div className="game-card game-card--skeleton" key={index} aria-hidden="true">
          <div className="skeleton skeleton--cover" />
          <div className="skeleton-stack">
            <div className="skeleton skeleton--short" />
            <div className="skeleton" />
            <div className="skeleton skeleton--medium" />
          </div>
        </div>
      ))}
      <span className="sr-only">Loading games…</span>
    </div>
  );
}

export function DetailSkeleton() {
  return (
    <div className="detail-layout" aria-label="Loading game details" aria-busy="true">
      <div className="skeleton skeleton--detail-cover" aria-hidden="true" />
      <div className="detail-skeleton-copy" aria-hidden="true">
        <div className="skeleton skeleton--short" />
        <div className="skeleton skeleton--heading" />
        <div className="skeleton" />
        <div className="skeleton" />
        <div className="skeleton skeleton--medium" />
      </div>
      <span className="sr-only">Loading game details…</span>
    </div>
  );
}
