# Infrastructure

The root `docker-compose.yml` starts PostgreSQL and the Stage 1 FastAPI service
with health checks. PostgreSQL uses a named volume; ordinary
`docker compose down` does not delete it.

`infra/docker-compose.test.yml` is a separate Compose project for PostgreSQL
integration tests. Its database uses `tmpfs`, has no published host port, and
is disposable. The test service requires both an explicit pytest flag and a
test-only database-reset opt-in. It never mounts or resets the development
database volume.

Development database and API ports bind to `127.0.0.1`, not every host
interface. The API image is a non-root, Python 3.12 development image built
from a transitive dependency lock. The `quality` Compose service bind-mounts
the working tree for current-source test, lint, and format commands.
Production container and deployment guidance belong to Stage 7. Kubernetes,
Kafka, and microservice infrastructure remain outside the current scope.
