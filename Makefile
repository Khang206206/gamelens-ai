.PHONY: help config up down logs

help:
	@echo "GameLens AI Stage 0 commands"
	@echo "  make config  Validate and render the Docker Compose configuration"
	@echo "  make up      Start the local PostgreSQL service"
	@echo "  make down    Stop the local PostgreSQL service"
	@echo "  make logs    Follow PostgreSQL service logs"

config:
	docker compose config

up:
	docker compose up -d
	docker compose ps

down:
	docker compose down

logs:
	docker compose logs -f db
