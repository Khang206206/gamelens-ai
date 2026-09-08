#!/bin/sh
# Explicit fault injection into disposable containers; shares production runner traps.
set -eu
. infra/e2e-ownership.sh
mode=${1:?Expected pass, setup, validation, browser, or interrupt}
case "$mode" in pass|setup|validation|browser|interrupt) ;; *) exit 2 ;; esac
project="gamelens-ai-e2e-teardown-$mode-$$"
stack_active=0
compose() {
    docker compose --project-name "$project" --file infra/docker-compose.e2e.yml "$@"
}
trap cleanup EXIT
trap handle_signal HUP INT TERM
stack_active=1
compose up --detach --wait test-db
# Allocate the same disposable volume as the real pipeline before faulting.
compose up --abort-on-container-exit --exit-code-from e2e-artifact-init e2e-artifact-init
case "$mode" in
    setup) compose run --rm --no-deps e2e-setup python -c 'raise SystemExit(41)' ;;
    validation)
        compose run --rm --no-deps e2e-model-validate ;;
    browser)
        compose up --detach --wait e2e-web
        compose run --rm --no-deps e2e node -e '
          const fs = require("fs");
          fs.writeFileSync("e2e/teardown.injected.spec.ts",
            "import { test, expect } from \"@playwright/test\";\n" +
            "test.use({ screenshot: \"off\", video: \"off\", trace: \"off\" });\n" +
            "test(\"injected teardown failure\", async ({ page }) => { " +
            "await page.goto(\"/\"); expect(false).toBe(true); });\n");
          const result = require("child_process").spawnSync("npx",
            ["playwright", "test", "e2e/teardown.injected.spec.ts", "--project=chromium",
             "--workers=1", "--retries=0", "--reporter=line"], { stdio: "inherit" });
          process.exit(result.status ?? 1);
        ' ;;
    interrupt) kill -TERM "$$" ;;
    pass) teardown ;;
esac
