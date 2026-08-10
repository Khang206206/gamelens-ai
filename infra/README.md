# Infrastructure

The root `docker-compose.yml` starts PostgreSQL, the FastAPI service, and the
Next.js web development service. PostgreSQL and FastAPI have readiness checks;
the web check proves Next.js HTTP liveness at `/`, while catalog and
recommendation integration are covered by the isolated E2E stack. PostgreSQL uses a named volume; ordinary
`docker compose down` does not delete it. Migrations and deterministic seeding
remain explicit operations and are never hidden in web startup.

The `model` profile adds a one-shot offline builder. It reads the migrated,
seeded database and writes a validated bundle at the configured
`MODEL_ARTIFACT_PATH`. The builder and API receive the same setting; the API
mounts `ml/artifacts` read-only and validates and loads but never builds or
mutates an artifact. Targets are immutable, so catalog/model changes use a new
path before the API is recreated; the old bundle remains available for
rollback. Loader-policy upgrades, including canonical CSR enforcement, also
require rotating `MODEL_ARTIFACT_PATH` and rebuilding and validating a new
bundle. The tracked `ml/artifacts/.gitkeep` ensures the bind-mount directory
exists on a fresh clone while generated members remain ignored.

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

`infra/docker-compose.e2e.yml` is a second isolated Compose project for Stage 3
browser acceptance. It creates a fresh `tmpfs` PostgreSQL database, runs
Alembic and the deterministic seed through a one-shot setup service, then
initializes a disposable named artifact volume. A root-only init container
changes that new volume's owner and exits; the model builder itself runs as the
non-root `gamelens` user. The API receives the finished artifact read-only.
Network-only API and web services then support the exact Playwright 1.62.0
image pinned by digest. `down --volumes --remove-orphans` removes the E2E
containers, network, and artifact volume; it never touches persistent
development data. The verified matrix contains 25 Playwright passes: 15
Chromium plus five smoke cases in each of Firefox and WebKit.

The
[Stage 4 feedback-and-persistence plan](../docs/stage-4-feedback-persistence-plan.md)
will extend this disposable stack with real anonymous-cookie, exact-origin,
CSRF, preference, feedback, event, and clear-data acceptance. The plan uses web
and API aliases under one reserved test site so browser SameSite behavior is
exercised rather than replaced by a fabricated auth header. This topology and
its session secret/cookie settings are not implemented yet.

Stage 4 also plans an explicit dry-run-first retention command. Retention will
never run from Compose startup, migration, seed, model build, general tests, or
ordinary teardown. Automated purge acceptance may target only the guarded
disposable database; it may not mount or delete development data. Fixed session
expiry makes owned state purge-eligible rather than pretending an unscheduled
command deletes it at an exact instant. Permanent bulk session revocation will
use a separately confirmed direct command with no general Make wrapper.

The API image is a non-root Python 3.12 development image built from a
transitive dependency lock. The `quality` Compose service bind-mounts the
working tree for current-source test, lint, and format commands. Production
container optimization and deployment guidance belong to Stage 7. Docker
Scout currently reports two critical and two high unfixed Debian `perl`
advisories inherited from the pinned development base. The local API remains
non-root and loopback-only; Stage 7 must choose and rescan a production-minimal
base rather than treating this development image as deployable.
Kubernetes, Kafka, and microservice infrastructure remain outside the current
scope.

The development image uses configurable `APP_UID`/`APP_GID` build arguments,
defaulting to 1000, so a non-root model builder can write the artifact bind
mount on a typical Linux checkout. Set them to the checkout owner's numeric
IDs before building when they differ; Docker Desktop can keep the defaults.

The repository-root `.dockerignore` excludes local environment files, VCS
metadata, caches, test output, and untracked data from generic root-context
builds. The API Dockerfile has a stricter Dockerfile-specific deny-all
allowlist; the web images use `apps/web/.dockerignore` at their context root.
