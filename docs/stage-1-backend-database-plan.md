# GameLens AI

## Stage 1 Engineering Plan: Backend and Database Foundation

- **Document status:** Implemented and verified on 2026-07-26
- **Stage 0 prerequisite:** Complete
- **Target branch:** `feat/stage-1-backend-foundation`
- **Primary outcome:** A runnable, tested, containerized catalog API backed by
  PostgreSQL and deterministic development data.

This document retains the original forward-looking implementation language so
the execution sequence remains reviewable. The implemented decisions are
recorded in Section 21, the completed frontend handoff in Section 22, and the
final acceptance evidence in Section 23.


## 1. Context

Stage 0 established the monorepo boundaries, architecture documentation,
environment-variable conventions, and a healthy PostgreSQL service managed by
Docker Compose. Stage 1 converts that foundation into the first executable
application slice.

The stage focuses on backend and persistence fundamentals rather than
recommendation quality. It must establish stable API contracts, a reproducible
database schema, deterministic seed data, and a development workflow that can
be reused by the frontend and machine-learning stages.

The resulting backend should demonstrate:

- Clear separation between HTTP routes, services, repositories, schemas, and
  database models.
- Environment-based configuration with no committed secrets.
- Reproducible schema evolution through Alembic.
- Deterministic local data with documented provenance.
- Typed API responses and centralized error handling.
- Fast tests for application behavior and PostgreSQL integration tests for
  database-specific behavior.
- Docker-first setup that does not require a host PostgreSQL installation.


## 2. Stage Objectives

Stage 1 will deliver:

1. A Python 3.12 FastAPI project under `apps/api`.
2. Typed settings, structured logging, CORS configuration, and centralized
   exception handling.
3. SQLAlchemy 2.x session management using PostgreSQL as the primary database.
4. Alembic configuration and an initial reviewed migration.
5. Relational models for the catalog, taxonomy, anonymous users, preferences,
   interactions, and recommendation events.
6. A deterministic seed dataset containing at least 25 varied games.
7. Health, catalog, detail, taxonomy, and model-status endpoints.
8. A documented recommendation-service interface without a fake active model.
9. Backend unit, contract, migration, seed, and integration tests.
10. An API Docker image and a complete local Docker Compose workflow.
11. Root commands and documentation that match verified behavior.


## 3. Non-Goals

The following work is intentionally excluded from Stage 1:

- Next.js or any frontend implementation.
- Onboarding and preference-submission endpoints.
- Interaction and feedback write endpoints.
- Popularity, content-based, collaborative, or hybrid recommendation logic.
- Model training or evaluation.
- Authentication and authorization.
- External game metadata APIs.
- Cover-image downloads.
- LLM integrations.
- Production deployment configuration.
- GitHub Actions or broader CI/CD work.
- Performance or recommendation-quality claims.

The database may include entities needed by later stages, but those entities
must not be exposed through incomplete APIs.


## 4. Engineering Principles

### 4.1 Incremental Delivery

Implementation will proceed through small vertical slices. Each phase must
leave the repository importable, testable, and understandable before the next
phase begins.

### 4.2 Honest System State

No endpoint may imply that a recommendation model has been trained or loaded.
The model-status endpoint will explicitly report that no active model is
configured until Stage 3.

### 4.3 Explicit Lifecycle Operations

Database migrations and seed operations will use explicit commands. They will
not run silently inside ordinary API requests.

### 4.4 Database Fidelity

PostgreSQL is the source of truth for runtime behavior. SQLite may support fast
tests only where the tested behavior is database-portable. PostgreSQL-specific
constraints, migrations, and seed behavior require PostgreSQL integration
tests.

### 4.5 Determinism

Seed records, ordering, pagination, migration state, and test fixtures must
produce repeatable results. Tie-breaking rules must be explicit.

### 4.6 Minimal Dependency Surface

Only dependencies with a clear Stage 1 purpose will be introduced. Exact
versions will be selected and pinned after a compatibility smoke test.

### 4.7 Safe Local Operations

Automated tests must not delete or reset the persistent development volume.
Destructive database tests will run against a disposable database or volume.


## 5. Proposed Technical Decisions

### 5.1 Runtime and Framework

- Python 3.12
- FastAPI
- Uvicorn
- Pydantic v2
- pydantic-settings

### 5.2 Persistence

- PostgreSQL 16
- SQLAlchemy 2.x synchronous sessions
- Psycopg 3
- Alembic

Synchronous sessions are preferred for this stage because the catalog workload
is small and the simpler transaction model is easier to test and maintain.
An asynchronous database stack can be evaluated later if profiling identifies
a concrete need.

### 5.3 Quality Tooling

- pytest
- pytest-cov
- HTTPX
- Ruff linting and formatting

Static type checking may be introduced later if it can be configured without
creating disproportionate setup overhead.

### 5.4 Project Metadata and Dependency Pinning

`apps/api/pyproject.toml` defines project metadata, Python compatibility,
direct dependencies, and tool configuration. Runtime and development
dependencies are fully locked for the Linux/Python 3.12 Docker workflow after
verifying that the complete initial stack imports and starts successfully.

### 5.5 Configuration

All runtime settings will come from environment variables:

- `APP_NAME`
- `ENVIRONMENT`
- `API_HOST`
- `API_PORT`
- `DATABASE_URL`
- `CORS_ORIGINS`
- `LOG_LEVEL`

The host workflow will connect to PostgreSQL through `localhost`. The Compose
API service will receive a container-specific `DATABASE_URL` using the `db` service
hostname.

### 5.6 API Layering

The required dependency direction is:

```text
route -> service -> repository -> SQLAlchemy session -> PostgreSQL
```

**Responsibilities:**

- Routes handle HTTP parsing, dependency injection, and response selection.
- Services implement use cases and domain-level decisions.
- Repositories own database queries and persistence behavior.
- Pydantic schemas define stable external contracts.
- SQLAlchemy models remain internal persistence representations.

### 5.7 Identifiers and Timestamps

- Integer primary keys for Stage 1 entities.
- Unique, stable slugs for games and taxonomy records.
- Timezone-aware UTC timestamps.
- Nullable external identifiers for future source adapters.


## 6. Target Repository Structure

```text
apps/api/
|-- app/
|   |-- api/
|   |   `-- v1/
|   |       |-- routes/
|   |       |   |-- games.py
|   |       |   |-- metadata.py
|   |       |   `-- models.py
|   |       `-- router.py
|   |-- core/
|   |   |-- config.py
|   |   |-- exceptions.py
|   |   `-- logging.py
|   |-- db/
|   |   |-- models/
|   |   |-- base.py
|   |   |-- seed.py
|   |   `-- session.py
|   |-- repositories/
|   |-- schemas/
|   |-- services/
|   |   `-- recommendation/
|   `-- main.py
|-- alembic/
|   `-- versions/
|-- tests/
|   |-- integration/
|   `-- unit/
|-- alembic.ini
|-- Dockerfile
|-- requirements.lock
|-- pyproject.toml
`-- README.md

data/seed/
`-- games.json

infra/
`-- docker-compose.test.yml
```

Directories will be created only when they contain implementation, fixtures,
configuration, or meaningful documentation.


## 7. Implementation Phase 0: Preflight and Baseline

### Objective

Establish a clean implementation baseline and protect the completed Stage 0
state.

### Work

1. Confirm that main is clean and synchronized with origin/main.
2. Confirm that Docker Engine and Docker Compose are available.
3. Validate the existing Compose configuration.
4. Check whether ports 5432 and 8000 are available.
5. Create feat/stage-1-backend-foundation from the latest main.
6. Record the baseline repository tree and verification commands.
7. Confirm that `.env` is ignored and `.env.example` is tracked.

### Verification

- `git status --short --branch`
- `git log --oneline -3`
- `docker version`
- `docker compose version`
- `docker compose config --quiet`
- `git check-ignore .env`

### Exit Criteria

- The working tree is clean.
- The feature branch starts from the current main commit.
- Docker Engine responds successfully.
- The Stage 0 Compose configuration remains valid.


## 8. Implementation Phase 1: Python and FastAPI Skeleton

### Objective

Create the smallest importable and testable API application before introducing
database dependencies.

### Work

1. Create `apps/api/pyproject.toml` with project metadata and tool configuration.
2. Select and pin compatible runtime and development dependency versions.
3. Create the Python package structure and FastAPI application factory.
4. Add an initial `GET /health` response that verifies application startup.
5. Enable generated OpenAPI documentation at `/docs` and `/openapi.json`.
6. Add initial pytest fixtures and a health endpoint contract test.
7. Replace the placeholder `apps/api/README.md` with working setup instructions.

### Verification

- Import the application in a clean Python environment.
- Start Uvicorn and request `GET /health`.
- Confirm that `/docs` and `/openapi.json` return HTTP 200.
- Run pytest for the initial health contract.
- Run Ruff lint and format checks.

### Exit Criteria

- The application imports without PostgreSQL running.
- `GET /health` returns a typed response.
- The initial tests and Ruff checks pass.
- No unrelated or placeholder endpoints are present.


## 9. Implementation Phase 2: Settings, Logging, and Error Contracts

### Objective

Stabilize configuration and cross-cutting behavior before database and catalog
features depend on them.

### Work

1. Implement typed settings with pydantic-settings.
2. Validate environment names, API ports, log levels, and CORS origins.
3. Cache the runtime settings object while allowing deterministic test
   overrides.
4. Configure structured application logging without exposing secrets.
5. Define a standard API error envelope:
   code, message, and optional details or request identifier.
6. Add domain exception types and centralized FastAPI exception handlers.
7. Configure CORS from the explicit environment allowlist.
8. Document every environment variable and its development default.

### Verification

- Default development settings load successfully.
- Invalid settings fail during startup with a clear error.
- Tests can override settings without reading the developer's `.env` file.
- Validation and not-found errors use the documented error envelope.
- Log output does not contain passwords or a complete connection URL.
- CORS tests confirm allowed and rejected origins.

### Exit Criteria

- Configuration has one documented source of truth.
- Error responses are consistent.
- Tests are independent of workstation-specific environment values.


## 10. Implementation Phase 3: Database Session and Alembic Foundation

### Objective

Establish reliable PostgreSQL connectivity, transaction boundaries, and
migration infrastructure before adding the full schema.

### Work

1. Create a SQLAlchemy Declarative Base with deterministic naming conventions
   for indexes and constraints.
2. Create the engine, session factory, and FastAPI database dependency.
3. Use SQLAlchemy 2.x query and session APIs.
4. Configure Alembic to load application metadata and `DATABASE_URL`.
5. Add a PostgreSQL connectivity check using `SELECT 1`.
6. Define clear commit, rollback, and close behavior.
7. Extend health behavior to report database readiness without exposing
   connection details.
8. Prepare host and container database URLs without duplicating secrets.

### Verification

- PostgreSQL reaches the healthy state.
- A SQLAlchemy `SELECT 1` query succeeds.
- `alembic current` runs successfully.
- Database sessions close after requests.
- A failed database connection produces a controlled readiness response.
- Connection failures do not leak credentials.

### Exit Criteria

- The API can connect to the Compose PostgreSQL service.
- Alembic is operational before the initial schema migration is created.
- Transaction lifecycle behavior is covered by tests.


## 11. Implementation Phase 4: Relational Models and Initial Migration

### Objective

Convert docs/data-model.md into an executable, reviewed relational schema.

### Tables

- games
- genres
- tags
- platforms
- game_genres
- game_tags
- game_platforms
- users
- user_preferences
- interactions
- recommendation_events

### Work

1. Implement SQLAlchemy models and relationships.
2. Add uniqueness constraints for slugs and association pairs.
3. Add non-negative checks for rating counts and applicable numeric signals.
4. Add documented bounds for preference weights.
5. Add explicit foreign keys and deletion behavior.
6. Add indexes for catalog filtering and user-event lookup paths.
7. Use application enums and database checks for interaction types.
8. Restrict JSON columns to recommendation request context and compact result
   summaries.
9. Generate the initial Alembic migration.
10. Review the generated migration manually for ordering, naming, indexes, and
    downgrade safety.
11. Update docs/data-model.md wherever implementation decisions refine the
    original design.

### Verification

- Run alembic upgrade head against a disposable PostgreSQL database.
- Confirm alembic current matches the head revision.
- Inspect the resulting tables, indexes, foreign keys, and constraints.
- Test unique slugs and association pairs.
- Test foreign-key enforcement.
- Test non-negative and bounded numeric constraints.
- Compare SQLAlchemy metadata with the migration result.

### Exit Criteria

- A fresh PostgreSQL database upgrades to head without manual SQL.
- Models and migration describe the same schema.
- Constraint and index behavior is covered by integration tests.
- No persistent development volume is deleted during testing.


## 12. Implementation Phase 5: Deterministic Seed Data

### Objective

Provide a varied local catalog for API development and future recommendation
work without requiring network access or third-party licensing.

### Work

1. Create `data/seed/games.json` with at least 25 varied games.
2. Include enough genre, tag, platform, release-date, rating, and popularity
   variation to exercise filtering and pagination.
3. Use minimal metadata and original short descriptions.
4. Keep cover_image_url null unless a stable, licensed source is documented.
5. Define and validate the seed-file schema.
6. Implement a standalone seed command.
7. Use game and taxonomy slugs as deterministic natural keys.
8. Upsert records and associations without creating duplicates.
9. Log inserted, updated, and unchanged record counts.
10. Document seed-data provenance and development-only limitations.

### Verification

- Parse and validate the seed file.
- Run the seed command against an empty PostgreSQL database.
- Confirm that at least 25 games are present.
- Run the seed command a second time.
- Confirm that record and association counts remain stable.
- Confirm that every game has a title, slug, genre, and platform.
- Confirm unique slugs and non-negative numeric values.
- Confirm that no image binaries, secrets, or performance claims are included.

### Exit Criteria

- The catalog can be reproduced with one documented command.
- Seeding is idempotent.
- Seed provenance and limitations are documented.


## 13. Implementation Phase 6: Repositories, Services, and API Schemas

### Objective

Create a maintainable catalog application layer and stable contracts for the
future frontend.

### Work

1. Implement GameRepository operations for count, paginated listing, filtering,
   and lookup by internal ID.
2. Implement taxonomy repositories or equivalent focused query functions.
3. Implement CatalogService for catalog use cases and domain error mapping.
4. Define GameSummary, GameDetail, taxonomy, pagination, and error schemas.
5. Use one-based pagination with validated bounds.
6. Set a documented default page size and maximum page size of 100.
7. Support catalog filters for:
   q, genre, tag, and platform slug.
8. Define deterministic sorting and tie-breaking.
9. Use appropriate eager loading to avoid N+1 taxonomy queries.
10. Keep SQLAlchemy models out of external responses.

### Verification

- Test empty and non-empty catalog behavior.
- Test first, middle, final, and out-of-range pages.
- Test invalid page and page-size values.
- Test each filter independently and in supported combinations.
- Test deterministic ordering when primary sort values are equal.
- Test unknown game lookup and domain-to-HTTP error mapping.
- Inspect query behavior for obvious N+1 loading.

### Exit Criteria

- Repository and service behavior is deterministic.
- Response schemas are independent of persistence models.
- Pagination and filter contracts are covered by tests.


## 14. Implementation Phase 7: HTTP Endpoints and Model Status

### Objective

Expose the complete Stage 1 catalog slice through versioned HTTP contracts.

### Endpoints

- `GET /health`
- `GET /api/v1/games`
- `GET /api/v1/games/{game_id}`
- `GET /api/v1/metadata/genres`
- `GET /api/v1/metadata/tags`
- `GET /api/v1/metadata/platforms`
- `GET /api/v1/models/status`

### Work

1. Register a versioned API router.
2. Keep route functions limited to request parsing, dependency injection, and
   response selection.
3. Return pagination metadata with catalog results:
   items, page, page_size, total, and total_pages.
4. Return full taxonomy metadata with game details.
5. Return taxonomy lists in deterministic order.
6. Define an abstract recommendation-service contract with model name, model
   version, readiness, and recommendation capabilities.
7. Report `not_configured` and a null active model until Stage 3.
8. Ensure all endpoint contracts appear in OpenAPI.

### Verification

- Health returns HTTP 200 when application and database are ready.
- Catalog returns seeded games and correct pagination metadata.
- A known game returns HTTP 200 with taxonomy details.
- An unknown game returns the standard HTTP 404 error envelope.
- Genre, tag, and platform lists are non-empty, unique, and sorted.
- Invalid query parameters return controlled validation errors.
- Model status accurately reports that no model is configured.
- `/docs` and `/openapi.json` contain every Stage 1 endpoint.

### Exit Criteria

- Every required Stage 1 endpoint works against PostgreSQL seed data.
- Contracts are stable enough for Stage 2 frontend integration.
- No endpoint produces fake recommendation output.


## 15. Implementation Phase 8: Docker and Development Commands

### Objective

Provide a reproducible Docker-first workflow that does not require host Python
or PostgreSQL installations.

### Work

1. Create `apps/api/Dockerfile` using a Python 3.12 slim base.
2. Run the application as a non-root container user where practical.
3. Add an API-specific .dockerignore.
4. Add the `api` service to `docker-compose.yml`.
5. Inject a container-specific `DATABASE_URL` using the `db` service hostname.
6. Make the API service depend on the database health check.
7. Add an API health check.
8. Keep migrations and seeding as explicit commands.
9. Add root commands only after their direct equivalents work:
   build, api, migrate, seed, test, test-integration, lint, and format.
10. Document direct PowerShell and Docker commands for environments without
    GNU Make.
11. Add a disposable PostgreSQL test configuration if required to isolate
    integration tests from development data.

### Verification

- `docker compose --profile quality config --quiet`
- `docker compose -f infra/docker-compose.test.yml config --quiet`
- `docker compose build api`
- `docker compose up -d db`
- `docker compose run --build --rm api python -m alembic upgrade head`
- `docker compose run --build --rm api python -m app.db.seed`
- `docker compose up -d api`
- `docker compose ps`
- HTTP requests to the health and catalog endpoints
- `docker compose down`

### Exit Criteria

- The db and api services both become healthy.
- The Docker-only workflow is fully documented.
- Restarting containers does not remove the PostgreSQL volume.
- No secret is embedded in an image or committed configuration.


## 16. Implementation Phase 9: Test Matrix and Quality Gate

### Objective

Validate application behavior, database fidelity, container startup, and
documentation before the stage is considered complete.

### Fast Test Suite

- Settings validation and overrides.
- Structured error responses.
- Schema validation.
- Pagination calculations.
- Repository and service behavior that is portable to SQLite.
- HTTP contracts through an isolated test application.

### PostgreSQL Integration Suite

- Engine connectivity.
- Initial migration against a fresh database.
- Constraint and index behavior.
- Seed creation and idempotency.
- Catalog, detail, and taxonomy endpoints using PostgreSQL seed data.
- Session commit, rollback, and cleanup behavior.

### Static Checks

- Ruff lint.
- Ruff format check.
- `git diff --check`.
- `docker compose --profile quality config --quiet`.
- `docker compose -f infra/docker-compose.test.yml config --quiet`.
- Secret and ignored-file review.
- OpenAPI route inventory.

### HTTP Smoke Matrix

- `GET /health` -> HTTP 200.
- `GET /api/v1/games?page=1&page_size=5` -> five or fewer items with correct
  pagination metadata.
- `GET` an existing game -> HTTP 200.
- `GET` an unknown game -> HTTP 404 with the standard error envelope.
- `GET` genre, tag, and platform metadata -> deterministic non-empty lists.
- `GET /api/v1/models/status` -> `not_configured`.
- `GET /docs` and `GET /openapi.json` -> HTTP 200.

### Coverage Policy

- Generate a coverage report for application code.
- Exclude migration scripts and static seed fixtures from coverage targets.
- Test failure paths explicitly rather than relying on a percentage alone.
- Record meaningful gaps instead of inventing or concealing results.

### Operational Smoke Test

1. Build and start the Compose stack.
2. Confirm that db and api report healthy.
3. Request health and a five-item catalog page from `localhost:8000`.
4. Inspect the generated API documentation.
5. Stop the stack with `docker compose down`.
6. Confirm that the named PostgreSQL volume remains present.

### Exit Criteria

- All automated tests pass.
- PostgreSQL integration tests pass.
- Ruff lint and format checks pass.
- Docker Compose validation and startup pass.
- The operational smoke test passes.
- Remaining limitations are documented.


## 17. Implementation Phase 10: Documentation and Release Preparation

### Objective

Make the completed backend reproducible, reviewable, and ready to support the
frontend stage.

### Work

1. Update the root README with:
   setup, migration, seed, test, lint, endpoint, and OpenAPI instructions.
2. Replace `apps/api` placeholder documentation with verified commands.
3. Update architecture.md and data-model.md to match the implementation.
4. Update roadmap.md only after the Stage 1 acceptance gate passes.
5. Document current limitations:
   no authentication, frontend, active recommender, or external metadata.
6. Record the commands actually executed and their outcomes.
7. Review the repository tree and remove dead placeholders.
8. Review the Git diff for secrets, generated artifacts, and unrelated changes.

### Suggested Commit Structure

1. `chore(api): scaffold FastAPI project and quality tooling`
2. `feat(db): add SQLAlchemy models and initial migration`
3. `feat(catalog): add deterministic seed data and catalog API`
4. `test(docker): add integration workflow and Stage 1 documentation`

### Exit Criteria

- Setup documentation is reproducible from a clean checkout.
- Every documented command exists and works.
- The final diff contains only Stage 1 scope.
- No `.env` file, credential, local database, or generated coverage output is
  tracked.
- The branch is ready for review and merge.


## 18. Command Interface Target

The following root commands should exist only after their implementations are
verified:

- `make help`
- `make config`
- `make build`
- `make up`
- `make down`
- `make logs`
- `make api`
- `make migrate`
- `make seed`
- `make test`
- `make test-integration`
- `make lint`
- `make format`

Equivalent Docker and PowerShell commands must be documented so GNU Make
remains optional on Windows.


## 19. Acceptance Criteria

Stage 1 is complete only when all of the following are true:

- The API image builds successfully.
- PostgreSQL and API services become healthy.
- Alembic upgrades a fresh PostgreSQL database to head.
- SQLAlchemy models and the migration describe the same schema.
- The deterministic seed command creates at least 25 games.
- Running the seed command twice does not duplicate records or associations.
- Health, catalog, detail, taxonomy, and model-status endpoints satisfy their
  documented contracts.
- The model-status endpoint does not claim that a model is trained or active.
- Fast and PostgreSQL integration test suites pass.
- Ruff lint and format checks pass.
- Development and integration Compose files pass quiet validation, including
  the opt-in quality profile.
- Root commands and README instructions match verified behavior.
- No secrets, local databases, or generated artifacts are committed.
- Known limitations and the Stage 2 handoff are documented.


## 20. Risks and Mitigations

**Risk:** Dependency incompatibility.

**Mitigation:** Run an import and startup compatibility smoke test before pinning
versions or building substantial application code.

**Risk:** Container code uses `localhost` for PostgreSQL.

**Mitigation:** Inject a Compose-specific `DATABASE_URL` that uses the `db` service
hostname while retaining localhost for host development.

**Risk:** Integration tests modify development data.

**Mitigation:** Use a disposable PostgreSQL database or Compose configuration and
never remove the persistent development volume as part of routine tests.

**Risk:** Alembic autogenerate produces noisy or incorrect migrations.

**Mitigation:** Review every generated migration and validate it against a fresh
PostgreSQL database.

**Risk:** Repeated seeding creates duplicates.

**Mitigation:** Use stable natural keys, explicit upserts, and an idempotency test.

**Risk:** Catalog serialization triggers N+1 queries.

**Mitigation:** Use focused eager loading and inspect query behavior in repository
tests.

**Risk:** Seed metadata introduces licensing concerns.

**Mitigation:** Use minimal metadata, original descriptions, nullable image URLs,
and documented provenance.

**Risk:** A placeholder recommender is mistaken for a trained model.

**Mitigation:** Expose an explicit `not_configured` status and return no fabricated
scores or recommendations.

**Risk:** Windows environments lack Python or GNU Make.

**Mitigation:** Maintain a complete Docker-first workflow and document direct
PowerShell equivalents.


## 21. Implementation-Time Decisions

The following decisions were confirmed during implementation after
compatibility or behavior tests:

1. Direct dependencies are pinned in `apps/api/pyproject.toml`; the complete
   Linux/Python 3.12 Docker graph is pinned in `apps/api/requirements.lock`
   after host and container smoke tests.
2. Structured logs use timestamp, level, logger, message, safe request/error
   context, and explicit seed inserted/updated/unchanged counters.
3. Catalog pages default to 20, are capped at 100, and support `popularity`,
   `rating`, `release_date`, and `title` sorts with deterministic ID
   tie-breaking.
4. Unknown taxonomy filters return an empty page with valid pagination
   metadata.
5. Stage 1 interactions remain repeatable events; state-like upsert policy is
   deferred to the Stage 4 feedback contract.
6. PostgreSQL integration tests use the independent
   `infra/docker-compose.test.yml` project with a `tmpfs` database. Destructive
   setup requires an explicit opt-in, a dedicated `_test` database on an
   allowlisted host, and verification of the connected database identity.
7. Coverage remains a diagnostic without a Stage 1 threshold. The verified
   application result is 92%, with explicit failure-path tests.
8. Request sessions and health checks use the same app-local engine. Readiness
   requires both the Stage 1 tables and Alembic head; the engine is disposed at
   application shutdown.

Every resolved decision must be reflected in code, tests, and documentation.


## 22. Stage 2 Handoff

Stage 1 leaves the frontend stage with:

- A stable local API base URL.
- OpenAPI documentation.
- Typed and documented catalog response shapes.
- Deterministic seed data for visual development.
- Reliable pagination and taxonomy filtering.
- Documented loading, empty, validation, and not-found behaviors.
- A Docker workflow that starts the API and PostgreSQL without source changes.

The catalog contracts and Stage 1 acceptance criteria are complete, so Stage 2
frontend implementation can begin against this handoff.


## 23. Verified Completion Record

Stage 1 was implemented on `feat/stage-1-backend-foundation` and re-audited on
2026-07-26. The verified result is:

- 84 fast unit and contract tests passed.
- 28 integration tests passed against disposable PostgreSQL.
- Diagnostic application coverage was 92%, including explicit failure paths.
- Ruff lint and format checks passed.
- Both development and integration Compose configurations passed quiet
  validation.
- Alembic upgraded the persistent development database from
  `0001_initial_schema` to `0002_stage_1_integrity_hardening` without data loss
  or model/schema drift.
- The seed command produced 30 games and 36 taxonomy records and remained
  unchanged on a second run.
- The locked container dependency graph had no known vulnerabilities.
- PostgreSQL and the non-root API container became healthy, and the health,
  catalog, detail, taxonomy, model-status, OpenAPI, and documentation smoke
  checks passed.
- `.env`, secrets, local databases, and generated coverage artifacts were not
  committed.

GNU Make remained optional and was not installed in the verification
environment; every Make target used in Stage 1 has a documented direct
PowerShell/Docker equivalent.
