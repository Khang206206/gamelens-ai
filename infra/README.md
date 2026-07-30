# Infrastructure

The root `docker-compose.yml` starts PostgreSQL, the FastAPI service, and the
Next.js web development service. PostgreSQL and FastAPI have readiness checks;
the web check proves Next.js HTTP liveness at `/`, while catalog integration is
covered by the isolated E2E stack. PostgreSQL uses a named volume; ordinary
`docker compose down` does not delete it. Migrations and deterministic seeding
remain explicit operations and are never hidden in web startup.

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

Changing a published port requires changing its paired origin:
`WEB_PORT` with `CORS_ORIGINS`, and `API_PORT` with
`NEXT_PUBLIC_API_URL`. The tracked `.env.example` shows both pairs.

`infra/docker-compose.test.yml` is a separate Compose project for PostgreSQL
integration tests. Its database uses `tmpfs`, has no published host port, and
is disposable. The test service requires both an explicit pytest flag and a
test-only database-reset opt-in. It never mounts or resets the development
database volume.

`infra/docker-compose.e2e.yml` is a second isolated Compose project for Stage 2
browser acceptance. It creates a fresh `tmpfs` PostgreSQL database, runs
Alembic and the deterministic seed through a one-shot setup service, starts
network-only API and web services, and executes the browser suite in the exact
Playwright 1.62.0 image pinned by digest. It has no dependency on the
persistent development volume and removes no development data when torn down.
The verified suite currently contains 21 scenarios across Chromium, Firefox,
and WebKit.

The API image is a non-root Python 3.12 development image built from a
transitive dependency lock. The `quality` Compose service bind-mounts the
working tree for current-source test, lint, and format commands. Production
container optimization and deployment guidance belong to Stage 7.
Kubernetes, Kafka, and microservice infrastructure remain outside the current
scope.

The repository-root `.dockerignore` excludes local environment files, VCS
metadata, caches, test output, and untracked data from generic root-context
builds. The API Dockerfile has a stricter Dockerfile-specific deny-all
allowlist; the web images use `apps/web/.dockerignore` at their context root.
