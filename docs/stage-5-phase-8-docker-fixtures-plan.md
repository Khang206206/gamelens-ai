# Stage 5 Phase 8: Docker, Configuration, and Full-Stack Fixtures

- **Status: PLANNED — NOT IMPLEMENTED**
- **Survey date:** 2026-09-05
- **Survey baseline:** `a1aab44` on `feat/stage-5-collaborative-and-hybrid-ranking`
- **Parent scope:** [Stage 5 engineering plan, Section 15](stage-5-collaborative-hybrid-ranking-plan.md#15-implementation-phase-8-docker-configuration-and-full-stack-fixtures)

This document decomposes Phase 8 into independently verifiable commits. It began
as a plan; measured execution evidence is recorded per slice in the ledger below.
The original planning commit changed documentation only and did not run builds
or mutate runtime data. A slice remains **PLANNED — NOT IMPLEMENTED** until its
acceptance gate passes and its implementation commit is recorded.

## 1. Survey findings and inherited boundaries

| Inspected source | Current behavior and consequence for Phase 8 |
| --- | --- |
| [Parent plan, Phases 5–7](stage-5-collaborative-hybrid-ranking-plan.md) | Artifact loading/readiness, hybrid orchestration, public response/event projection, and guarded operator lifecycle already exist. Reuse them; do not reimplement ranking or reopen the Stage 6 quality evaluation. |
| [Root Compose](../docker-compose.yml), [environment example](../.env.example), [Settings](../apps/api/app/core/config.py) | Separate content/collaborative paths and default-off live-data/fixture gates exist. Settings also has `collaborative_live_promotion_enabled`, which root Compose and the example do not expose. The example still says serving does not load the collaborative artifact, although loading now exists. Audit wiring and comments before adding settings. |
| [Makefile](../Makefile) | Content commands use `model-builder`; collaborative fixture wrappers use the `quality` service. Live audit and direct Phase 7 lifecycle commands already exist. Preserve wrapper meanings and make operator commands explicit. |
| [API Dockerfile](../apps/api/Dockerfile), [effective build allowlist](../apps/api/Dockerfile.dockerignore), [root ignore file](../.dockerignore) | Image copies API, ML source, API tests, and catalog, but no `data/fixtures`. Root artifacts and external payloads are excluded. A fresh fixture builder needs a deliberate read-only fixture input; a local quality bind mount is not evidence that the shipped image has it. |
| [E2E Compose](../infra/docker-compose.e2e.yml) | Disposable database → migrate/catalog seed → owner init → content build → API → exact-host web → Playwright. Only content is built; no separate collaborative validation gate or lineage cohort exists. API artifact mount is already read-only. |
| [Operator safety](../apps/api/app/commands/operator_safety.py), [artifact commands](../apps/api/app/commands/collaborative_artifact.py) | Destructive test actions require settings/process `ENVIRONMENT=test`, exact reset opt-in, a database ending `_test`, and an allowed host such as `test-db`. Cleanup also requires an artifact set strictly below the system temporary directory. Existing E2E uses `gamelens_e2e`, `e2e-db`, and `/artifacts`, so it cannot simply reuse cleanup commands. |
| [Committed interaction fixture](../data/fixtures/README.md), [snapshot contract](../ml/src/gamelens_recommender/interaction_snapshot.py) | JSON fixture has 12 synthetic profiles, 36 expected edges, and 6 games. Current activation minima are 10 users, 20 edges, 5 items, with support minima of 2. This fixture produces `source_kind=fixture`; it has no live contributor registry. |
| [Live promotion tests](../apps/api/tests/integration/test_stage_5_live_build_promotion.py), [lifecycle handoff](../apps/api/tests/integration/test_stage_5_lifecycle_handoff.py) | Existing disposable PostgreSQL tests provide a separate synthetic cohort, real contribution rows, immutable live builds, revisions, invalidation, rollback checks, and cleanup. These are references for a reusable test harness, not browser evidence or an approved real cohort. |
| [Session routes](../apps/api/app/api/v1/routes/anonymous_sessions.py) | Public personalization consent/re-consent and clear-data exist. No public route grants collaborative contribution consent. Browser tests must not invent such a route or silently grant contribution rights through personalization. |
| [Playwright configuration](../apps/web/playwright.config.ts), [persistence tests](../apps/web/e2e/persistence.spec.ts) | Tests are fully parallel by default. Chromium runs the full suite; Firefox/WebKit run only `*.smoke.spec.ts`. Some existing failure/re-consent scenarios intercept requests; these are not proof of a real database lifecycle transition. |

The inherited migration head is `0011_stage_5_lifecycle_guard`. No migration,
ranking-policy change, public consent feature, external dataset ingestion,
production approval, scheduler, or deployment automation is planned in Phase 8.
If a focused gate reveals a defect outside the slice, document the failing
contract and revise scope explicitly instead of weakening an assertion.

## 2. Two test modes and the meaning of live build

| Mode | Input and authority | What it proves | What it cannot prove |
| --- | --- | --- | --- |
| Guarded fixture | Committed project-authored JSON; `ENVIRONMENT=test` and explicit `COLLABORATIVE_ALLOW_TEST_FIXTURE=true`; live gates off | Offline deterministic bundle, loader, ready hybrid response, UI evidence, optional-component fallback | Contributor registration, withdrawal/deletion invalidation, or live-source authorization |
| Disposable database lifecycle | Project-authored cohort inserted only by an explicit guarded test helper into tmpfs PostgreSQL; separate test contribution rows; live extraction/promotion gates explicitly enabled | Real `--source live` snapshot/build/registration and lifecycle behavior over synthetic test rows | Permission to use development/production users, product contribution consent, or ranking quality |

Do not relabel a fixture bundle as live, edit its manifest to create readiness,
or register fixture profiles as a live build. A database-derived bundle really
uses `source_kind=live`, while the run record must still identify the cohort as
synthetic test data. Its authority exists only inside that disposable scenario.

“Docker live build” below means executing real image builds and containers.
“Live-source build” means the existing `build --source live` command against
guarded PostgreSQL. The latter is unnecessary for ordinary fixture UI tests but
mandatory before accepting contributor lifecycle browser tests. Neither was run
by the original planning commit; completed-slice execution is recorded below.

## 3. Commit and dependency map

Each row is one future commit containing that slice's implementation, focused
tests, and command notes. It must be runnable using completed prerequisites,
without relying on a later slice or leaving intentionally failing tests.
Implementation is sequential by default; independent branches below describe
debugging boundaries, not a requirement to delegate work.

| Slice | Boundary | Depends on | Intended commit |
| --- | --- | --- | --- |
| 8A | Configuration and explicit command wiring | Verified Phase 7 | `chore(infra): align collaborative configuration and commands` |
| 8B | Guarded PostgreSQL cohort and scenario helper | 8A | `test(api): add disposable collaborative lifecycle fixtures` |
| 8C | Two-artifact fixture Compose topology | 8A | `feat(infra): add guarded collaborative fixture stack` |
| 8D | Real hybrid browser acceptance | 8C | `test(web): verify full-stack hybrid recommendations` |
| 8E | Real optional-component fallback acceptance | 8C | `test(web): verify full-stack collaborative fallback` |
| 8F | Explicit database-derived build and registry topology | 8B, 8C | `test(infra): add disposable live-source build workflow` |
| 8G | Browser invalidation, re-consent, clear-data, and rollback | 8D, 8E, 8F | `test(e2e): verify collaborative lifecycle transitions` |
| 8H | Container isolation, teardown, and combined phase gate | 8A–8G | `test(infra): verify phase 8 isolation and handoff` |
| 8I | Final documentation reconciliation | Passing 8H | `docs: record phase 8 verification and reconcile workflows` |

8B and 8C can be debugged separately after 8A. 8D and 8E can be accepted
separately after 8C. No browser acceptance should absorb a broken builder or
registry gate: diagnose those at 8C/8F first.

## 4. Slice acceptance contracts

### 8A — Configuration and explicit commands

**Status: IMPLEMENTED — VERIFIED (2026-09-06).** Depends on Phase 7.

- Scope: `.env.example`, root Compose, `Makefile`, configuration/command notes;
  focused tests in the existing configuration and artifact command suites.
  Modify Settings only if the survey demonstrates a real wiring gap.
- Inventory paths, fixture path, live extraction, contribution version, live
  promotion, and fixture opt-in. Document current frozen limits/policy identities
  from ML contracts as versioned constants, not invented environment knobs for
  changing weights or thresholds. Keep server settings out of `NEXT_PUBLIC_*`.
- Preserve blank collaborative path and default-off gates, separate content
  commands, and fixture-only meanings of current wrappers. Add only explicit
  operator entry points with direct CLI equivalents. Default model service
  invocation must remain help/read-only; startup must not build or promote.
- Acceptance: settings reject invalid gate combinations; fixture access fails
  in development/production; missing live authority/confirmation fails before
  writes; direct CLI help and wrapper arguments match the actual parser. API
  mounts remain read-only. No dependency or migration change is required.
- Gate: focused `test_config.py`, `test_collaborative_artifact_command.py`,
  `test_collaborative_artifact_entrypoint.py`; parse all three Compose files
  with `config --quiet` and inspect wrapper expansion. Real Docker command
  smoke is required if image packaging/entry points change; no live-source
  build is needed for this slice.

### 8B — Disposable cohort and scenario helper

**Status: IMPLEMENTED — VERIFIED (2026-09-06).** Depends on 8A.

- Scope: test-only API fixture/helper modules and focused PostgreSQL tests;
  test fixture provenance notes. Reuse existing seed/cohort contracts without
  adding behavior to `app.db.seed`, startup, migrations, or public routes.
- Implement a bounded explicit setup/control interface for named scenarios:
  create cohort, arrange outdated consent, withdraw test contribution, and
  inspect aggregate registry/event assertions. No HTTP test-control endpoint.
  Connect browser-created sessions to the synthetic cohort through a private
  test channel; do not print tokens, digests, user IDs, or cohort mappings.
- Guard both configured and actual connected database identity before writes.
  Use a `_test` database and allowlisted host; missing test/reset opt-in,
  development target, mismatched connection, or partial setup must fail closed.
  Define deterministic re-run behavior (explicit refusal or bounded idempotence)
  instead of truncating arbitrary data.
- Acceptance: current personalization and separate contribution rows cross the
  frozen support gate; expired/revoked/outdated/negative/pruned examples stay
  excluded. Use a captured database time for relative eligibility; do not freeze
  fixture validity to a calendar date that expires between runs. Public session
  creation/re-consent alone must create no contribution grant.
- Gate: focused disposable PostgreSQL tests for aggregate counts, eligibility,
  refusal paths, repeatability, and private-output checks. A real DB is required;
  building a collaborative live bundle and launching browsers are not.

### 8C — Two-artifact fixture topology

**Status: IMPLEMENTED — VERIFIED (2026-09-06).** Depends on 8A.

- Scope: E2E Compose, narrowly scoped fixture input mounts/build allowlists as
  needed, explicit runner/wrapper, topology probes. Keep the content-only E2E
  route available so the existing Stage 1–4 suite remains independently runnable.
- Add a visibly selected fixture mode: tmpfs DB → migrate/catalog seed → volume
  owner init → explicit content and fixture builders → explicit validation of
  both bundles → API readiness/model status → web → selected browser tests.
  Use fresh immutable output paths; existing targets fail rather than overwrite.
- Mount only committed fixture/catalog inputs read-only. Keep external payloads,
  `.env`, user rows, and generated artifacts out of image contexts. The builder
  writes only disposable artifacts as non-root; API mounts them read-only.
  Root owner init must affect only the newly created disposable volume and exit.
- Resolve lifecycle-compatible test topology now: a project-local `test-db`
  service/alias, database such as `gamelens_e2e_test`, and artifact-set mount such
  as `/tmp/gamelens-e2e/artifact-set`, strictly below `/tmp`. Use the same resolved
  paths in builder, API, and later operators. Preserve existing guards instead
  of broadening host/path allowlists to fit the old topology.
- Preserve `gamelens.test` exact-host cookie/CORS behavior and non-public E2E
  ports. Fixture gates must be explicit and must not inherit local `.env` live
  settings. A failed build/validation prevents this ready-fixture pipeline from
  starting the API; intentional broken-artifact serving belongs to 8E.
- Gate: first required real Docker image build and fresh fixture stack smoke.
  Verify both validators, `/health`, `/api/v1/models/status`, read-only API write
  refusal, non-root builder identity, immutable-target refusal, and explicit
  teardown. Repeat a fresh fixture build to compare stable semantic identities.
  No live-source build is needed.

### 8D — Hybrid browser acceptance

**Status: IMPLEMENTED — VERIFIED (2026-09-06).** Depends on 8C.

- Scope: new focused Playwright specs/helpers and only necessary project
  selection. Test real public endpoints and cookies; do not fulfill mocked
  recommendation responses or fake model readiness.
- Acceptance: explicitly consent, save supported preferences, generate saved
  recommendations, and observe `hybrid` mode with nonempty collaborative
  evidence. Compare DOM order with the captured server response, including
  component disclosure and exact contribution reconstruction from the server
  evidence. Exercise supported and cold-start sources, source/dislike exclusion,
  played evidence, reload, and stateless content-only behavior.
- Correlate each successful saved generation with exactly one committed
  `stage-5-v1` event via a bounded test-side assertion; no event becomes a label.
  Do not expose internal database credentials to the browser or web bundle.
- Gate: focused Chromium tests plus a small hybrid `*.smoke.spec.ts` selected by
  Firefox and WebKit. Verify keyboard/focus, accessible disclosure, serious/critical
  axe violations, representative viewport overflow, and honest synthetic wording
  in test documentation. These are functional checks, not quality evidence.
- Requires real fixture containers/browser execution; no live-source build.

### 8E — Optional-component fallback

**Status: IMPLEMENTED — VERIFIED (2026-09-06).** Depends on 8C.

- Scope: isolated scenario configuration, focused API/container probes, browser
  fallback specs. Preserve valid required content while varying only the optional
  collaborative component. Use API recreation for load-time changes because
  components load once; do not mutate files under a running read-only API.
- Matrix: unconfigured/missing path, corrupt/checksum-invalid bundle, expired
  bundle, catalog mismatch, fixture opt-in absent, and unsupported query source.
  Create damaged/expired copies only inside disposable test artifact storage.
  Check development/production fixture rejection separately with valid environment
  security settings so an unrelated settings error cannot masquerade as the gate.
- Acceptance: content health remains available, saved generation reports the
  actual typed fallback reason, and score/order match the exact Stage 4 reference
  for the same request and persisted context. Browser displays no applied
  collaborative evidence; response and committed event agree. Required-content
  failure retains its distinct existing health/failure behavior.
- Gate: container/API probes cover every matrix row; real browsers cover
  representative absent and invalid optional artifacts plus cold start, with
  cross-browser fallback smoke. Compare against the existing Stage 4 scorer/oracle,
  not a second implementation of the same hybrid formula.
- Requires real fixture/fallback stack execution; no live-source build. Registry
  invalidation is deliberately deferred to 8G.

### 8F — Explicit live-source build topology

**Status: IMPLEMENTED — VERIFIED (2026-09-06).** Depends on 8B and 8C.

- Scope: opt-in lifecycle Compose mode and test runner sequencing. Keep pure
  fixture and database-derived modes separate; fixture flag is off in live mode.
- Run guarded cohort setup, read-only `audit --source live`, then explicit
  `build --source live --output <unused-path> --build-id <id>
  --confirm-live-build <id>` with live data, contribution version, and promotion
  gates set only for this disposable run. Values are scenario-specific; these
  placeholders are not ready-to-run commands or production approvals.
- Build separate immutable previous/current collaborative bundles alongside
  content, with a deliberate supported revision change if needed for rollback
  evidence. Validate/inspect and check registered readiness before choosing the
  API's configured path. Selection/recreation is explicit; no mutable active
  symlink, hidden promotion, or runtime training.
- Acceptance: metadata says `live`, retained lineage and revisions match the
  real snapshot, and the run record says synthetic PostgreSQL cohort. Missing
  authority, mismatched confirmation, existing path, or registration failure
  cannot produce a ready half-state. Reuse Phase 7 recovery behavior rather than
  rewriting it. CLI outputs and bundle members contain no contributor identities.
- Gate: this is the first mandatory live-source build on real disposable
  PostgreSQL, in real containers. Run audit/build/validate/inspect/rollback-check
  and HTTP saved-hybrid smoke before any lifecycle browser work. A fixture build,
  prebuilt local artifact, mocked registry, or successful image build is insufficient.

### 8G — Browser lifecycle and operator transitions

**Status: IMPLEMENTED — VERIFIED (2026-09-07).** Depends on 8D, 8E, and 8F.

- Scope: lifecycle browser specs, explicit scenario runner, and guarded helper
  assertions. Serialize scenarios that mutate shared cohort/registry/consent;
  isolate project/DB/artifact state between scenarios and retries. Preserve
  parallel execution for unrelated browser cases.
- Start with ready hybrid. Perform public preference/feedback removal and public
  clear-data for a contributing test session; use an independent observer session
  to prove the next saved generation falls back after invalidation. A fixture-only
  artifact is not a valid oracle for these transitions.
- Arrange actual outdated personalization consent with the guarded helper or a
  controlled server-version scenario; browser must see the real server refusal
  and explicitly re-consent through the existing public route. Old output and
  credentials must not bypass the lifecycle. This must not grant contribution
  consent or resurrect old artifacts. Separate contribution withdrawal/re-grant
  remains a guarded test operation and must be labeled as such, not a UI feature.
- Acceptance: committed removal/withdrawal/deletion invalidates applicable live
  lineage before subsequent serving; the observer receives exact Stage 4 fallback
  and a truthful event while content serving survives. Clear-data clears the
  caller's cookie and saved data while preserving another user's data. Re-consent,
  restart, rollback-check, or recovery cannot revive invalidated history.
- While previous/current are valid, verify explicit valid-only rollback selection
  and API recreation; after invalidation, verify rejection. Then retire an eligible
  non-configured bundle, preview, reject a mismatched confirmation, and clean up
  only the exact confirmed candidate, protecting content/current paths. A fresh
  approved test rebuild, if exercised, uses a new path and re-audited eligible rows.
- Gate: real Chromium lifecycle sequence plus representative re-consent/clear-data
  and hybrid-to-fallback smoke in Firefox/WebKit. Read aggregate DB/event state
  through the private helper. No response interception may serve as lifecycle proof.
  Live-source builds are mandatory at each fresh lifecycle scenario setup, not
  after every user action; any later build must be an explicit runner step.

### 8H — Isolation, teardown, and combined gate

**Status: PLANNED — NOT IMPLEMENTED.** Depends on 8A–8G.

- Scope: focused topology/safety regression checks, explicit runners and retained
  aggregate evidence. Do not add a blanket trainer to broad test collection.
- Acceptance: normal Compose startup, API/web restart, migration, catalog seed,
  and ordinary tests never fit, promote, invalidate, retire, or delete derived
  artifacts as a hidden side effect. Probe on disposable analogues and compare
  artifact hashes/registry state; never reset the persistent development database.
- Verify image contexts, non-root runtime, builder/API write boundaries, secrets
  remaining server-only, no token/identity leakage in logs/reports/screenshots,
  no Docker socket mount, and no persistent development data/artifact mount in
  destructive scenarios. Do not collect secret-expanded Compose configuration.
- Teardown must work after pass, failed setup/validation, browser failure, and
  interrupted run: remove only the recorded E2E project's containers/network/
  disposable volumes. Capture resource ownership before removal. No global prune,
  root-project `down --volumes`, lifecycle wildcard cleanup, or host artifact delete.
  Command cleanup remains a separate preview/confirmation operation from teardown.
- Gate: `config --quiet` for all Compose definitions and modes; combined API unit,
  ML, PostgreSQL, web type/lint/format/unit/build/OpenAPI drift, current Stage 1–4
  E2E, and new fixture/lifecycle E2E checks. Run a second clean disposable replay
  to verify scenario determinism and cleanup. Compare semantic artifact/ordering
  values; newly captured live cutoff/build identities need not be byte-identical.
- Record actual host/runtime versions, image digests, commands, exit codes,
  counts, durations, artifact sizes/identities, and privacy findings. Verify on
  the available supported Docker host; identify untested platforms explicitly.
  No extrapolation from Linux container UID checks to untested host filesystems.
- This gate requires real Docker builds and both fixture and live-source runs.
  It is the Phase 8 handoff; the exhaustive release/security/license/coverage and
  acceptance inventory still belongs to Phase 9, with release docs in Phase 10.

### 8I — Documentation reconciliation and phase handoff

**Status: PLANNED — NOT IMPLEMENTED.** Depends on passing 8H.

- Scope: documentation only; one separate final docs commit. Reconcile against
  the committed implementation and retained run evidence, not this plan's intended
  filenames, commands, or anticipated outcomes.
- Required comparison inventory:

  | Documents | Compare with |
  | --- | --- |
  | Root/API/ML/web/infra READMEs and `scripts/README.md` | Actual wrappers and direct CLI parsers; working directory/shell syntax; topology, mounts, explicit setup/build/validation, scenario selection, failure/teardown behavior |
  | `data/README.md`, `data/fixtures/README.md` | Exact synthetic cohort provenance, JSON-vs-database source distinction, eligibility/authority, output privacy and fixture isolation |
  | `docs/architecture.md`, `docs/data-model.md`, `docs/recommendation-design.md` | Actual component loading, registry/invalidation, one-time artifact selection, unchanged schema head and scoring/response/event contracts |
  | `docs/roadmap.md`, parent plan Sections 15, 18, 21–23, and this slice ledger | Measured Phase 8 completion, exact commits/commands/deviations, remaining Phase 9/10 gates, provisional Stage 6 handoff |
  | Configuration descriptions throughout docs | Actual `.env.example`, Settings, Compose values, frozen ML constants; no stale “serving does not load it yet”, fictional limits, or missing gate descriptions |

- For each item, record corrected or reviewed/no-change with a source reference.
  Configuration fixes belong in the owning implementation slice before 8H; do not
  silently change configuration in this docs-only commit. Keep Stage 5 completion
  and parent Section 23 pending; Phase 8 does not finalize Stage 6 evidence.
- Gate: check local links, formatting, `git diff --check`, commands against parser
  and runner definitions, and every numerical claim against logs. Replay changed
  command instructions only when the recorded 8H invocation does not establish
  their correctness. No new live-source build solely to edit prose.

## 5. Execution and evidence rules

The following existing read-only validation commands are useful starting points
for implementation. They are not recorded as executed by this planning commit:

```powershell
docker compose --profile quality --profile source-audit config --quiet
docker compose -f infra/docker-compose.test.yml config --quiet
docker compose -f infra/docker-compose.e2e.yml config --quiet
git diff --check
```

Focused Python suites use the existing `quality` service for API-unit/ML tests
and `test-api` with `--run-integration -m integration` for guarded PostgreSQL
tests. Existing combined entry points are `make test`, `make test-ml`,
`make test-integration`, `make test-web`, `make test-web-e2e`, and `make lint`.
New mode/service/spec names are proposals until their owning slice implements
and documents direct equivalents. Validate PowerShell instructions separately
from POSIX environment assignments and Make shell recipes.

Before each slice commit: run its focused gate, inspect the diff, record exact
command/results and any deviation, then commit only that slice. Run broader
tests when a shared boundary changes or at 8H; do not repeat expensive live-source
builds for unrelated prose or UI assertions. If a gate fails, fix within its
owner and rerun it before starting dependent work.

For every completed slice append: commit ID, tested revision, command and mode,
pass/fail evidence, artifact/registry identities when relevant, limitations, and
docs impact. Do not prefill counts or mark a slice verified from inherited Phase
7 logs. The current ledger is:

| Slice | Status | Implementation commit | Verification |
| --- | --- | --- | --- |
| 8A | IMPLEMENTED — VERIFIED | `e19ea9f` | Configuration/command and Compose gates passed; see the record below. |
| 8B | IMPLEMENTED — VERIFIED | `53c112b` | Guarded disposable PostgreSQL cohort gate passed; see the record below. |
| 8C | IMPLEMENTED — VERIFIED | `44d070d` | Two-artifact fixture topology passed two fresh deterministic runs; see the record below. |
| 8D | IMPLEMENTED — VERIFIED | `7f8cf1b` | Real hybrid Chromium and cross-browser smoke passed; see the record below. |
| 8E | IMPLEMENTED — VERIFIED | `4711979` | Full optional-component fallback matrix and browsers passed; see the record below. |
| 8F | IMPLEMENTED — VERIFIED | `4769d5d` | Disposable PostgreSQL/live-source gate passed; see the record below. |
| 8G | IMPLEMENTED — VERIFIED | this commit | Six isolated live lifecycle scenarios passed; see the record below. |
| 8H | PLANNED — NOT IMPLEMENTED | — | Not run |
| 8I | PLANNED — NOT IMPLEMENTED | — | Not run |

### Slices 8A–8E verification record — 2026-09-06

- **Tested tree:** `34df2b0`, with a clean worktree before verification. The
  implementation commits remain the owning revisions listed in the ledger.
- **8A — `e19ea9f`:** configuration and direct command wiring expose separate
  content/collaborative paths plus explicit live, contribution-version,
  promotion, and fixture gates. Invalid combinations and unsafe fixture/live
  invocations remain fail-closed; default service behavior is read-only and API
  artifact mounts remain read-only. Root, test, and E2E Compose definitions all
  parsed successfully.
- **8B — `53c112b`:** the named synthetic cohort crossed the frozen support gate
  in real disposable PostgreSQL while expired, revoked, outdated, negative, and
  pruned rows stayed excluded. Configured and connected database guards,
  partial/repeated setup behavior, public-versus-contribution consent separation,
  aggregate inspection, and private-output checks passed. The current focused
  file also contains the later bounded 8F revision-control regression, so its
  measured result is 8 tests rather than the original slice-only count.
- **8C — `44d070d`:** the runner built real API, web, and Playwright images and
  twice created a fresh tmpfs PostgreSQL → migration/catalog seed → volume owner
  init → content/fixture build → validation → ready API/web stack. Builders ran
  as UID 1000, existing content and collaborative targets were refused, and the
  serving API rejected artifact writes. Both runs produced the same semantic
  identities: content fingerprint
  `1a304ac3686742022ef41828bf48467412e34bd0e882c9b428cc723a5e2685e1`,
  fixture build
  `stage5-fixture-22197350a7b9d5316a98a14f7a819f64a5aef98c879e26a1ec597927c9af60b9`,
  and interaction fingerprint
  `d2ec587ef4e06eeaaf918447e58d8c233840575a33299556eb9765b786a1c003`.
  The collaborative bundle retained 12 contributors, 36 positive edges, and 6
  items, with `quality_evidence=false`.
- **8D — `7f8cf1b`:** each fresh fixture run passed four focused Chromium hybrid
  cases and one Chromium/Firefox/WebKit smoke case. Assertions covered supported
  and cold-start sources, dislike/source exclusion, played evidence, reload,
  stateless content-only behavior, exact DOM/server order, contribution/edge
  reconstruction, keyboard/focus, axe, and viewport behavior. Event evidence
  recorded eight exactly-once `hybrid` generations per run and exposed neither
  database credentials nor identity fields to browser evidence.
- **8E — `4711979`:** container/API probes passed `not_configured`,
  `artifact_missing`, `artifact_corrupt`, `artifact_expired`, `catalog_stale`,
  `fixture_not_allowed`, and `no_supported_sources`; every saved fallback matched
  the exact Stage 4 score/order oracle and committed a matching event. Separate
  development/production fixture rejection passed with valid security settings.
  Chromium passed representative missing/corrupt browser cases, Firefox/WebKit
  passed cold-start smoke, and missing required content retained its distinct
  HTTP 503 behavior without committing an event.

| Verification command | Result |
| --- | --- |
| `docker compose run --build --rm --no-deps quality python -m pytest tests/unit/test_config.py tests/unit/test_collaborative_artifact_command.py tests/unit/test_collaborative_artifact_entrypoint.py tests/unit/test_e2e_fixture_topology.py tests/unit/test_e2e_hybrid_event_evidence.py tests/unit/test_e2e_fallback_topology.py -q -p no:cacheprovider` | 89 passed in 35.15s. |
| `docker compose -f infra/docker-compose.test.yml run --rm test-api python -m pytest --run-integration -m integration tests/integration/test_stage_5_disposable_lifecycle_fixture.py -q -p no:cacheprovider` | 8 passed in 13.05s against real disposable PostgreSQL. |
| `sh infra/run-e2e-fixture.sh` | Passed two fresh deterministic fixture runs, the hybrid browser suites, the complete fallback matrix, event/privacy probes, and project-local teardown. |
| Root Compose with `quality`/`source-audit`, test Compose, and E2E Compose with `fixture`/`fallback`, each using `config --quiet` | Passed. |
| `sh -n infra/run-e2e-fixture.sh` | Passed. |

GNU Make was unavailable on the host, so the documented underlying Docker
commands were invoked directly without reducing test scope. Compose parsing
returned exit code 0 while the restricted shell warned that the host Docker
client configuration file was unreadable; real escalated Docker builds and
containers ran successfully. These are functional fixture results, not ranking
quality evidence or production-data authority. Native non-Linux-container host
behavior, live-source lifecycle transitions, invalidation, re-consent,
clear-data, retirement, and the combined isolation/handoff gate remain deferred
to 8G–8H; the separately verified live-source build is recorded under 8F below,
and broad documentation reconciliation remains 8I.

### Slice 8F verification record — 2026-09-06

- **Implementation commit and tested tree:** `4769d5d`
  (`test(infra): add disposable live-source build workflow`).
- **Mode and authority:** explicit `live-source` Compose profile against the
  project-owned synthetic cohort in disposable `gamelens_e2e_test` PostgreSQL;
  fixture access remained off and live promotion authority was limited to the
  guarded build/recovery probes.
- **Artifact and registry evidence:** immutable builds
  `stage8f-live-previous-v1` and `stage8f-live-current-v1` were registered
  `active` at revisions 224 and 225. Each retained 12 contributor lineages, both
  matched the real extracted snapshot fingerprint, and the previous build
  passed rollback readiness after Phase 7 orphan recovery.
- **Failure and privacy evidence:** missing live authority, mismatched
  confirmation, an existing target, and a real PostgreSQL registry insertion
  rejection all failed closed. The recovery result was `orphan_registered`;
  CLI/run records and bundle structure exposed no contributor token, digest, or
  user identifier.
- **Serving evidence:** the API selected the current bundle only after
  validation, inspection, registry, lineage, and rollback checks. Its artifact
  mount rejected writes. Saved recommendation generation returned `hybrid` with
  live collaborative evidence, committed exactly one matching `stage-5-v1`
  event, created no contribution grant, and removed the disposable session/event
  during cleanup.

| Verification command | Result |
| --- | --- |
| `sh infra/run-e2e-live-source.sh` | Passed the real image/container, audit/build/recover/validate/inspect/rollback, registry, HTTP smoke, and project-local teardown workflow. |
| `docker compose -f infra/docker-compose.test.yml run --rm test-api python -m pytest --run-integration -m integration tests/integration/test_stage_5_disposable_lifecycle_fixture.py -q -p no:cacheprovider` | 8 passed in 13.57s. |
| `docker compose run --build --rm --no-deps quality python -m pytest tests/unit -q -p no:cacheprovider` | 483 passed in 54.40s. |
| `docker compose run --build --rm --no-deps quality python -m ruff check --no-cache app tests alembic /workspace/ml/src /workspace/ml/tests` | Passed. |
| `docker compose run --build --rm --no-deps quality python -m ruff format --no-cache --check app tests alembic /workspace/ml/src /workspace/ml/tests` | 203 files already formatted. |
| Root Compose with `quality`/`source-audit`, test Compose, and E2E Compose with `live-source`, each using `config --quiet` | Passed. |
| `sh -n infra/run-e2e-live-source.sh` and `git diff --cached --check` | Passed. |

Implementation used direct Docker commands because GNU Make and host `pytest`
were unavailable; this did not reduce the planned test scope. An initial HTTP
smoke selected a preference without supported collaborative evidence, and an
initial unit run lacked the new runner's read-only quality mount. Both defects
were corrected in `4769d5d`, followed by clean full reruns. Browser lifecycle,
invalidation, re-consent, clear-data, retirement, cross-platform claims, and the
broad documentation reconciliation remain explicitly deferred to 8G–8I. This
record does not grant production-data authority or provide ranking-quality
evidence.

### Slice 8G verification record — 2026-09-07

- **Implementation commit and tested tree:** this atomic commit; the final hash
  is reported from Git after commit creation. The complete lifecycle workflow
  ran before Ruff-only formatting, followed by green unit, integration, lint,
  format, and focused topology reruns on the final tree.
- **Mode and isolation:** the explicit `lifecycle` profile ran six serialized,
  fresh Compose projects. Each project owned its tmpfs PostgreSQL database,
  immutable artifact volume, private browser-evidence volume, two live-source
  builds, API/web containers, and browser container, then removed those resources
  with project-local `down --volumes --remove-orphans`.
- **Browser and serving evidence:** 26 no-retry one-test Playwright phases passed:
  Chromium covered preference removal, feedback removal, contribution withdrawal,
  clear-data, valid previous/current selection, re-consent after invalidation,
  restart, rollback, retirement, and cleanup; Firefox repeated clear-data; WebKit
  repeated real outdated-consent refusal/re-consent. Requests used the real
  exact-host API and web containers without response interception.
- **Artifact and lifecycle evidence:** every fresh project audited and built
  live PostgreSQL data twice. Builds retained 13 contributors; ordinary scenarios
  used revisions 231/232, while feedback setup used 235/236. Committed transitions
  invalidated both registered lineages before the observer's next saved request.
  Across scenarios, the private helper verified 19 observer generation IDs as
  exactly-once `stage-5-v1` events with truthful mode/reason, and the independent
  observer retained its saved data without receiving contribution consent.
- **Consent, deletion, and operator evidence:** clear-data removed only the
  contributor session, cookie, preferences, feedback, and contribution authority;
  public re-consent restored personalization authority but never revived lineage
  or missing preferences. Guarded contribution re-grant remained private. The
  operator scenario rejected post-invalidation rollback/recovery and mismatched
  cleanup confirmation, retired only the eligible unconfigured previous build,
  removed exactly that bundle, and preserved the configured current and content
  paths.

| Verification command | Result |
| --- | --- |
| `sh infra/run-e2e-lifecycle.sh` | Exit 0 in approximately 17m12s; all six fresh PostgreSQL/live-build/browser scenarios and exact project-local teardowns passed. |
| `docker compose run --build --rm --no-deps quality python -m pytest tests/unit -q -p no:cacheprovider` | 487 passed in 54.29s. |
| `docker compose -f infra/docker-compose.test.yml run --rm test-api python -m pytest --run-integration -m integration tests/integration/test_stage_5_disposable_lifecycle_fixture.py -q -p no:cacheprovider` | 8 passed in 15.68s against disposable PostgreSQL; the test project was then removed. |
| Full Ruff check and format check over API/ML sources and tests | Passed; 205 files were already formatted. |
| Web TypeScript, ESLint, Prettier, and Vitest | Passed; 12 files / 86 tests passed in 39.20s. |
| Root Compose with `quality`/`source-audit`, test Compose, and E2E Compose with `lifecycle`, each using `config --quiet` | Passed. |
| `sh -n infra/run-e2e-lifecycle.sh` and `git diff --check` | Passed. |

GNU Make was unavailable on the Windows host, so the documented direct POSIX
runner was used without reducing scope. Git Bash path conversion required the
runner to set `MSYS_NO_PATHCONV=1`; browser project selection therefore remains
in the Compose service command rather than a dynamically supplied `/bin/sh`
argument. Review found and corrected the corresponding topology assertion before
the clean 487-test rerun. The project-authored cohort remains functional test data,
not recommendation-quality evidence or production contribution authority. Slice
8H isolation/combined-handoff work and slice 8I broad documentation reconciliation
remain explicitly unstarted.

Phase 8 exits only when a fresh isolated stack reproducibly builds and validates
both artifact types, serves hybrid, invalidates a real registered test build,
serves exact fallback, exercises real re-consent/clear-data boundaries, and tears
down safely, with all slice gates and the final documentation comparison recorded.
