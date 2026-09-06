#!/bin/sh

set -eu

compose_file="infra/docker-compose.e2e.yml"
project="gamelens-ai-e2e-live-source-$$"
stack_active=0

compose() {
    docker compose --project-name "$project" --file "$compose_file" \
        --profile live-source "$@"
}

teardown() {
    if [ "$stack_active" -eq 1 ]; then
        compose down --volumes --remove-orphans
        stack_active=0
    fi
}

cleanup() {
    code=$?
    trap - EXIT HUP INT TERM
    if [ "$code" -ne 0 ] && [ "$stack_active" -eq 1 ]; then
        compose ps --all || true
        compose logs --no-color || true
    fi
    teardown || true
    exit "$code"
}

handle_signal() {
    trap - EXIT HUP INT TERM
    teardown || true
    exit 130
}

trap cleanup EXIT
trap handle_signal HUP INT TERM

compose config --quiet
compose build e2e-setup
stack_active=1
compose up --detach --wait e2e-live-api
compose logs --no-color \
    e2e-live-audit \
    e2e-live-registration-failure \
    e2e-live-previous-recover \
    e2e-live-previous-validate \
    e2e-live-previous-inspect \
    e2e-live-current-model \
    e2e-live-current-validate \
    e2e-live-current-inspect \
    e2e-live-rollback \
    e2e-live-verify
compose run --rm --no-deps e2e-live-smoke

teardown
trap - EXIT HUP INT TERM
printf '%s\n' "Disposable live-source build workflow passed"
