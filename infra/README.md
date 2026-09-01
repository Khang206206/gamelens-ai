# Infrastructure

The root `docker-compose.yml` starts PostgreSQL, the FastAPI service, and the
Next.js web development service. PostgreSQL and FastAPI have readiness checks;
the web check proves Next.js HTTP liveness at `/`, while catalog and
recommendation integration are covered by the isolated E2E stack. PostgreSQL
uses a named volume; ordinary `docker compose down` does not delete it.
Migrations and deterministic seeding remain explicit operations and are never
hidden in web startup.

The `model` profile adds a one-shot offline builder. It reads the migrated,
seeded database and writes a validated bundle at the configured
`MODEL_ARTIFACT_PATH`. The builder and API receive the same setting; the API
mounts `ml/artifacts` read-only and validates and loads but never builds or
mutates an artifact. Targets are immutable, so catalog/model changes use a new
path before the API is recreated; the old bundle remains available for rollback.
Loader-policy upgrades, including canonical CSR enforcement, also require
rotating `MODEL_ARTIFACT_PATH` and rebuilding and validating a new bundle. The
tracked `ml/artifacts/.gitkeep` ensures the bind-mount directory exists on a
fresh clone while generated members remain ignored.

All published development ports bind to `127.0.0.1`. The web service waits for
API readiness, bind-mounts `apps/web` for source edits, and isolates its Linux
dependencies and build cache in the `web_node_modules` and `web_next` named
volumes. The Node.js 24.18.0 image installs the locked dependency graph with
`npm ci`. Its startup initializer verifies that the source and image lockfiles
match, repairs and refreshes a stale dependency volume from the image without a
runtime registry request, clears the disposable Next.js cache after dependency
changes, and drops privileges to the `node` user before starting the server.
This prevents a named volume from silently preserving a vulnerable dependency
after an image rebuild.

Changing a published port requires changing its paired origin: `WEB_PORT` with
`CORS_ORIGINS`, and `API_PORT` with `NEXT_PUBLIC_API_URL`. The tracked
`.env.example` shows both pairs.

`infra/docker-compose.test.yml` is a separate Compose project for PostgreSQL
integration tests. Its database uses `tmpfs`, has no published host port, and is
disposable. The test service requires both an explicit pytest flag and a
test-only database-reset opt-in. It never mounts or resets the development
database volume.

`infra/docker-compose.e2e.yml` is a second isolated Compose project for browser
acceptance. It creates a fresh `tmpfs` PostgreSQL database, runs Alembic and the
deterministic seed through a one-shot setup service, then initializes a
disposable named artifact volume. A root-only init container changes that new
volume's owner and exits; the model builder itself runs as the non-root
`gamelens` user. The API receives the finished artifact read-only. Network-only
API and web services then support the exact Playwright 1.62.0 image pinned by
digest. `down --volumes --remove-orphans` removes the E2E containers, network,
and artifact volume; it never touches persistent development data. The verified
matrix contains 25 Playwright passes: 15 Chromium plus five smoke cases in each
of Firefox and WebKit.

The
[Stage 4 feedback-and-persistence plan](../docs/stage-4-feedback-persistence-plan.md)
extends this disposable stack with real anonymous-cookie, exact-origin, CSRF,
preference, feedback, event, and clear-data acceptance. The browser uses the
exact hostname `gamelens.test`: web origin `http://gamelens.test:3000` and API
URL `http://gamelens.test:8000`. The web service shares the API network
namespace so both ports resolve to the same endpoint. The API receives the exact
web Origin, `stage-4-v1` consent version, a test-only session secret, and
`ANONYMOUS_SESSION_COOKIE_SECURE=false`. This topology exercises a first-party
cookie over credentialed cross-origin requests across ports rather than a
fabricated auth header. The expanded Stage 4 Playwright matrix enumerates 38
cases: 28 Chromium plus five critical Firefox and five critical WebKit paths.
All 38 pass in 1.3 minutes without retry using two workers.

Stage 4 implements explicit dry-run-first retention and revocation commands.
`make retention-preview` runs `python -m app.commands.retention` without
mutation. Purge execution requires explicit event and expired-user cutoffs plus
the exact database-fingerprinted confirmation emitted by preview. Permanent bulk
session revocation uses the separately confirmed direct command
`python -m app.commands.anonymous_sessions`; it has no general Make execution
wrapper and selects the immutable creation cohort with `--created-before`. Key
retirement quiesces old-secret creation/re-consent, drains in-flight requests,
captures the database-time cutover while switching issuance to the new secret,
executes revocation until `remaining` is zero, and only then retires the old
secret. Neither operation runs from Compose startup, migration, seed, model
build, general tests, or ordinary teardown. Automated execution acceptance may
target only the guarded disposable database. The passing integration suite
verifies preview/purge counts, one-row batches, expiry/revoked cascades, cohort
stability across re-consent, and catalog preservation. Fixed session expiry
makes owned state purge-eligible rather than pretending an unscheduled command
deletes it at an exact instant.

The PostgreSQL integration Compose file supplies the test-only session and
fixture settings and runs migration/persistence suites against its guarded
`tmpfs` database. Readiness expects Alembic head `0010_stage_5_event_contract`.
The Phase 6 handoff passes 109 PostgreSQL integration tests, including
registry/count constraints, transactional authority and label invalidation,
component status, same-snapshot saved-request orchestration, populated event
migration, Stage 5 constraints, and response/event correlation. Companion gates
pass 365 API unit, 331 ML tests with one Windows symbolic-link capability skip,
and 86 web tests. Ruff lint/format passes across 172 Python files and generated
OpenAPI types have no drift. Five focused no-retry browser cases cover Phase 6
axe/responsive behavior. Disposable test containers, networks, and volumes are
removed after each run; the latest full inherited browser matrix remains the
verified Stage 4 38/38 run.

The API image is a non-root Python 3.12 development image built from a
transitive dependency lock. The `quality` Compose service bind-mounts the
working tree for current-source test, lint, and format commands. The Dockerfile
removes unused Debian `perl-base` only after all install steps. A rebuilt
no-cache `gamelens-ai-api:stage4-test` build with digest prefix `11b2f940731e`
passes runtime imports and `pip check` and retains all 49 PostgreSQL integration
passes. Removing `perl-base` resolves the earlier two critical and two high
findings. The comprehensive Docker Scout scan reports 0 critical, 0 high, 3
medium, 27 low, and 2 unspecified findings across 193 packages; its only-fixed
scan reports no actionable fixed advisory. Production container optimization and
deployment guidance still belong to Stage 7; the local API remains non-root and
loopback-only, and Stage 7 must choose and rescan a production-minimal base
rather than treating this development image as deployable. Kubernetes, Kafka,
and microservice infrastructure remain outside the current scope.

The development image uses configurable `APP_UID`/`APP_GID` build arguments,
defaulting to 1000, so a non-root model builder can write the artifact bind
mount on a typical Linux checkout. Set them to the checkout owner's numeric IDs
before building when they differ; Docker Desktop can keep the defaults.

The repository-root `.dockerignore` excludes local environment files, VCS
metadata, caches, test output, and untracked data from generic root-context
builds. The API Dockerfile has a stricter Dockerfile-specific deny-all
allowlist; the web images use `apps/web/.dockerignore` at their context root.

## Stage 5 Phase 0–6 artifact and saved-contract topology

The
[Stage 5 collaborative-and-hybrid plan](../docs/stage-5-collaborative-hybrid-ranking-plan.md)
has completed implementation Phases 0–6. Phases 0–4 add the contribution/
revision contract, default-off audit commands, guarded fixture artifact
workflow, pure scorer/materializers, and hybrid policy. Phase 5 adds the API
load-once optional component, PostgreSQL live build/contributor lineage,
transactional invalidation, one-row readiness, additive status, and internal
saved-request orchestration. Phase 6 adds the synchronized public hybrid-or-
fallback response, `stage-5-v1` event, generated client contract, and focused
browser evidence. The guarded two-artifact lifecycle E2E topology remains Phase
8 work.

The implemented guarded workflow audits the project-authored fixture, builds a
separate immutable collaborative bundle, validates it with the production
loader, and promotes only to an unused path. Live audit/build remains default-
off and unapproved. The normal API already receives
`COLLABORATIVE_ARTIFACT_PATH` and mounts the common artifact root read-only; it
loads a configured bundle only at construction. Fixture loading is accepted only
in the explicit test environment/gate, while a live artifact also requires
matching active database lineage. A collaborative bundle is never trained or
mutated by API/web startup, a request, migration, seed, broad test, or ordinary
teardown.

The disposable PostgreSQL project already proves fixture/live readiness,
authority and included-label invalidation, exact Stage 4 fallback, hybrid
decision projection, and `stage-5-v1` event truth against tmpfs PostgreSQL.
Phase 8 must extend the E2E project to build both artifacts, exercise public
hybrid/fallback and lifecycle browser paths, and remove only its tmpfs database
and disposable volumes. Development data and artifacts must remain untouched.
Fixture artifacts require both the test environment and explicit test-only flag;
ordinary development and production reject them.

Audit, fixture build, validation, aggregate inspection, and immutable promotion
have direct commands. Database invalidation is implemented transactionally, but
protected live build registration/promotion, operator invalidation, rollback,
retirement, and physical deletion remain future lifecycle work. Cleanup remains
preview-first with exact confirmation and cannot target an active artifact or a
broad directory. A production scheduler, registry service, or hot reload remains
Stage 7 work.
