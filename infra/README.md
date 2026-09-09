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
and artifact volume; it never touches persistent development data. The inherited
content-only matrix now has 38 passing browser cases; the earlier Stage 3 matrix
had 25.

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
`tmpfs` database. Readiness expects Alembic head `0011_stage_5_lifecycle_guard`.
The following Phase 6 counts are historical; the Phase 8 record below supersedes
them with the combined gate.
The Phase 6 handoff passes 109 PostgreSQL integration tests, including
registry/count constraints, transactional authority and label invalidation,
component status, same-snapshot saved-request orchestration, populated event
migration, Stage 5 constraints, and response/event correlation. Companion gates
pass 365 API unit, 331 ML tests with one Windows symbolic-link capability skip,
and 86 web tests. Ruff lint/format passes across 172 Python files and generated
OpenAPI types have no drift. Five focused no-retry browser cases cover Phase 6
axe/responsive behavior. Disposable test containers, networks, and volumes are
removed after each run; Phase 8 reran the inherited Stage 4 matrix with 38 passes.

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

## Stage 5 Phase 0–8 artifact and saved-contract topology

The
[Stage 5 collaborative-and-hybrid plan](../docs/stage-5-collaborative-hybrid-ranking-plan.md)
has completed implementation Phases 0–8, including the final docs comparison.
Phases 0–4 add the contribution/revision contract, default-off audit commands, guarded
fixture artifact workflow, pure scorer/materializers, and hybrid policy. Phase 5
adds the API load-once optional component, PostgreSQL live build/contributor lineage,
transactional invalidation, one-row readiness, additive status, and internal
saved-request orchestration. Phase 6 adds the synchronized public hybrid-or-
fallback response, `stage-5-v1` event, generated client contract, and focused
browser evidence. Phase 7 adds guarded registration/recovery, invalidation,
retirement, valid-only rollback checks, and previewed confirmed cleanup.

The implemented Phase 8 workflows audit the project-authored fixture, build a
separate immutable collaborative bundle, and independently audit/build/register
live artifacts from a guarded synthetic cohort in disposable PostgreSQL. Both
paths validate with the production loader and write only unused paths. Live
audit/build remains default-off and unapproved outside its explicit guarded test
profile. The normal API already receives
`COLLABORATIVE_ARTIFACT_PATH` and mounts the common artifact root read-only; it
loads a configured bundle only at construction. Fixture loading is accepted only
in the explicit test environment/gate, while a live artifact also requires
matching active database lineage. A collaborative bundle is never trained or
mutated by API/web startup, a request, migration, seed, broad test, or ordinary
teardown.

Run the complete slice 8G lifecycle acceptance from the repository root:

```sh
make test-e2e-lifecycle
# Direct equivalent when GNU Make is unavailable:
sh infra/run-e2e-lifecycle.sh
```

The runner serializes six fresh Compose projects: Chromium preference removal,
feedback removal, contribution withdrawal, and clear-data; Firefox clear-data;
and WebKit outdated-consent/re-consent. Every project creates its own tmpfs
PostgreSQL database, immutable artifact volume, private browser-state/evidence
volume, previous/current live builds, and exact-host API/web stack. Browser
mutations use existing public routes; contribution grant/re-grant and aggregate
database/event assertions stay in the guarded private control container. The API
is explicitly recreated to select an artifact and never hot-reloads one.

Each scenario proves ready hybrid before mutation and exact Stage 4
`privacy_invalid` fallback afterward, including after re-consent and API restart.
The operator scenario additionally proves valid rollback selection before
invalidation, invalid rollback/recovery rejection afterward, retirement of the
unconfigured previous build, mismatched-confirmation rejection, and exact cleanup
that preserves content and the configured current path. No response interception
is lifecycle evidence. Private browser state is removed before the project-local
`down --volumes --remove-orphans`; development data/artifacts are never mounted
or targeted.

Audit, fixture build, validation, aggregate inspection, and immutable promotion
have direct commands. Cleanup remains preview-first with exact confirmation and
cannot target an active artifact or a broad directory. Fixture artifacts still
require both the test environment and explicit test-only flag; development and
production reject them. Slice 8I records the completed documentation comparison.
A production scheduler, registry
service, or hot reload remains outside this test topology.

### Phase 8 workflow selection

All commands run from the repository root. GNU Make is optional; the direct
commands need POSIX `sh` (Git Bash on Windows) and Docker.

| Workflow | Make target | Direct command |
| --- | --- | --- |
| Content-only Stage 1–4 | `make test-web-e2e` | `sh infra/run-e2e-content.sh` |
| JSON fixture hybrid and fallback; two fresh fixture builds | `make test-e2e-fixture` | `sh infra/run-e2e-fixture.sh` |
| PostgreSQL-derived live build, registry, recovery and HTTP smoke | `make test-e2e-live-source` | `sh infra/run-e2e-live-source.sh` |
| Six serialized live lifecycle scenarios | `make test-e2e-lifecycle` | `sh infra/run-e2e-lifecycle.sh` |
| Complete combined gate | `make test-phase8` | `python infra/run-phase8.py` |

The fixture runner selects both `fixture` and `fallback` profiles. Live-source
and lifecycle runners select their own profiles with fixture access off. They
use `test-db`, `gamelens_e2e_test` and `/tmp/gamelens-e2e/artifact-set`, with
committed fixture/catalog inputs only and no host artifact or user-data mounts.
Fixture setup explicitly builds and validates content and collaborative bundles
before ready serving; failed validation prevents that pipeline from starting.
Fallback damage is confined to disposable copies and selected by API recreation.
Lifecycle setup explicitly links a browser session through private test control,
builds previous/current live bundles, validates registry readiness, then selects
the serving path. The browser never receives database credentials.

### Phase 8 combined isolation gate

From the repository root, run `python infra/run-phase8.py` (or
`make test-phase8`). This explicit, long-running gate requires Python 3.12+,
a POSIX `sh` (Git Bash on the verified Windows host), and a running Docker
Desktop Linux engine. It does not run during ordinary test collection.

The gate validates all Compose modes, runs API unit/ML/PostgreSQL checks,
Stage 1–4 browsers, web type/lint/format/unit/production-build/OpenAPI drift
checks, actual setup/validation/browser failure and signal teardown probes,
two clean fixture builds, and two complete live-source/lifecycle replays.
Web checks run in the built Playwright image against the disposable API.
The live-source probe compares artifact bytes and registered lineage around
ordinary startup/restart, migration, catalog seed and fast tests. Lifecycle
scenarios also compare snapshots around API/web restart and idempotent setup.
The fixture probe checks readiness and semantic identity after restart.
Because web shares the API network namespace for exact-host cookies, the restart
probe stops web, restarts API, and recreates web to join the new namespace before
testing web restart separately. Fixture traffic is also checked from the browser
container; a localhost-only health check cannot prove this network boundary.

Each run retains commands, exit codes, durations, runtime versions, safe image
identities, aggregate artifact sizes/hashes and replay comparisons under
`tmp/phase8-<timestamp>/`. Raw logs remain local and are scanned for credential
URLs and private identity fields; do not publish failed logs without review.
Browser traces are disabled; private browser state and any failure reports stay
inside disposable containers/volumes and are not exported by this gate.

All standalone E2E runners use `e2e-ownership.sh` to capture project-labelled
resource IDs before removal and verify no resources remain. Cleanup failure
is a failing exit, including during error/signal handling. The content-only
`make test-web-e2e` route now calls `sh infra/run-e2e-content.sh`, which gives
each run its own project. No runner prunes global resources or deletes host
artifacts. Artifact retirement/cleanup remains the separate guarded operator
workflow. Abrupt engine/host termination cannot execute shell traps; ownership
records identify the exact project for recovery after Docker returns.

The accepted run is owned by `35082f2`; see the
[Phase 8 ledger](../docs/stage-5-phase-8-docker-fixtures-plan.md) and
[machine-readable evidence](../docs/evidence/stage-5-phase-8h.json). It combines
a successful combined-run prefix with resumed live/lifecycle suffixes after host
interruptions, not one uninterrupted invocation. Both suffixes completed twice;
exact-project recovery removed interrupted resources.

These are functional synthetic-data checks on Linux containers. They do not
establish native Windows/macOS filesystem behavior, production contribution
authority, ranking quality, or the Phase 9/10 release gates.
