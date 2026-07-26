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

**Status:** Ready for implementation; application code has not started

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

## Stage 3 — Content recommendation MVP

**Status:** Planned

Create deterministic preprocessing and TF-IDF artifacts, a replaceable
recommendation service, onboarding, structured explanations, recommendation
API contracts, and ranking tests.

## Stage 4 — Feedback and persistence

**Status:** Planned

Persist interactions and preferences, adjust results from feedback, exclude
disliked games, and log model-versioned recommendation events.

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
