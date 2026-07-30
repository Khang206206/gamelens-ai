import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link className="brand" href="/" aria-label="GameLens AI home">
          <span className="brand__mark" aria-hidden="true">
            GL
          </span>
          <span>
            <strong>GameLens</strong>
            <small>AI catalog lab</small>
          </span>
        </Link>
        <nav aria-label="Primary navigation">
          <ul className="nav-list">
            <li>
              <Link href="/">Overview</Link>
            </li>
            <li>
              <Link href="/games">Game catalog</Link>
            </li>
          </ul>
        </nav>
        <span className="status-chip">
          <span aria-hidden="true" />
          Stage 2 catalog
        </span>
      </div>
    </header>
  );
}
