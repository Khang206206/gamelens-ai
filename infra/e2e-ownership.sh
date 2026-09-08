#!/bin/sh
# Shared by explicit disposable runners; never source from development startup.
export MSYS_NO_PATHCONV=1

teardown() {
    if [ "$stack_active" -eq 1 ]; then
        record_ownership || return 1
        compose down --volumes --remove-orphans || return 1
        assert_removed || return 1
        stack_active=0
    fi
}

cleanup() {
    code=$?
    trap - EXIT HUP INT TERM
    teardown || code=1
    exit "$code"
}

handle_signal() {
    trap - EXIT HUP INT TERM
    teardown || exit 1
    exit 130
}

owned_resources() {
    case "$project" in
        gamelens-ai-e2e-?*) ;;
        *) printf '%s\n' 'Refusing non-disposable project ownership' >&2; return 1 ;;
    esac
    docker container ls --all --filter "label=com.docker.compose.project=$project" --format '{{.ID}}' || return 1
    docker network ls --filter "label=com.docker.compose.project=$project" --format '{{.ID}}' || return 1
    docker volume ls --filter "label=com.docker.compose.project=$project" --format '{{.Name}}'
}

record_ownership() {
    resources=$(owned_resources) || return 1
    printf 'E2E ownership project=%s resources=%s\n' "$project" "$resources"
}

assert_removed() {
    resources=$(owned_resources) || return 1
    if [ -n "$resources" ]; then
        printf 'E2E teardown left resources for %s\n' "$project" >&2
        return 1
    fi
    printf 'E2E teardown verified project=%s\n' "$project"
}
