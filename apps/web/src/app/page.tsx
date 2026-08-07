import type { Metadata } from "next";
import type { Route } from "next";
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
    copy: "Build an anonymous request from games and taxonomy preferences, then inspect project-owned ranking evidence.",
  },
];

export default function HomePage() {
  return (
    <>
      <section className="hero shell">
        <div className="hero__copy">
          <p className="eyebrow">
            <span aria-hidden="true">●</span> Stage 3 · Content recommendations
          </p>
          <h1>
            Find your next world.
            <span>For now, start with the map.</span>
          </h1>
          <p className="hero__lede">
            GameLens AI now turns request-scoped choices into deterministic, explained
            content recommendations—without saved identity, mystery scores, or pretend
            feedback.
          </p>
          <div className="hero__actions">
            <Link className="button button--primary" href="/games">
              Explore the catalog <span aria-hidden="true">↗</span>
            </Link>
            <Link className="button button--secondary" href={"/recommendations" as Route}>
              Build a shortlist <span aria-hidden="true">↗</span>
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
              <dt>Stage 3 model</dt>
              <dd>Content TF-IDF</dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="signal-strip" aria-label="Product status">
        <div className="shell signal-strip__inner">
          <span>Implemented</span>
          <strong>Catalog plus anonymous artifact-backed content ranking</strong>
          <span className="signal-strip__future">Feedback persistence · Stage 4</span>
        </div>
      </section>

      <section className="capabilities shell" id="how-it-works">
        <div className="section-heading">
          <p className="eyebrow">What you can do</p>
          <h2>Observable signals, through the ranking.</h2>
          <p>
            Each recommendation maps to an implemented API contract, fixed component
            weights, and structured evidence you can inspect.
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
          <strong>Request-scoped recommendations</strong>
          <p>Anonymous · deterministic · no persistence</p>
        </div>
      </section>
    </>
  );
}
