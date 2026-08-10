# Roadmap

Each stage has an acceptance gate. Later work should not make earlier runnable
components less reliable.

## Stage 0 — Repository foundation

**Status:** Complete

Deliverables:

- Git and text-format hygiene.
- Purposeful monorepo boundaries.
- Root README and design documents.
- Example environment configuration.
- Valid local PostgreSQL Compose definition.
- Root commands limited to existing functionality.

Acceptance gate:

- `git diff --check` succeeds.
- `.env` is ignored while `.env.example` is tracked.
- `docker compose config --quiet` succeeds.
- PostgreSQL starts and becomes healthy on a Docker-enabled machine.
- Setup, architecture, limitations, and next work are understandable.

## Stage 1 — Backend and database foundation

**Status:** Complete

Detailed execution plan:
[`stage-1-backend-database-plan.md`](stage-1-backend-database-plan.md)

Build one vertical slice at a time:

1. Python project with pinned direct dependencies and a transitive container lock.
2. FastAPI settings, logging, and error handling.
3. PostgreSQL session management and Alembic.
4. Initial relational models and migration.
5. Deterministic seed dataset with at least 25 varied games.
6. Health, catalog, detail, and taxonomy endpoints.
7. pytest coverage and API Docker image.

The stage is complete when migrations, seed, server, tests, linting, and
Compose startup all succeed.

Acceptance was re-audited on 2026-07-26 with 84 fast tests, 28
disposable-PostgreSQL integration tests, 92% diagnostic application coverage,
a clean dependency vulnerability scan, a healthy Compose stack, and the
complete HTTP smoke matrix.

## Stage 2 — Frontend foundation

**Status:** Complete (verified 2026-07-30)

Detailed execution plan:
[`stage-2-frontend-foundation-plan.md`](stage-2-frontend-foundation-plan.md)

Build one reviewable slice at a time:

1. Verify the Stage 1 contract and select a compatible pinned Node/Next.js
   toolchain.
2. Create the strict TypeScript, App Router, Tailwind, and test skeleton.
3. Generate types from OpenAPI and establish one project-owned API client.
4. Build accessible design tokens, shared UI, navigation, and responsive shell.
5. Add the truthful landing page.
6. Add URL-backed catalog title search, single-value filters, sorting, and
   pagination.
7. Add numeric-ID game details and explicit nullable-field fallbacks.
8. Harden loading, empty, partial-error, not-found, unavailable, responsive,
   and keyboard states.
9. Add the web Docker workflow, browser tests, accessibility checks, and
   documentation.

The stage is complete only when clean install, type, lint, format, test, build,
OpenAPI-drift, accessibility, real-browser, and full-stack Docker gates pass.
No Stage 2 screen may imply that recommendations are active while the model
status remains `not_configured`.

Acceptance was detail-audited with a clean `npm ci`, 40 fast tests, a
successful production build, current OpenAPI-generated contracts, and 21
Docker-first Playwright scenarios across Chromium, Firefox, and WebKit. The
browser suite passed serious/critical axe checks, keyboard-reachable mobile
navigation, recovery states, URL races, and responsive catalog/detail layouts.
The repaired development stack verified the locked Sharp and PostCSS versions
inside its existing dependency volume. PostgreSQL, API, and web services became
healthy, and the Stage 1 regression suite remained green with 84 fast tests and
28 disposable-PostgreSQL integration tests. See the completion record in the
detailed plan for exact versions, commands, and known limitations.

## Stage 3 — Content recommendation MVP

**Status:** Complete (verified 2026-08-07)

Detailed execution plan:
[`stage-3-content-recommendation-mvp-plan.md`](stage-3-content-recommendation-mvp-plan.md)

Build one reviewable slice at a time:

1. Re-run the Stage 1 and Stage 2 gates, audit the deterministic catalog, and
   finalize request, response, scoring, artifact, and user-state contracts.
2. Create the pinned Python 3.12 ML workspace and shared package boundary.
3. Extract and fingerprint a canonical stable-slug catalog snapshot.
4. Implement and independently test the versioned popularity baseline.
5. Build deterministic TF-IDF features and a checksum-covered sparse artifact.
6. Add bounded online ranking, stable tie-breaking, component scores, and
   structured deterministic explanations.
7. Activate an injectable API service with honest unconfigured, unavailable,
   and ready states plus explicit stale-artifact and `catalog_invalid` reasons.
8. Add the typed recommendation `POST` contract, CORS coverage, OpenAPI types,
   and project-owned browser client support.
9. Add accessible anonymous onboarding and explained recommendation results.
10. Add explicit Docker artifact lifecycle, disposable full-stack browser
    fixtures, and complete regression gates.
11. Synchronize documentation and record the Stage 4 persistence handoff.

Stage 3 is complete only when the same canonical data and configuration produce
the same semantic artifact and ordered rankings; missing, corrupt,
incompatible, or stale artifacts and non-canonical catalog inputs fail clearly;
the real API and web flow pass contract, browser, accessibility, and Docker
gates; and all Stage 1 and Stage 2 regressions remain green.

Onboarding selections remain request-scoped in Stage 3. Persistent preferences,
feedback writes and adjustments, disliked-game exclusion, and
model-versioned recommendation-event logging remain Stage 4 work. The
30-game synthetic catalog supports functional and reproducibility acceptance,
not recommendation-quality claims.

Acceptance passed with 25 ML tests, 104 fast API tests, 29 disposable-PostgreSQL
integration tests, 45 frontend tests, and 25 Docker-first Playwright passes.
Ruff, strict TypeScript, ESLint, Prettier, production build, Compose validation,
OpenAPI generation, accessibility, responsive, CORS, artifact integrity, and
dependency-integrity checks passed. The disposable full-stack path migrated and
seeded PostgreSQL, initialized artifact-volume ownership in a root-only setup
container, built the artifact as a non-root user, loaded it read-only in the
API, returned real explained recommendations, and removed only E2E resources.
The completion record documents diagnostic size/timing, coverage, licenses,
and the unfixed Debian base-image advisories retained for Stage 7.

## Stage 4 — Feedback and persistence

**Status:** Engineering plan ready; implementation has not started

Detailed execution plan:
[`stage-4-feedback-persistence-plan.md`](stage-4-feedback-persistence-plan.md)

Build one reviewable slice at a time:

1. Re-run the Stage 1–3 gates and freeze consent, identity, preference,
   feedback, ranking, event, retention, deletion, and privacy contracts.
2. Add data-preserving migrations for consent-aware token digests, temporal
   interaction state, and model/data/policy-versioned recommendation events.
3. Add explicit-consent anonymous sessions with host-only HttpOnly cookies,
   fixed expiry, credentialed CORS, exact-origin checks, and CSRF protection.
4. Add bounded atomic preference replacement and canonical like/dislike,
   played, wishlist, and rating state contracts.
5. Add a deterministic feedback policy that hard-excludes dislikes, exposes
   bounded positive affinity, applies a played adjustment, and leaves wishlist
   neutral in version 1.
6. Add a separate saved-context recommendation endpoint whose success commits
   exactly one bounded event while the Stage 3 stateless endpoint stays
   cookie-agnostic and read-only.
7. Add accessible opt-in, rehydration, saved-preference, feedback, expiry, and
   clear-data behavior while retaining the complete opt-out flow.
8. Add explicit dry-run-first retention operations with bounded batches and no
   startup or scheduled side effect.
9. Extend the disposable full stack with real same-site cookie, origin, CSRF,
   persistence, event, deletion, and retention fixtures.
10. Pass migration, concurrency, ML, API, web, browser, accessibility, privacy,
    security, Docker, OpenAPI, and complete Stage 1–3 regression gates.
11. Synchronize verified documentation and record the exact Stage 5
    interaction-data handoff.

Stage 4 is complete only when no identity exists before current-version
consent; raw credentials never leave the HttpOnly-cookie boundary; preference
and feedback state is bounded, atomic, idempotent, isolated, and deletable;
dislikes, affinity, and played adjustment are deterministic and observable;
every successful personalized generation has one matching bounded event; the
opt-out endpoint remains read-only; and all earlier-stage regressions pass.

The 30-game synthetic catalog and local feedback prove lifecycle,
reproducibility, integration, and explanation behavior only. Collaborative and
hybrid ranking remain Stage 5 work, while comparative ranking evaluation and
quality claims remain Stage 6 work.

## Stage 5 — Collaborative and hybrid ranking

**Status:** Planned

Introduce an interaction dataset and collaborative baseline, compare it with
existing baselines, and combine independently observable component scores.

## Stage 6 — Evaluation and reporting

**Status:** Planned

Run reproducible ranking evaluation with saved configuration, machine-readable
metrics, and an evidence-based Markdown experiment report.

## Stage 7 — Production readiness

**Status:** Planned

Add CI, production Dockerfiles, deployment documentation, logging and
monitoring hooks, security review, and demo assets.

## Stage 8 — Selected advanced capability

**Status:** Planned

Choose only one or two justified capabilities after evaluation is credible,
such as diversity reranking, semantic embeddings, natural-language preference
input, an evidence-grounded LLM explanation layer, or authentication.
