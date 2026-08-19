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

**Status:** Complete (verified 2026-08-13)

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

The implementation branch now contains the `0003`-`0005` migration sequence
(expected head `0005_stage_4_event_contract`), explicit-consent anonymous
sessions, protected preference and temporal-feedback APIs, personalized event
logging, and feedback policy `gamelens-feedback-adjustment/1.0.0`. The web
opt-in/rehydration/clear-data flow, dry-run-first retention and guarded
revocation commands, and the exact-host E2E topology are also present.

Stage 4 is complete. The verified worktree passes 184 API tests with
89% diagnostic coverage, 52 ML tests with 83%, and 76 web tests with 67.15%
statement/71.4% line coverage. All 49 disposable-PostgreSQL integration tests
pass in 4.53 seconds, including populated legacy upgrade, Stage 4 constraints,
concurrent feedback serialization, event/delete correlation, cascades, and
retention; resources were torn down. Ruff passes across 112 Python files;
strict TypeScript, ESLint, Prettier, production build, generated OpenAPI drift,
production/full npm audits, and all three Compose definitions also pass. The
exact-host Docker browser matrix passes 38/38 in 1.3 minutes without retry with
two workers: 28 Chromium, 5 Firefox, and 5 WebKit. Real Origin/CSRF rejection,
stateless and active accessibility, persistence, isolation, invalid-cookie
recovery, and clear-data paths pass; actual expiry/re-consent mutation is
verified by the API/PostgreSQL suites. E2E containers, network, and volume were
removed, and the final Compose process list was empty. Section 23 of the
detailed plan records the completed acceptance evidence.
The API Dockerfile now removes unused Debian `perl-base` after all install
steps, resolving the earlier two critical and two high Perl findings. The
rebuilt no-cache `gamelens-ai-api:stage4-test` image with digest prefix
`11b2f940731e` passes runtime imports and `pip check`, keeps all 49 PostgreSQL
integration tests green, and its comprehensive Docker Scout scan reports 0
critical, 0 high, 3 medium, 27 low, and 2 unspecified findings across 193
packages. Its only-fixed scan reports no actionable fixed advisory; the
remaining base-image findings stay documented. Bulk key retirement uses the
immutable `--created-before` cohort: quiesce creation/re-consent, drain requests,
capture the database-time cutover while switching issuance to the new secret,
revoke until `remaining` is zero, then retire the old secret. The implementation
is published as commit `c96b6c2` in draft PR
[#5](https://github.com/Khang206206/gamelens-ai/pull/5).

## Stage 5 — Collaborative and hybrid ranking

**Status:** Engineering plan ready 2026-08-19; implementation has not started

Detailed execution plan:
[`stage-5-collaborative-hybrid-ranking-plan.md`](stage-5-collaborative-hybrid-ranking-plan.md)

Build one reviewable slice at a time:

1. Re-run the Stage 1–4 gates and freeze contribution-consent, label,
   provenance, cutoff, lifecycle, artifact, hybrid, API, and fallback
   contracts.
2. Add a read-only aggregate suitability audit plus a deterministic
   project-authored multi-user fixture; do not present either as quality
   evidence.
3. Extract one consent- and retention-aware as-of interaction snapshot in a
   database-time repeatable-read transaction, with canonical fingerprinting
   and no serialized identity.
4. Build and validate a separate sparse item-item cosine artifact with support
   thresholds, deterministic pruning, complete checksums, resource caps, and
   protected lifecycle lineage.
5. Add a pure collaborative scorer and a versioned hybrid policy whose base,
   feedback-affinity, collaborative, popularity, platform, and played
   components remain independently reconstructible.
6. Compare baseline candidates and component units on deterministic
   hand-calculated fixtures without reporting recommendation quality.
7. Preserve exact Stage 4 behavior for missing, insufficient, unsupported,
   invalid, stale, expired, retired, or privacy-invalid collaborative state.
8. Extend the saved personalized response, component status,
   recommendation-generation event, OpenAPI types, and conditional browser
   evidence while leaving the stateless endpoint unchanged.
9. Add explicit build/validate/invalidate/retire commands and disposable
   PostgreSQL/Docker lifecycle fixtures; no startup or request may train.
10. Pass ML, API, migration, PostgreSQL, web, browser, accessibility, privacy,
   Docker, dependency, OpenAPI, and complete Stage 1–4 regression gates.
11. Synchronize verified documentation and leave evaluation-ready artifact,
    component, cold-start, and limitation contracts for Stage 6.

Stage 5 is complete only when the data source and permission are explicit;
recommendation events are provably excluded as labels; deleted, withdrawn,
revoked, expired, or changed contributions cannot survive through a serveable
artifact; the sparse baseline and every hybrid contribution are deterministic
and reconstructible; every cold-start/failure path falls back exactly to Stage
4; and all earlier-stage gates pass.

The current 30-game seed and developer-generated sessions are functional
fixtures. They do not establish representative interaction data or model
quality. Precision/Recall/NDCG, coverage, novelty, diversity, tuning, and any
claim that one ranker is better remain Stage 6 work.

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
