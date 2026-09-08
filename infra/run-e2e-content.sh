#!/bin/sh
set -eu
. infra/e2e-ownership.sh
project="gamelens-ai-e2e-content-$$"
stack_active=0
compose() {
    docker compose --project-name "$project" --file infra/docker-compose.e2e.yml "$@"
}
trap cleanup EXIT
trap handle_signal HUP INT TERM
compose build e2e-setup e2e-web e2e
stack_active=1
compose up --detach --wait e2e-web
compose run --rm --no-deps e2e
teardown
