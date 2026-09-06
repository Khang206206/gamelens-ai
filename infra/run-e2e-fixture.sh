#!/bin/sh

set -eu

compose_file="infra/docker-compose.e2e.yml"
project="gamelens-ai-e2e-fixture-$$"
stack_active=0

compose() {
    docker compose --project-name "$project" --file "$compose_file" --profile fixture "$@"
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

compose build e2e-setup e2e-fixture-web e2e-fixture

start_fresh_stack() {
    stack_active=1
    compose up --detach --wait e2e-fixture-web >&2
    compose run --rm --no-deps e2e-test-evidence-init >&2
    compose logs e2e-model-validate e2e-collaborative-validate >&2
    compose run --rm --no-deps e2e-fixture >&2
    compose run --rm --no-deps e2e-fixture-events >&2
    compose run --rm --no-deps e2e-fixture-immutability >&2
}

probe_stack() {
    compose exec --no-TTY e2e-fixture-api \
        python -m tests.fixtures.e2e_fixture_stack runtime
}

start_fresh_stack
first_identity=$(probe_stack)
printf '%s\n' "$first_identity"
teardown

start_fresh_stack
second_identity=$(probe_stack)
printf '%s\n' "$second_identity"

if [ "$first_identity" != "$second_identity" ]; then
    printf '%s\n' "Fixture stack semantic identity changed across fresh builds" >&2
    exit 1
fi

teardown
trap - EXIT HUP INT TERM
printf '%s\n' "Fixture stack passed two fresh deterministic runs"
