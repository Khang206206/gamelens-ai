#!/bin/sh

set -eu

. infra/e2e-ownership.sh

compose_file="infra/docker-compose.e2e.yml"
project="gamelens-ai-e2e-live-source-$$"
stack_active=0

compose() {
    docker compose --project-name "$project" --file "$compose_file" \
        --profile live-source "$@"
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

isolation_snapshot() {
    compose run --rm --no-deps e2e-live-smoke python -m tests.fixtures.e2e_isolation
}
before=$(isolation_snapshot)
# Ordinary operations use only this disposable analogue.
compose up --detach --wait --no-deps e2e-live-api
compose restart e2e-live-api
compose up --detach --wait --no-deps e2e-live-api
compose run --rm --no-deps e2e-setup
compose run --rm --no-deps \
    -e COLLABORATIVE_LIVE_DATA_ENABLED=false \
    -e COLLABORATIVE_CONTRIBUTION_CONSENT_VERSION= \
    e2e-live-smoke python -m pytest \
    tests/unit/test_config.py tests/unit/test_health.py -q -p no:cacheprovider
after=$(isolation_snapshot)
test "$before" = "$after"
printf '%s\n' "$after"
printf '%s\n' "Ordinary operations preserved artifact bytes and registered lineage"

teardown
trap - EXIT HUP INT TERM
printf '%s\n' "Disposable live-source build workflow passed"
