.PHONY: help config build build-web up down logs api web migrate seed model-build model-validate test-ml test test-integration test-web test-web-e2e lint lint-web format format-web api-types

help:
	@echo "GameLens AI Stage 3 commands"
	@echo "  make config  Validate development and test Compose without printing secrets"
	@echo "  make build   Build the API development image"
	@echo "  make build-web  Build the web development image"
	@echo "  make up      Start PostgreSQL, API, and web in the background"
	@echo "  make down    Stop services without deleting the database volume"
	@echo "  make logs    Follow PostgreSQL and API logs"
	@echo "  make api     Run PostgreSQL and API in the foreground"
	@echo "  make web     Run the full development stack in the foreground"
	@echo "  make migrate Upgrade the development database to Alembic head"
	@echo "  make seed    Load deterministic development catalog data"
	@echo "  make model-build  Build the configured MODEL_ARTIFACT_PATH"
	@echo "  make model-validate  Validate the configured artifact without mutation"
	@echo "  make test-ml  Run deterministic ML and artifact tests"
	@echo "  make test    Run the fast unit and contract suite"
	@echo "  make test-integration  Run tests against disposable PostgreSQL"
	@echo "  make test-web  Run web type, lint, format, unit, build, and API drift checks"
	@echo "  make test-web-e2e  Run browser tests against an isolated full stack"
	@echo "  make lint    Run Ruff lint and formatting checks"
	@echo "  make lint-web  Run web lint and formatting checks"
	@echo "  make format  Apply Ruff fixes and formatting"
	@echo "  make format-web  Apply Prettier formatting"
	@echo "  make api-types  Refresh web contracts from the running API"

config:
	docker compose --profile quality config --quiet
	docker compose -f infra/docker-compose.test.yml config --quiet
	docker compose -f infra/docker-compose.e2e.yml config --quiet

build:
	docker compose build api

build-web:
	docker compose build web

up:
	docker compose up --build -d db api web
	docker compose ps

down:
	docker compose down

logs:
	docker compose logs -f db api web

api:
	docker compose up --build api

web:
	docker compose up --build db api web

migrate:
	docker compose run --build --rm api python -m alembic upgrade head

seed:
	docker compose run --build --rm api python -m app.db.seed

model-build:
	docker compose --profile model run --build --rm model-builder python -m app.commands.recommendation_artifact build

model-validate:
	docker compose --profile model run --rm --no-deps model-builder python -m app.commands.recommendation_artifact validate

test-ml:
	docker compose run --build --rm --no-deps quality python -m pytest /workspace/ml/tests -q -p no:cacheprovider

test:
	docker compose run --build --rm --no-deps quality python -m pytest tests/unit -q -p no:cacheprovider

test-integration:
	@code=0; trap 'docker compose -f infra/docker-compose.test.yml down --remove-orphans' EXIT; docker compose -f infra/docker-compose.test.yml up -d test-db && docker compose -f infra/docker-compose.test.yml run --build --rm test-api || code=$$?; exit $$code

test-web:
	cd apps/web && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run typecheck
	cd apps/web && npm run lint
	cd apps/web && npm run format:check
	cd apps/web && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run test
	cd apps/web && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run build
	cd apps/web && npm run api:types:check

test-web-e2e:
	@code=0; trap 'docker compose -f infra/docker-compose.e2e.yml down --volumes --remove-orphans' EXIT; docker compose -f infra/docker-compose.e2e.yml up --build --abort-on-container-exit --exit-code-from e2e e2e || code=$$?; exit $$code

lint:
	docker compose run --build --rm --no-deps quality python -m ruff check --no-cache app tests alembic /workspace/ml/src /workspace/ml/tests
	docker compose run --build --rm --no-deps quality python -m ruff format --no-cache --check app tests alembic /workspace/ml/src /workspace/ml/tests

lint-web:
	cd apps/web && npm run lint
	cd apps/web && npm run format:check

format:
	docker compose run --build --rm --no-deps quality python -m ruff check --no-cache app tests alembic /workspace/ml/src /workspace/ml/tests --fix
	docker compose run --build --rm --no-deps quality python -m ruff format --no-cache app tests alembic /workspace/ml/src /workspace/ml/tests

format-web:
	cd apps/web && npm run format

api-types:
	cd apps/web && npm run api:types
