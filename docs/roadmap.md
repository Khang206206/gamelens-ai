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
- `docker compose config` succeeds.
- PostgreSQL starts and becomes healthy on a Docker-enabled machine.
- Setup, architecture, limitations, and next work are understandable.

## Stage 1 — Backend and database foundation

**Status:** Planned

Detailed execution plan:
[`stage-1-backend-database-plan.md`](stage-1-backend-database-plan.md)

Build one vertical slice at a time:

1. Python project and locked dependencies.
2. FastAPI settings, logging, and error handling.
3. PostgreSQL session management and Alembic.
4. Initial relational models and migration.
5. Deterministic seed dataset with at least 25 varied games.
6. Health, catalog, detail, and taxonomy endpoints.
7. pytest coverage and API Docker image.

The stage is complete when migrations, seed, server, tests, linting, and
Compose startup all succeed.

## Stage 2 — Frontend foundation

Create the Next.js application after catalog response schemas are stable.
Implement the responsive shell, landing page, catalog, details, typed API
client, and loading, empty, and error states.

## Stage 3 — Content recommendation MVP

Create deterministic preprocessing and TF-IDF artifacts, a replaceable
recommendation service, onboarding, structured explanations, recommendation
API contracts, and ranking tests.

## Stage 4 — Feedback and persistence

Persist interactions and preferences, adjust results from feedback, exclude
disliked games, and log model-versioned recommendation events.

## Stage 5 — Collaborative and hybrid ranking

Introduce an interaction dataset and collaborative baseline, compare it with
existing baselines, and combine independently observable component scores.

## Stage 6 — Evaluation and reporting

Run reproducible ranking evaluation with saved configuration, machine-readable
metrics, and an evidence-based Markdown experiment report.

## Stage 7 — Production readiness

Add CI, production Dockerfiles, deployment documentation, logging and
monitoring hooks, security review, and demo assets.

## Stage 8 — Selected advanced capability

Choose only one or two justified capabilities after evaluation is credible,
such as diversity reranking, semantic embeddings, natural-language preference
input, an evidence-grounded LLM explanation layer, or authentication.
