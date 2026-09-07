#!/bin/sh

set -eu

compose_file="infra/docker-compose.e2e.yml"
project=""
scenario=""
browser_project=""
stack_active=0

compose() {
    MSYS_NO_PATHCONV=1 docker compose --project-name "$project" --file "$compose_file" \
        --profile lifecycle "$@"
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
        compose logs --no-color e2e-lifecycle-api e2e-lifecycle-web || true
    fi
    teardown || true
    exit "$code"
}

handle_signal() {
    trap - EXIT HUP INT TERM
    teardown || true
    exit 130
}

control() {
    compose run --rm --no-deps \
        -e STAGE8G_SCENARIO="$scenario" \
        e2e-lifecycle-control \
        python -m tests.fixtures.e2e_lifecycle "$@"
}

browser_phase() {
    phase="$1"
    compose run --rm --no-deps \
        -e STAGE8G_SCENARIO="$scenario" \
        -e STAGE8G_PHASE="$phase" \
        -e STAGE8G_BROWSER_PROJECT="$browser_project" \
        e2e-lifecycle-browser
}

stop_serving() {
    compose stop e2e-lifecycle-web e2e-lifecycle-api
}

start_serving() {
    E2E_LIFECYCLE_ARTIFACT_PATH="$1"
    export E2E_LIFECYCLE_ARTIFACT_PATH
    compose up --detach --wait --force-recreate --no-deps \
        e2e-lifecycle-api e2e-lifecycle-web
}

run_scenario() {
    scenario="$1"
    browser_project="$2"
    operator_mode="$3"
    reconsent_after_invalidation="$4"
    project="gamelens-ai-e2e-lifecycle-$browser_project-$scenario-$$"

    export STAGE8G_SCENARIO="$scenario"
    unset E2E_LIFECYCLE_ARTIFACT_PATH || true
    compose config --quiet
    compose build e2e-setup e2e-lifecycle-web e2e-lifecycle-browser
    stack_active=1

    compose up e2e-lifecycle-evidence-init
    start_serving ""
    control cohort
    browser_phase prepare
    control link
    stop_serving

    control audit
    control build previous
    control validate previous
    control advance
    control audit
    control build current
    control validate current
    control ready

    if [ "$operator_mode" = "operator" ]; then
        start_serving "/tmp/gamelens-e2e/artifact-set/collaborative-lifecycle-previous-v1"
        browser_phase previous
        stop_serving
    fi
    start_serving "/tmp/gamelens-e2e/artifact-set/collaborative-lifecycle-current-v1"
    browser_phase ready

    if [ "$scenario" = "contribution-withdrawal" ]; then
        control private-transition withdraw-contribution
        control assert-invalidated
        control private-transition regrant-contribution
    elif [ "$scenario" = "reconsent" ]; then
        control private-transition arrange-outdated-consent
        control assert-invalidated
    fi

    browser_phase transition
    control assert-invalidated
    control assert-transition

    if [ "$reconsent_after_invalidation" = "reconsent" ]; then
        control private-transition arrange-outdated-consent
        browser_phase reconsent
        control assert-invalidated
        control assert-transition
    fi

    stop_serving
    start_serving "/tmp/gamelens-e2e/artifact-set/collaborative-lifecycle-current-v1"
    browser_phase restart

    if [ "$operator_mode" = "operator" ]; then
        control operator-cleanup
        control final --operator
    else
        control final
    fi

    teardown
    printf '%s\n' "Stage 8G lifecycle scenario passed: $browser_project/$scenario"
}

trap cleanup EXIT
trap handle_signal HUP INT TERM

run_scenario preference-removal chromium operator reconsent
run_scenario feedback-removal chromium standard none
run_scenario contribution-withdrawal chromium standard none
run_scenario clear-data chromium standard none
run_scenario clear-data firefox-smoke standard none
run_scenario reconsent webkit-smoke standard none

trap - EXIT HUP INT TERM
printf '%s\n' "Disposable collaborative lifecycle workflow passed"
