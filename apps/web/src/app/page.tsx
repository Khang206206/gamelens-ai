import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Catalog lab",
};

const capabilityCards = [
  {
    index: "01",
    title: "Browse with context",
    copy: "Search by title, filter one taxonomy at a time, sort deterministically, and share the exact URL.",
  },
  {
    index: "02",
    title: "Inspect the details",
    copy: "Open every fictional title to see its studio, release, rating context, platforms, and tags.",
  },
  {
    index: "03",
    title: "Watch the system grow",
    copy: "The catalog foundation is implemented. Preference capture and project-owned recommendations begin in Stage 3.",
  },
];

export default function HomePage() {
  return (
    <>
      <section className="hero shell">
        <div className="hero__copy">
          <p className="eyebrow">
            <span aria-hidden="true">●</span> Stage 2 · Catalog foundation
          </p>
          <h1>
            Find your next world.
            <span>For now, start with the map.</span>
          </h1>
          <p className="hero__lede">
            GameLens AI is building a recommendation system in the open. Explore the
            working catalog today—without fabricated matches, mystery scores, or pretend
            personalization.
          </p>
          <div className="hero__actions">
            <Link className="button button--primary" href="/games">
              Explore the catalog <span aria-hidden="true">↗</span>
            </Link>
            <a className="text-link" href="#how-it-works">
              See what works now
            </a>
          </div>
        </div>
        <div className="hero-console" aria-label="Current product capability summary">
          <div className="hero-console__top">
            <span>CATALOG / SIGNALS</span>
            <span>02—07</span>
          </div>
          <div className="hero-console__orb" aria-hidden="true">
            <span className="hero-console__axis hero-console__axis--one" />
            <span className="hero-console__axis hero-console__axis--two" />
            <span className="hero-console__core">GL</span>
          </div>
          <dl className="hero-console__metrics">
            <div>
              <dt>Seed games</dt>
              <dd>30</dd>
            </div>
            <div>
              <dt>Seed taxonomy terms</dt>
              <dd>36</dd>
            </div>
            <div>
              <dt>Stage 2 mode</dt>
              <dd>Catalog only</dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="signal-strip" aria-label="Product status">
        <div className="shell signal-strip__inner">
          <span>Implemented</span>
          <strong>Catalog search, filters, sorting, pagination, and game details</strong>
          <span className="signal-strip__future">Recommendations · Stage 3</span>
        </div>
      </section>

      <section className="capabilities shell" id="how-it-works">
        <div className="section-heading">
          <p className="eyebrow">What you can do</p>
          <h2>A real foundation, before the ranking.</h2>
          <p>
            Each current interaction maps to an implemented API contract. Later
            intelligence will build on this observable base.
          </p>
        </div>
        <div className="capability-grid">
          {capabilityCards.map((card) => (
            <article className="capability-card" key={card.index}>
              <span>{card.index}</span>
              <h3>{card.title}</h3>
              <p>{card.copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="manifesto shell">
        <p className="eyebrow">The product promise</p>
        <blockquote>
          “Useful recommendations should be explainable, testable, and earned—not painted
          onto a mockup.”
        </blockquote>
        <div className="manifesto__aside">
          <span>Current mode</span>
          <strong>Catalog exploration</strong>
          <p>Anonymous · deterministic · no tracking</p>
        </div>
      </section>
    </>
  );
}
