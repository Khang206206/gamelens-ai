#!/bin/sh

set -eu

compose_file="infra/docker-compose.e2e.yml"
project="gamelens-ai-e2e-fixture-$$"
stack_active=0

compose() {
    docker compose --project-name "$project" --file "$compose_file" \
        --profile fixture --profile fallback "$@"
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
    compose run --rm --no-deps e2e-fixture-immutability >&2
}

probe_stack() {
    compose exec --no-TTY e2e-fixture-api \
        python -m tests.fixtures.e2e_fixture_stack runtime
}

run_event_probe() {
    compose run --rm --no-deps e2e-fixture-events >&2
}

scenario_compose() {
    MSYS_NO_PATHCONV=1 \
    E2E_FALLBACK_ARTIFACT_PATH="$scenario_artifact_path" \
    E2E_FALLBACK_ALLOW_TEST_FIXTURE="$scenario_allow_fixture" \
    E2E_FALLBACK_CONTENT_ARTIFACT_PATH="$scenario_content_path" \
    E2E_EXPECTED_FALLBACK_REASON="$scenario_reason" \
        docker compose --project-name "$project" --file "$compose_file" \
        --profile fixture --profile fallback "$@"
}

run_fallback_scenario() {
    scenario_reason=$1
    scenario_artifact_path=$2
    scenario_allow_fixture=$3
    browser_service=$4
    scenario_content_path=/tmp/gamelens-e2e/artifact-set/content-v1

    scenario_compose up --detach --wait --force-recreate --no-deps \
        e2e-fallback-api >&2
    scenario_compose up --detach --wait --force-recreate --no-deps \
        e2e-fallback-web >&2
    scenario_compose run --rm --no-deps e2e-fallback-probe >&2
    if [ "$browser_service" != "none" ]; then
        scenario_compose run --rm --no-deps "$browser_service" >&2
    fi
    scenario_compose rm --stop --force e2e-fallback-web e2e-fallback-api >&2
}

run_required_content_failure() {
    scenario_reason=not_configured
    scenario_artifact_path=""
    scenario_allow_fixture=false
    scenario_content_path=/tmp/gamelens-e2e/artifact-set/missing-content

    scenario_compose up --detach --wait --force-recreate --no-deps \
        e2e-fallback-api >&2
    scenario_compose up --detach --wait --force-recreate --no-deps \
        e2e-fallback-web >&2
    scenario_compose run --rm --no-deps e2e-fallback-probe \
        python -m tests.fixtures.e2e_fixture_stack required-content >&2
    scenario_compose rm --stop --force e2e-fallback-web e2e-fallback-api >&2
}

run_fallback_acceptance() {
    compose run --rm --no-deps e2e-fallback-artifacts >&2
    compose run --rm --no-deps e2e-fixture-development-rejection >&2
    compose run --rm --no-deps e2e-fixture-production-rejection >&2
    compose rm --stop --force e2e-fixture-web e2e-fixture-api >&2

    run_fallback_scenario not_configured "" false none
    run_fallback_scenario artifact_missing \
        /tmp/gamelens-e2e/artifact-set/missing-collaborative true e2e-fallback-browser
    run_fallback_scenario artifact_corrupt \
        /tmp/gamelens-e2e/artifact-set/collaborative-fixture-corrupt true \
        e2e-fallback-browser
    run_fallback_scenario artifact_expired \
        /tmp/gamelens-e2e/artifact-set/collaborative-fixture-expired true none
    run_fallback_scenario catalog_stale \
        /tmp/gamelens-e2e/artifact-set/collaborative-fixture-catalog-mismatch true none
    run_fallback_scenario fixture_not_allowed \
        /tmp/gamelens-e2e/artifact-set/collaborative-fixture-v1 false none
    run_fallback_scenario no_supported_sources \
        /tmp/gamelens-e2e/artifact-set/collaborative-fixture-v1 true e2e-fallback-smoke
    run_required_content_failure
}

start_fresh_stack
first_identity=$(probe_stack)
printf '%s\n' "$first_identity"
run_fallback_acceptance
run_event_probe
teardown

start_fresh_stack
second_identity=$(probe_stack)
printf '%s\n' "$second_identity"
run_event_probe

if [ "$first_identity" != "$second_identity" ]; then
    printf '%s\n' "Fixture stack semantic identity changed across fresh builds" >&2
    exit 1
fi

teardown
trap - EXIT HUP INT TERM
printf '%s\n' "Fixture stack passed two fresh deterministic runs"
