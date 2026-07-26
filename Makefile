.PHONY: help config build up down logs api migrate seed test test-integration lint format

help:
	@echo "GameLens AI Stage 1 commands"
	@echo "  make config  Validate development and test Compose without printing secrets"
	@echo "  make build   Build the API development image"
	@echo "  make up      Start PostgreSQL and API in the background"
	@echo "  make down    Stop services without deleting the database volume"
	@echo "  make logs    Follow PostgreSQL and API logs"
	@echo "  make api     Run PostgreSQL and API in the foreground"
	@echo "  make migrate Upgrade the development database to Alembic head"
	@echo "  make seed    Load deterministic development catalog data"
	@echo "  make test    Run the fast unit and contract suite"
	@echo "  make test-integration  Run tests against disposable PostgreSQL"
	@echo "  make lint    Run Ruff lint and formatting checks"
	@echo "  make format  Apply Ruff fixes and formatting"

config:
	docker compose --profile quality config --quiet
	docker compose -f infra/docker-compose.test.yml config --quiet

build:
	docker compose build api

up:
	docker compose up --build -d db api
	docker compose ps

down:
	docker compose down

logs:
	docker compose logs -f db api

api:
	docker compose up --build api

migrate:
	docker compose run --build --rm api python -m alembic upgrade head

seed:
	docker compose run --build --rm api python -m app.db.seed

test:
	docker compose run --build --rm --no-deps quality python -m pytest tests/unit -q -p no:cacheprovider

test-integration:
	@code=0; trap 'docker compose -f infra/docker-compose.test.yml down --remove-orphans' EXIT; docker compose -f infra/docker-compose.test.yml up -d test-db && docker compose -f infra/docker-compose.test.yml run --build --rm test-api || code=$$?; exit $$code

lint:
	docker compose run --build --rm --no-deps quality python -m ruff check --no-cache app tests alembic
	docker compose run --build --rm --no-deps quality python -m ruff format --no-cache --check app tests alembic

format:
	docker compose run --build --rm --no-deps quality python -m ruff check --no-cache app tests alembic --fix
	docker compose run --build --rm --no-deps quality python -m ruff format --no-cache app tests alembic
