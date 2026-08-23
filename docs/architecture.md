# Architecture

## Goals

GameLens AI uses a modular monorepo so the portfolio demonstrates product,
backend, data, and ML engineering without introducing unnecessary distributed
systems. Each major stage must leave the repository runnable and documented.

The initial architecture favors explicit boundaries, deterministic local data,
replaceable recommendation algorithms, and deployment-neutral containers.

## System context

```mermaid
flowchart TB
    User["Anonymous user (current)"]
    AuthUser["Authenticated user (future)"]:::future
    Web["Next.js web application"]
    API["FastAPI application"]
    DB[("PostgreSQL")]
    Seed["Deterministic seed data"]
    Recommender["Immutable recommendation service"]
    Artifacts["Versioned model artifact"]
    Builder["Explicit offline model builder"]
    Evaluation["Offline evaluation (Stage 6)"]:::future
    Sources["External adapters (future)"]:::future

    User --> Web
    Web -->|"JSON over HTTP"| API
    API --> DB
    Seed --> DB
    AuthUser -.-> Web
    API --> Recommender
    Recommender --> Artifacts
    DB --> Builder
    Builder --> Artifacts
    Sources -.-> DB
    Sources -.-> Evaluation
    Artifacts -.-> Evaluation

    classDef future stroke-dasharray: 6 4
```

### Implemented Stage 3 activation

Stage 3 activates the recommendation boundary through an explicit
offline-to-online artifact flow:

```mermaid
flowchart LR
    DB[("Migrated and seeded PostgreSQL")]
    Snapshot["Canonical read-only catalog snapshot"]
    Builder["Offline popularity and TF-IDF builder"]
    Artifact["Validated versioned sparse artifact"]
    Loader["API lifecycle loader"]
    Ranker["Immutable online ranker"]
    API["FastAPI recommendation use case"]
    Web["Anonymous onboarding and results"]

    DB --> Snapshot
    Snapshot --> Builder
    Builder --> Artifact
    Artifact --> Loader
    Loader --> Ranker
    Web -->|"Bounded preference context"| API
    API -->|"Read one consistent catalog snapshot"| DB
    API --> Ranker
    Ranker -->|"Ranked items and structured evidence"| API
    API --> Web
```

The browser does not import or execute ranking code. Artifact building remains
an explicit offline command, while API startup only validates and loads the
intrinsic contents of an already built bundle. Model-status and recommendation
requests compare that immutable artifact with one transactionally consistent
current-catalog snapshot before reporting `ready` or ranking. Missing, corrupt,
incompatible, or catalog-stale artifacts and catalogs that cannot be
canonicalized leave catalog behavior available and recommendation capability
unavailable. The latter is reported as `catalog_invalid`. See the
[Stage 3 engineering plan](stage-3-content-recommendation-mvp-plan.md).

### Stage 4 activation (verified 2026-08-13)

The
[Stage 4 feedback-and-persistence plan](stage-4-feedback-persistence-plan.md)
implements a separate explicit-consent path without changing the Stage 3 stateless
route:

```mermaid
flowchart LR
    User["Anonymous user"]
    Consent["Explicit current-version consent"]
    Cookie["Host-only HttpOnly session cookie"]
    API["Protected /api/v1/me contracts"]
    State[("Consent, preferences, feedback")]
    Base["Immutable Stage 3 artifact"]
    Policy["Versioned feedback policy"]
    Event[("Bounded recommendation event")]

    User --> Consent
    Consent --> Cookie
    Cookie --> API
    API --> State
    API --> Base
    State --> Policy
    Base --> Policy
    Policy --> API
    API --> Event
    API --> User
```

Only the session-creation contract may create identity. The raw token remains
in the host-only HttpOnly browser cookie; PostgreSQL stores a domain-separated
HMAC-SHA-256 digest plus explicit consent, expiry, and revocation state.
Protected unsafe requests use exact-origin, credentialed CORS, and CSRF checks.
Saved preferences and temporal feedback remain user-scoped relational state
and never enter the artifact.

The stateless endpoint retains one repeatable-read read-only snapshot. The
personalized endpoint owns one bounded repeatable-read read-write
transaction from identity/context resolution through ranking and insertion of
the exact matching model/data/policy-versioned event. Deletion and explicit
retention remove user-owned state through relational cascades. Fast tests cover
the application boundaries, and 49 disposable-PostgreSQL integration tests
verify the Stage 4 schema, populated legacy upgrade, transaction/concurrency,
event/delete correlation, cascades, and retention behavior.

### Planned Stage 5 activation (not implemented)

The
[Stage 5 collaborative-and-hybrid plan](stage-5-collaborative-hybrid-ranking-plan.md)
proposes a second offline-to-online path. Every node below with a dashed border
is future behavior; the current runtime still ends at the verified Stage 4
feedback policy.


The implemented read-only UCSD Steam preflight is a separate offline source
identity, preparation, and aggregate-support check. It is not connected to the
future consent-qualified live-data activation path below.

```mermaid
flowchart LR
    State[("Consented preferences and interactions")]:::future
    Audit["Consent-qualified live-data suitability audit"]:::future
    Snapshot["Cutoff-bound eligible snapshot"]:::future
    Builder["Sparse item-item cosine builder"]:::future
    CF["Identity-free collaborative artifact"]:::future
    Lineage[("Build and contributor lineage")]:::future
    Content["Existing content artifact"]
    Feedback["Existing feedback components"]
    Hybrid["Versioned hybrid policy"]:::future
    API["Saved recommendation use case"]
    Event[("Versioned generation event")]

    State --> Audit
    Audit --> Snapshot
    Snapshot --> Builder
    Builder --> CF
    Builder --> Lineage
    Content --> Hybrid
    Feedback --> Hybrid
    CF --> Hybrid
    Lineage --> Hybrid
    Hybrid --> API
    API --> Event

    classDef future stroke-dasharray: 6 4
```

The proposed builder reads eligible state in one database-time,
repeatable-read transaction, writes a separate immutable artifact, and keeps
user identity out of that artifact. PostgreSQL lineage and a dataset revision
would invalidate collaborative serving after relevant consent, feedback,
expiry, revocation, or deletion changes. The API would then continue through
the exact Stage 4 fallback until an explicit rebuild. No request, startup, or
ordinary migration trains a model.

## Repository boundaries

### Web

`apps/web` owns pages, presentation components, browser state, and a typed API
client. It does not connect directly to PostgreSQL, embed secrets, or implement
recommendation ranking.

Stages 2 and 3 implement Next.js App Router routes for `/`, `/games`,
`/games/[gameId]`, and `/recommendations`. The root layout and landing page are statically rendered;
focused catalog and detail client components own browser-side API requests and
interactive state. Catalog request state is normalized into URL search
parameters so reload and browser history restore the same request without a
global store. Recommendation selections deliberately remain local to one
select-review-results flow and are discarded on restart or navigation.

Stage 4 adds an opt-in durable branch of `/recommendations` with consent,
rehydration, feedback, expiry, and clear-data states. The opt-out branch
retains the request-only behavior. Credentials remain in an HttpOnly cookie;
profile data is not copied into URLs or Web Storage, and the browser renders
rather than calculates ranks. Component and client tests pass. The
full-Chromium and critical Firefox/WebKit acceptance matrix passes 38/38 in 1.3
minutes without retry against the exact-host `gamelens.test` topology.

All browser requests pass through one project-owned client configured by the
validated `NEXT_PUBLIC_API_URL`. Its compile-time contracts are generated from
the live FastAPI OpenAPI document and checked for drift. The runtime boundary
also verifies JSON responses and the standard API error envelope. There is no
backend-for-frontend, internal API URL, direct database access, or browser-side
ranking logic. See the completed
[Stage 2 frontend engineering plan](stage-2-frontend-foundation-plan.md).

### API

`apps/api` owns HTTP contracts, validation, orchestration, and persistence.
Online inference activates only after an explicit offline build produces an
artifact whose integrity, compatibility, and current-catalog fingerprint pass
validation. Absent configuration remains `not_configured`; a configured load
failure, catalog mismatch, or catalog canonicalization failure is
`unavailable`; the last condition uses `catalog_invalid`. Route functions
remain thin:

```text
route -> service -> repository/model interface -> database or artifact
```

Database sessions are dependency-injected from the app-local engine, which is
also used by readiness checks and disposed at shutdown. Database models are
not returned directly as API responses. Recommendation status and execution
read one eager `REPEATABLE READ, READ ONLY` snapshot and compare its canonical
fingerprint with the immutable startup artifact before returning ready data.

Stage 4 implements protected `/api/v1/me`, `/api/v1/me/preferences`,
`/api/v1/me/feedback`, `/api/v1/me/games/{game_id}/feedback`, and
`/api/v1/me/recommendations` contracts. Application services own identity,
validation, locking, transaction, persistence, and event semantics. This
read-write path does not replace the stateless read-only path. Routes remain
thin and repositories remain explicitly user-scoped.

### Database

PostgreSQL stores games, taxonomy, users, preferences, interactions, and
recommendation events. Schema changes use Alembic migrations. Flexible JSON
is limited to request context and compact result summaries where a relational
shape would not be stable.

Stage 4 migrations replace plaintext anonymous-key semantics with a consented,
expiring token digest, add temporal active/superseded interaction rules, and
extend recommendation events with data and personalization-policy identity.
The expected Alembic head is `0005_stage_4_event_contract`. Legacy placeholder
rows are deterministically converted to unique revoked, inaccessible
identities and are not treated as consented sessions. The populated `0002` to
head upgrade and the documented populated downgrade/re-upgrade gate pass in
the verified Stage 4 suite.

### Machine learning

`ml` owns preprocessing, the popularity baseline, TF-IDF feature construction,
pure ranking logic, reproducibility metadata, artifact generation, and later
offline evaluation. The implemented matrix is float64 CSR keyed by stable game
slug. Transparent JSON/NPY members have manifest sizes and checksums and are
loaded with pickle disabled under explicit resource caps. The loader rejects
non-canonical CSR indices, negative feature weights, IDF weights below one,
and feature rows that are not L2-normalized. Loader-policy changes require
operators to rotate the configured path and rebuild and validate the immutable
artifact before an API restart. Training is never triggered by a request or
ordinary application startup. The API loads one known validated artifact version and exposes an
honest unconfigured, unavailable, or ready status.

The implemented `gamelens-feedback-adjustment/1.0.0` policy consumes bounded
saved/interaction context as immutable per-request input, uses existing
artifact vectors, and exposes its own identity and contribution. User identity
and mutable state never enter an artifact or the application-lifecycle ranker
singleton. The Stage 3 model and artifact identity remain unchanged.

Stage 5 plans a separate sparse item-item artifact and pure collaborative
scorer because interaction data has different consent, deletion, freshness,
and rebuild semantics from catalog content. The ML package would receive only
canonical ephemeral cohort rows during build and stable-slug query context at
serving. The resulting bundle would contain aggregate item neighborhoods,
support, fingerprints, configuration, and checksums—not user rows, IDs, token
digests, or recommendation events. Component readiness and hybrid math would
remain independently testable; formal ranking evaluation stays in Stage 6.

### External data

Future metadata sources sit behind adapters. The local MVP must start from a
deterministic seed dataset and remain usable without network access or API
keys.

## Runtime environments

### Local development

Docker Compose provides PostgreSQL, the FastAPI service, and the Next.js
development server while preserving direct host workflows for both
applications. Schema migration and deterministic seeding remain explicit
commands; starting the web service never changes database state.

The web service bind-mounts `apps/web` for source edits and uses separate named
volumes for Linux `node_modules` and `.next` data. It publishes only to
`127.0.0.1` and waits for API readiness. Startup compares the bind-mounted and
image lockfiles, refreshes stale dependencies from the built image, repairs
volume ownership, clears invalidated Next.js cache data, and then runs the
development server as the non-root `node` user. A separate E2E Compose project
uses a `tmpfs` PostgreSQL database, applies migrations and seed data explicitly,
and runs the locked Playwright suite without touching the persistent
development database volume. Stage 3 adds a disposable named artifact volume:
a short root init changes only that new volume's ownership, the builder runs
non-root, and the API mounts the result read-only. E2E teardown removes this
isolated volume.

### Production direction

The intended deployment is a Node-compatible web host, a containerized API,
and managed PostgreSQL. The repository must not depend on a specific vendor.
The current social metadata base is the local development origin; Stage 7 must
add and validate the public site origin before deployment.

## Cross-cutting decisions

- Configuration comes from environment variables.
- Timestamps are stored in UTC.
- CORS uses an explicit configured allowlist.
- Secrets and local datasets are excluded from version control.
- Structured logging and centralized error handling begin in Stage 1.
- Model names, versions, and component scores remain observable.
- Account authentication remains deferred. Stage 4 implements only a
  possession-based anonymous session credential, and user identifiers are not
  embedded into recommendation algorithms.

## Current state

Stages 1 through 4 implement the API, database, web, ML, consent, and saved
personalization boundaries. Catalog routes depend on services, repositories,
and injected SQLAlchemy sessions; PostgreSQL is the runtime source of truth.
Readiness requires connectivity and the expected Alembic schema head. The
responsive web application supports catalog search, filters, sorting,
pagination, game details, request-only recommendations, and opt-in saved
personalization with explicit loading, empty, unavailable, not-found, consent,
expiry, and deletion states.

The recommendation boundary now exposes honest `ready`, `not_configured`, and
`unavailable` states plus the bounded `POST /api/v1/recommendations` vertical
slice. The offline builder, checksum-validated artifact, immutable ranker,
generated browser contract, and anonymous explained-result experience are
active. Account authentication, collaborative/hybrid ranking, formal
evaluation, and production deployment remain later components. The Stage 5
engineering plan is ready, but its interaction snapshot, collaborative
artifact, hybrid policy, lifecycle lineage, API fields, and UI evidence are not
implemented.

Stage 4 is complete and verified. Its consented identity, durable
preferences, temporal feedback writes, deterministic feedback adjustment,
personalized recommendation-event logging, retention/revocation operations,
and persistent browser components are present on the implementation branch.
The E2E topology uses the exact hostname `gamelens.test` for the web origin on
port 3000 and API on port 8000. The web container shares the API network
namespace, preserving a first-party cookie while exercising credentialed
cross-origin requests across ports. The disposable PostgreSQL suite passes 49
tests; companion fast gates pass 184 API, 52 ML, and 76 web tests. The Docker
browser gate passes 38/38 with 28 Chromium, 5 Firefox, and 5 WebKit cases,
including a real WebKit consent `201`, active axe, and real Origin/CSRF `403`
paths. Teardown removes the isolated containers, network, and volume and leaves
an empty Compose process list. The API Dockerfile removes unused Debian
`perl-base` after all install steps, resolving
the earlier two critical and two high findings. The comprehensive scan of
rebuilt no-cache `gamelens-ai-api:stage4-test` digest prefix `11b2f940731e`
reports 0 critical, 0 high, 3 medium, 27 low, and 2 unspecified findings across
193 packages; its only-fixed scan reports no actionable fixed advisory.
Runtime imports, `pip check`, and all 49 PostgreSQL passes remain green. Final
generated-output, credential, trace, coverage, and unrelated-diff review is
clean.
