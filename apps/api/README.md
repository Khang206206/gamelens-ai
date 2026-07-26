# GameLens AI API

The Stage 1 API is a Python 3.12 FastAPI application backed by PostgreSQL 16.
It exposes a deterministic catalog and an honest recommendation-model status;
it does not train or fabricate recommendations.

## Responsibilities

The dependency direction is:

```text
route -> service -> repository -> SQLAlchemy session -> PostgreSQL
```

Routes parse HTTP input, services own use cases, repositories own queries,
Pydantic schemas define external contracts, and SQLAlchemy models remain
internal.

## Docker-first setup

Run these commands from the repository root:

```powershell
Copy-Item .env.example .env
docker compose build api
docker compose up -d db
docker compose run --build --rm api python -m alembic upgrade head
docker compose run --build --rm api python -m app.db.seed
docker compose up -d api
docker compose ps
```

Migrations and seed operations are intentionally explicit. Starting the API
does not modify the database schema or catalog.

Verify the running service:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod "http://localhost:8000/api/v1/games?page=1&page_size=5"
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
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m app.db.seed
python -m app
```

The root `.env` is loaded automatically. Its host `DATABASE_URL` uses
`localhost`; Compose injects a separate URL using the `db` service hostname.
The Docker build uses the complete Linux/Python 3.12 dependency set pinned in
`requirements.lock`; the host workflow resolves the platform-appropriate
dependencies from `pyproject.toml` because the container lock includes
Linux-only packages.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Application and PostgreSQL readiness |
| GET | `/api/v1/games` | Paginated catalog with search, filters, and sorting |
| GET | `/api/v1/games/{game_id}` | Full game details and taxonomy |
| GET | `/api/v1/metadata/genres` | Sorted genres |
| GET | `/api/v1/metadata/tags` | Sorted tags |
| GET | `/api/v1/metadata/platforms` | Sorted platforms |
| GET | `/api/v1/models/status` | Explicit `not_configured` model state |
| GET | `/docs` | Interactive OpenAPI documentation |
| GET | `/openapi.json` | Machine-readable OpenAPI contract |

Catalog pagination is one-based; `page` is capped at 1,000,000. The default
page size is 20 and the maximum is 100. Supported sort values are
`popularity`, `rating`, `release_date`, and `title`. Filters accept `q`,
`genre`, `tag`, and `platform`; unknown taxonomy slugs return an empty page.

Readiness returns HTTP 200 only when PostgreSQL is reachable, every required
Stage 1 table exists, and Alembic is at the expected head. Otherwise it returns
a typed degraded response with HTTP 503.

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
docker compose run --build --rm --no-deps quality python -m ruff check --no-cache app tests alembic
docker compose run --build --rm --no-deps quality python -m ruff format --no-cache --check app tests alembic
docker compose run --build --rm --no-deps quality python -m pytest tests/unit --cov=app --cov-report=term-missing -p no:cacheprovider
docker compose run --build --rm --no-deps quality python -m ruff check --no-cache app tests alembic --fix
docker compose run --build --rm --no-deps quality python -m ruff format --no-cache app tests alembic
```

The `quality` service bind-mounts `apps/api`, so checks always read the current
working tree and formatting writes changes back to the host.

Coverage is reported as a diagnostic in Stage 1; failure-path coverage matters
more than an arbitrary percentage threshold.

The acceptance gate was last re-audited on 2026-07-26: 84 fast tests and 28
PostgreSQL integration tests passed, application coverage was 92%, Ruff checks
passed, the locked dependency graph had no known vulnerabilities, and the
Docker/HTTP smoke matrix passed.

## Seed data

`data/seed/games.json` contains 30 fictional games and 36 taxonomy records.
Descriptions and synthetic rating signals are project-authored. There are no
cover binaries, external API identifiers, or recommendation-quality claims.
The seed command validates all references and upserts by stable slug.
It emits structured inserted, updated, and unchanged counters.

## Current limitations

- No authentication or authorization.
- No preference or interaction write endpoints.
- No frontend.
- No trained or active recommendation model.
- No external metadata source.
- The Docker image is development-oriented; production hardening is Stage 7.
