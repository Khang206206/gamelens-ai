import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <div>
          <p className="site-footer__brand">GameLens AI</p>
          <p>A transparent recommendation-system portfolio, built one stage at a time.</p>
        </div>
        <div className="site-footer__links">
          <Link href="/games">Browse catalog</Link>
          <a href="#main-content">Back to main content</a>
        </div>
        <p className="site-footer__stage">Stage 2 · Catalog foundation</p>
      </div>
    </footer>
  );
}
