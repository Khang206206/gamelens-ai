# GameLens AI API

The GameLens AI API is a Python 3.12 FastAPI application backed by PostgreSQL 16. It exposes the deterministic catalog and Stage 3 artifact-backed content
recommendations. It never trains during startup or a request and never
fabricates recommendations when the configured model is unavailable.

The web application in `apps/web` consumes this API through generated
OpenAPI types and a project-owned browser client. Use the repository
[README](../../README.md) for complete db/API/web startup.

The completed
[Stage 3 plan](../../docs/stage-3-content-recommendation-mvp-plan.md) records the
artifact, scoring, contract, and verification decisions. Anonymous selections
are request-scoped; persistence and feedback are Stage 4 work.

The detailed
[Stage 4 feedback-and-persistence plan](../../docs/stage-4-feedback-persistence-plan.md)
is ready; none of its identity, preference, feedback, personalized-event, or
retention runtime contracts is implemented yet. The endpoint and command
tables below remain the current source of truth.

## Responsibilities

The dependency direction is:

```text
route -> application service -> repository/model service -> PostgreSQL/artifact
```

Routes parse HTTP input, services own use cases, repositories own queries,
Pydantic schemas define external contracts, and SQLAlchemy models remain
internal.

The Stage 4 plan will add a distinct protected `/api/v1/me` boundary after
explicit consent. It keeps `POST /api/v1/recommendations` cookie-agnostic and
read-only, while planned session, preference, feedback, and personalized
recommendation services own their user-scoped validation, locking,
transactions, persistence, and bounded event writes. Raw anonymous credentials
will remain in a host-only HttpOnly cookie and never enter response models,
logs, PostgreSQL, or model artifacts.

## Docker-first setup

Run these commands from the repository root:

```powershell
Copy-Item .env.example .env
docker compose build api
docker compose up -d db
docker compose run --build --rm api python -m alembic upgrade head
docker compose run --build --rm api python -m app.db.seed
docker compose --profile model run --build --rm model-builder `
    python -m app.commands.recommendation_artifact build
docker compose --profile model run --rm --no-deps model-builder `
    python -m app.commands.recommendation_artifact validate
docker compose up -d api
docker compose ps
```

Migrations, seed, and model builds are intentionally explicit. Starting the API
does not modify the database schema, catalog, or model artifact.

Verify the running service:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod "http://localhost:8000/api/v1/games?page=1&page_size=5"
Invoke-RestMethod http://localhost:8000/api/v1/models/status
$body = @{
    preferred_genres = @("rpg")
    preferred_platforms = @("linux")
    top_k = 5
} | ConvertTo-Json
Invoke-RestMethod -Method Post `
    -Uri http://localhost:8000/api/v1/recommendations `
    -ContentType application/json -Body $body
Start-Process http://localhost:8000/docs
```

Stop containers without deleting development data:

```powershell
docker compose down
```

## Host Python workflow

Start PostgreSQL from the repository root:

```powershell
docker compose up -d db
Set-Location apps/api
```

Then use Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ../../ml
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m app.db.seed
$env:MODEL_ARTIFACT_PATH = Join-Path `
    (Resolve-Path ../../ml/artifacts) "content-v1-host"
python -m app.commands.recommendation_artifact build
python -m app.commands.recommendation_artifact validate
python -m app
```

The root `.env` is loaded automatically. Its host `DATABASE_URL` uses
`localhost`; Compose injects a separate URL using the `db` service hostname.
The Docker build uses the complete Linux/Python 3.12 dependency set pinned in
`requirements.lock`; the host workflow resolves the platform-appropriate
dependencies from `pyproject.toml` because the container lock includes
Linux-only packages.

The API declares the source-local `gamelens-recommender==0.1.0` distribution;
installing `../../ml` first makes the host dependency graph complete. The root
`.env` uses the container path `/artifacts/content-v1`, so the host workflow
must override it with an absolute Windows path as shown. If that immutable
target already exists, choose a new directory name instead of deleting or
overwriting the active bundle.

## Endpoints

| Method | Path                         | Purpose                                                        |
| ------ | ---------------------------- | -------------------------------------------------------------- |
| GET    | `/health`                    | Application and PostgreSQL readiness                           |
| GET    | `/api/v1/games`              | Paginated catalog with search, filters, and sorting            |
| GET    | `/api/v1/games/{game_id}`    | Full game details and taxonomy                                 |
| GET    | `/api/v1/metadata/genres`    | Sorted genres                                                  |
| GET    | `/api/v1/metadata/tags`      | Sorted tags                                                    |
| GET    | `/api/v1/metadata/platforms` | Sorted platforms                                               |
| GET    | `/api/v1/models/status`      | Honest `ready`, `not_configured`, or `unavailable` model state |
| POST   | `/api/v1/recommendations`    | Bounded request-scoped recommendations and evidence            |
| GET    | `/docs`                      | Interactive OpenAPI documentation                              |
| GET    | `/openapi.json`              | Machine-readable OpenAPI contract                              |

Catalog pagination is one-based; `page` is capped at 1,000,000. The default
page size is 20 and the maximum is 100. Supported sort values are
`popularity`, `rating`, `release_date`, and `title`. Filters accept `q`,
`genre`, `tag`, and `platform`; unknown taxonomy slugs return an empty page.

Readiness returns HTTP 200 only when PostgreSQL is reachable, every required
Stage 1 table exists, and Alembic is at the expected head. Otherwise it returns
a typed degraded response with HTTP 503. Recommendation-model readiness is
reported separately by `/api/v1/models/status` and is not part of `/health`.

The recommendation request accepts at most five distinct game IDs, five genre
slugs, ten tag slugs, six platform slugs, and `top_k` from 1 through 20. At
least one game, genre, or tag is required. Unknown references, duplicates,
unknown fields, and invalid bounds return the standard 422 envelope. A missing,
invalid, incompatible, or catalog-stale artifact returns 503. A catalog that
cannot be canonicalized returns the same typed 503 envelope with
`catalog_invalid`. The response includes model identity, rank, deterministic
score components, structured evidence, and explanations grounded in that
evidence. Ranking scores are not probabilities or percentages.

`MODEL_ARTIFACT_PATH` is optional at the settings boundary. Compose passes the
same configured path to the offline builder and API, and mounts `ml/artifacts`
read-only in the API. Without configuration, status is `not_configured`; with a failed load it is
`unavailable`. A valid artifact is loaded and made immutable once during app
construction. Ready status and each recommendation compare its fingerprint
with a `REPEATABLE READ, READ ONLY` catalog snapshot.

To rebuild after a catalog or model change, rotate `.env` to a new path such as
`MODEL_ARTIFACT_PATH=/artifacts/content-v1-r2`, run `make model-build` and
`make model-validate`, and recreate the API. Builder targets intentionally
reject existing directories so an active artifact is never overwritten. The
hardened loader also rejects non-canonical CSR indices, so operators upgrading
an existing Stage 3 bundle must rotate the configured path and rebuild and
validate the artifact rather than modify it in place.

The implemented migration chain is:

```text
0001_initial_schema -> 0002_stage_1_integrity_hardening
```

The second revision hardens constraints and indexes without resetting an
existing Stage 1 database.

Errors use one envelope:

```json
{
  "error": {
    "code": "game_not_found",
    "message": "Game 999 was not found"
  }
}
```

## Quality commands

Fast tests:

```powershell
docker compose run --build --rm --no-deps quality python -m pytest tests/unit -q -p no:cacheprovider
docker compose run --build --rm --no-deps quality python -m pytest /workspace/ml/tests -q -p no:cacheprovider
```

PostgreSQL integration tests use a separate Compose project and an in-memory
`tmpfs` data directory. The database has no published host port:

```powershell
docker compose -f infra/docker-compose.test.yml up -d test-db
try {
    docker compose -f infra/docker-compose.test.yml run --build --rm test-api
} finally {
    docker compose -f infra/docker-compose.test.yml down --remove-orphans
}
```

The test service explicitly selects the `integration` marker, requires the
`--run-integration` opt-in, and injects
`GAMELENS_TEST_DATABASE_URL` plus
`GAMELENS_ALLOW_TEST_DATABASE_RESET=true`. The test guard rejects non-test
database identities before Alembic can reset a schema.

Lint, format, and coverage:

```powershell
docker compose run --build --rm --no-deps quality python -m ruff check --no-cache app tests alembic /workspace/ml/src /workspace/ml/tests
docker compose run --build --rm --no-deps quality python -m ruff format --no-cache --check app tests alembic /workspace/ml/src /workspace/ml/tests
docker compose run --build --rm --no-deps quality python -m pytest tests/unit --cov=app --cov-report=term-missing -p no:cacheprovider
docker compose run --build --rm --no-deps quality python -m ruff check --no-cache app tests alembic --fix
docker compose run --build --rm --no-deps quality python -m ruff format --no-cache app tests alembic
```

The `quality` service bind-mounts `apps/api`, so checks always read the current
working tree and formatting writes changes back to the host.

Coverage remains diagnostic; failure-path coverage matters more than an
arbitrary percentage threshold.

The Stage 3 gate on 2026-08-07 passed 104 fast API tests and 29 disposable
PostgreSQL integration tests; diagnostic API coverage was 92%. The integration
suite proves a successful recommendation leaves users, preferences,
interactions, recommendation events, games, and taxonomy unchanged. Ruff,
artifact validation, `catalog_stale`/`catalog_invalid` agreement, CORS
allow/reject cases, OpenAPI generation, Docker E2E, and `pip check` passed.
Docker Scout separately reported two critical and two high unfixed Debian
`perl` advisories inherited from the pinned development base image; this known
base-image finding is retained for Stage 7 hardening.

## Seed data

`data/seed/games.json` contains 30 fictional games and 36 taxonomy records.
Descriptions and synthetic rating signals are project-authored. There are no
cover binaries, external API identifiers, or recommendation-quality claims.
The seed command validates all references and upserts by stable slug.
It emits structured inserted, updated, and unchanged counters.

## Current limitations

- No authentication or authorization.
- No preference, interaction, or feedback write endpoints; persistence begins
  in the
  [Stage 4 engineering plan](../../docs/stage-4-feedback-persistence-plan.md).
- No explicit-consent anonymous session, personalized `/me` recommendation,
  recommendation-event write, or retention command is implemented yet.
- No online fit, background rebuild, hot reload, or automatic artifact
  promotion. Operators build explicitly and restart the API to activate.
- No formal recommendation-quality evaluation on the synthetic seed; that is
  Stage 6 work.
- No external metadata source.
- The Docker image is development-oriented; production hardening is Stage 7.
