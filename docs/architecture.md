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
    Recommender["Recommendation service (future)"]:::future
    Artifacts["Versioned model artifacts (future)"]:::future
    Pipeline["Offline training and evaluation (future)"]:::future
    Sources["External adapters (future)"]:::future

    User --> Web
    Web -->|"JSON over HTTP"| API
    API --> DB
    Seed --> DB
    AuthUser -.-> Web
    API -.-> Recommender
    Recommender -.-> Artifacts
    Sources -.-> DB
    Sources -.-> Pipeline
    Pipeline -.-> Artifacts

    classDef future stroke-dasharray: 6 4
```

## Repository boundaries

### Web

`apps/web` owns pages, presentation components, browser state, and a typed API
client. It does not connect directly to PostgreSQL, embed secrets, or implement
recommendation ranking.

Stage 2 implements Next.js App Router routes for `/`, `/games`, and
`/games/[gameId]`. The root layout and landing page are statically rendered;
focused catalog and detail client components own browser-side API requests and
interactive state. Catalog request state is normalized into URL search
parameters so reload and browser history restore the same request without a
global store.

All browser requests pass through one project-owned client configured by the
validated `NEXT_PUBLIC_API_URL`. Its compile-time contracts are generated from
the live FastAPI OpenAPI document and checked for drift. The runtime boundary
also verifies JSON responses and the standard API error envelope. There is no
backend-for-frontend, internal API URL, direct database access, or browser-side
ranking logic. See the completed
[Stage 2 frontend engineering plan](stage-2-frontend-foundation-plan.md).

### API

`apps/api` owns HTTP contracts, validation, orchestration, and persistence. It
will own online recommendation inference only after a later stage adds a
validated artifact. Route functions remain thin:

```text
route -> service -> repository/model interface -> database or artifact
```

Database sessions are dependency-injected from the app-local engine, which is
also used by readiness checks and disposed at shutdown. Database models are
not returned directly as API responses.

### Database

PostgreSQL stores games, taxonomy, users, preferences, interactions, and
recommendation events. Schema changes use Alembic migrations. Flexible JSON
is limited to request context and compact result summaries where a relational
shape would not be stable.

### Machine learning

`ml` owns preprocessing, training, offline evaluation, reproducibility
metadata, and artifact generation. Training is never triggered by a request.
The API loads a known artifact version and exposes its status.

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
development database volume.

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
- Authentication is deferred, but user identifiers are not embedded into
  recommendation algorithms.

## Current state

Stages 1 and 2 implement the API, database, and web boundaries. Catalog routes
depend on services, repositories, and injected SQLAlchemy sessions; PostgreSQL
is the runtime source of truth. Readiness requires connectivity and the
expected Alembic schema head. The responsive web application supports catalog
search, filters, sorting, pagination, and game details with explicit loading,
empty, unavailable, not-found, and nullable-field states.

The recommendation boundary still exposes only the honest `not_configured`
status. Authentication, onboarding, feedback, an active recommender, the
training pipeline, model artifacts, and production deployment remain future
components.
