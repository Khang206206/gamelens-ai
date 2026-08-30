# GameLens AI API

The GameLens AI API is a Python 3.12 FastAPI application backed by PostgreSQL
16. It exposes the deterministic catalog, Stage 3 artifact-backed content
recommendations, the verified Stage 4 consented persistence slice, and Stage 5
Phase 5 component readiness/internal saved-ranking orchestration. It never
trains during startup or a request and never fabricates recommendations when a
configured component is unavailable.

The web application in `apps/web` consumes this API through generated
OpenAPI types and a project-owned browser client. Use the repository
[README](../../README.md) for complete db/API/web startup.

The completed
[Stage 3 plan](../../docs/stage-3-content-recommendation-mvp-plan.md) records the
artifact, scoring, contract, and verification decisions. Its anonymous
selection endpoint remains request-scoped and read-only.

The detailed
[Stage 4 feedback-and-persistence plan](../../docs/stage-4-feedback-persistence-plan.md)
is complete and verified. Anonymous identity, preference, temporal feedback,
personalized-event, retention, and revocation contracts are present on the
implementation branch. The Stage 5 Phase 5 handoff passes 311 API unit tests,
98 disposable-PostgreSQL tests, and 331 ML tests with one Windows symlink-
capability skip. Ruff lint/format passes across 165 Python files, generated
OpenAPI types have no drift, and the Docker test stack is removed after the
run. The most recent web/browser acceptance remains the verified Stage 4 run:
76 web tests and 38/38 exact-host browser cases.
The endpoint and command tables below describe the current worktree.

The detailed
[Stage 5 collaborative-and-hybrid plan](../../docs/stage-5-collaborative-hybrid-ranking-plan.md)
has completed implementation Phases 0–5. In addition to the governed snapshot,
fixture artifact, pure scorer/materializers, and hybrid policy, the API now owns
an optional immutable collaborative component, protected live build/contributor
lineage, transactional invalidation, one-row readiness, additive component
status, and internal saved-request orchestration. No HTTP route grants
contribution consent and no approved live build/promotion command exists.
Current personalized HTTP responses and events deliberately remain Stage 4;
Phase 6 will expose the internal hybrid decision as one synchronized response,
`stage-5-v1` event, generated client contract, and browser presentation.

## Responsibilities

The dependency direction is:

```text
route -> application service -> repository/model service -> PostgreSQL/artifact
```

Routes parse HTTP input, services own use cases, repositories own queries,
Pydantic schemas define external contracts, and SQLAlchemy models remain
internal.

Stage 4 adds a distinct protected `/api/v1/me` boundary after explicit consent.
It keeps `POST /api/v1/recommendations` cookie-agnostic and read-only, while
session, preference, feedback, and personalized-recommendation services own
their user-scoped validation, locking, transactions, persistence, and bounded
event writes. Raw anonymous credentials remain in a host-only HttpOnly cookie
and never enter response models, logs, PostgreSQL, or model artifacts.

## Docker-first setup

Run these commands from the repository root:

```powershell
Copy-Item .env.example .env
docker compose build api
docker compose up -d db
docker compose run --build --rm api python -m alembic upgrade head
docker compose run --build --rm api python -m app.db.seed
docker compose --profile model run --build --rm model-builder `
    python -m app.commands.recommendation_artifact build
docker compose --profile model run --rm --no-deps model-builder `
    python -m app.commands.recommendation_artifact validate
docker compose up -d api
docker compose ps
```

Migrations, seed, and model builds are intentionally explicit. Starting the API
does not modify the database schema, catalog, or model artifact.

Verify the running service:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod "http://localhost:8000/api/v1/games?page=1&page_size=5"
Invoke-RestMethod http://localhost:8000/api/v1/models/status
$body = @{
    preferred_genres = @("rpg")
    preferred_platforms = @("linux")
    top_k = 5
} | ConvertTo-Json
Invoke-RestMethod -Method Post `
    -Uri http://localhost:8000/api/v1/recommendations `
    -ContentType application/json -Body $body
Start-Process http://localhost:8000/docs
```

Stop containers without deleting development data:

```powershell
docker compose down
```

## Host Python workflow

Start PostgreSQL from the repository root:

```powershell
docker compose up -d db
Set-Location apps/api
```

Then use Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ../../ml
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m app.db.seed
$env:MODEL_ARTIFACT_PATH = Join-Path `
    (Resolve-Path ../../ml/artifacts) "content-v1-host"
python -m app.commands.recommendation_artifact build
python -m app.commands.recommendation_artifact validate
python -m app
```

The root `.env` is loaded automatically. Its host `DATABASE_URL` uses
`localhost`; Compose injects a separate URL using the `db` service hostname.
The Docker build uses the complete Linux/Python 3.12 dependency set pinned in
`requirements.lock`; the host workflow resolves the platform-appropriate
dependencies from `pyproject.toml` because the container lock includes
Linux-only packages.

The API declares the source-local `gamelens-recommender==0.1.0` distribution;
installing `../../ml` first makes the host dependency graph complete. The root
`.env` uses the container path `/artifacts/content-v1`, so the host workflow
must override it with an absolute Windows path as shown. If that immutable
target already exists, choose a new directory name instead of deleting or
overwriting the active bundle.

## Endpoints

| Method | Path                                      | Purpose                                                        |
| ------ | ----------------------------------------- | -------------------------------------------------------------- |
| GET    | `/health`                                 | Application and PostgreSQL readiness                           |
| GET    | `/api/v1/games`                           | Paginated catalog with search, filters, and sorting            |
| GET    | `/api/v1/games/{game_id}`                 | Full game details and taxonomy                                 |
| GET    | `/api/v1/metadata/genres`                 | Sorted genres                                                  |
| GET    | `/api/v1/metadata/tags`                   | Sorted tags                                                    |
| GET    | `/api/v1/metadata/platforms`              | Sorted platforms                                               |
| GET    | `/api/v1/models/status`                   | Required content state plus additive collaborative component state |
| POST   | `/api/v1/recommendations`                 | Bounded request-scoped recommendations and evidence            |
| POST   | `/api/v1/anonymous-sessions`              | Create or explicitly renew a consented anonymous session       |
| GET    | `/api/v1/me`                              | Read session lifecycle metadata and CSRF token                 |
| DELETE | `/api/v1/me`                              | Withdraw consent and delete all user-owned state               |
| GET    | `/api/v1/me/preferences`                  | Rehydrate canonical saved preferences                         |
| PUT    | `/api/v1/me/preferences`                  | Atomically replace saved preferences                           |
| DELETE | `/api/v1/me/preferences`                  | Clear saved preferences                                        |
| GET    | `/api/v1/me/feedback`                     | Paginate current feedback state                                |
| PUT    | `/api/v1/me/games/{game_id}/feedback`    | Replace one game's current feedback state                      |
| DELETE | `/api/v1/me/games/{game_id}/feedback`    | Clear one game's current feedback state                        |
| POST   | `/api/v1/me/recommendations`              | Rank saved context and commit one bounded event                |
| GET    | `/docs`                                   | Interactive OpenAPI documentation                              |
| GET    | `/openapi.json`                           | Machine-readable OpenAPI contract                              |

Catalog pagination is one-based; `page` is capped at 1,000,000. The default
page size is 20 and the maximum is 100. Supported sort values are
`popularity`, `rating`, `release_date`, and `title`. Filters accept `q`,
`genre`, `tag`, and `platform`; unknown taxonomy slugs return an empty page.

Readiness returns HTTP 200 only when PostgreSQL is reachable, every required
Stage 1 table exists, and Alembic is at the expected head. Otherwise it returns
a typed degraded response with HTTP 503. Recommendation-model readiness is
reported separately by `/api/v1/models/status` and is not part of `/health`.

The recommendation request accepts at most five distinct game IDs, five genre
slugs, ten tag slugs, six platform slugs, and `top_k` from 1 through 20. At
least one game, genre, or tag is required. Unknown references, duplicates,
unknown fields, and invalid bounds return the standard 422 envelope. A missing,
invalid, incompatible, or catalog-stale artifact returns 503. A catalog that
cannot be canonicalized returns the same typed 503 envelope with
`catalog_invalid`. The response includes model identity, rank, deterministic
score components, structured evidence, and explanations grounded in that
evidence. Ranking scores are not probabilities or percentages.

`POST /api/v1/anonymous-sessions` requires the exact configured Origin,
`application/json`, and current consent version `stage-4-v1`. A new session
returns HTTP 201 and sets the 32-byte URL-safe credential only in the host-only
`gamelens_session` cookie. The default cookie path is `/api/v1`, with
`HttpOnly`, `SameSite=Lax`, a fixed 180-day lifetime, and environment-aware
`Secure`; production rejects the development secret, insecure cookies, and
HTTP credentialed origins. PostgreSQL stores only a domain-separated
HMAC-SHA-256 digest. `GET /api/v1/me` returns lifecycle metadata and a derived
CSRF token with `Cache-Control: no-store`, never an internal user ID or raw
credential.

Every protected unsafe request requires the credential cookie, an exact
allowed Origin, and the CSRF value in `X-CSRF-Token`. Credentialed CORS uses an
explicit origin allowlist and the `GET`, `POST`, `PUT`, and `DELETE` methods.
Preference replacement uses the Stage 3 selection bounds and validates all
references before mutation. Feedback exposes canonical current reaction,
played, wishlist, and half-step rating state while retaining superseded rows as
history. `DELETE /api/v1/me` cascades all user-owned preferences,
interactions, and recommendation events and clears the cookie.

`POST /api/v1/me/recommendations` accepts only `top_k` from 1 through 20. It
uses feedback policy `gamelens-feedback-adjustment/1.0.0`, preserves the Stage
3 model/artifact identity, and commits one `stage-4-v1` bounded event before a
successful response. The response correlates through a unique generation ID
and exposes base, affinity, played, policy, model, and data-fingerprint
evidence. The PostgreSQL transaction/event-correlation gate and the 38/38
Docker browser gate pass.

Phase 5 now resolves the optional collaborative component and invokes
`gamelens-hybrid-ranking/1.0.0` inside that same saved-request transaction.
Lifecycle readiness uses database time and at most one live build row from the
same repeatable-read snapshot. The resulting `hybrid` or `stage_4_fallback`
decision is internal: the route still maps an exact Stage 4 result to the
response and `stage-4-v1` event. This intentional handoff prevents a hybrid
HTTP 200 or mislabeled event before Phase 6 changes both contracts together.
The stateless endpoint remains unchanged and never queries collaborative
lineage.

`MODEL_ARTIFACT_PATH` is optional at the settings boundary. Compose passes the
same configured path to the offline builder and API, and mounts `ml/artifacts`
read-only in the API. Without configuration, status is `not_configured`; with a failed load it is
`unavailable`. A valid artifact is loaded and made immutable once during app
construction. Ready status and each recommendation compare its fingerprint
with a `REPEATABLE READ, READ ONLY` catalog snapshot.

To rebuild after a catalog or model change, rotate `.env` to a new path such as
`MODEL_ARTIFACT_PATH=/artifacts/content-v1-r2`, run `make model-build` and
`make model-validate`, and recreate the API. Builder targets intentionally
reject existing directories so an active artifact is never overwritten. The
hardened loader also rejects non-canonical CSR indices, so operators upgrading
an existing Stage 3 bundle must rotate the configured path and rebuild and
validate the artifact rather than modify it in place.

`COLLABORATIVE_ARTIFACT_PATH` is an independent optional path. The API loads
and freezes that artifact once during application construction. A fixture
bundle is accepted only with `ENVIRONMENT=test` and
`COLLABORATIVE_ALLOW_TEST_FIXTURE=true`; development and production reject it.
A structurally valid live artifact is not `ready` without one matching active
registry row and exact build/revision/cutoff/count/consent/fingerprint/validity
facts. Collaborative failure changes only the optional component and falls back
to Stage 4; it does not make required content capability unavailable.

The implemented migration chain is:

```text
0001_initial_schema
  -> 0002_stage_1_integrity_hardening
  -> 0003_stage_4_anonymous_identity
  -> 0004_stage_4_interaction_state
  -> 0005_stage_4_event_contract
  -> 0006_stage_5_collab_contract
  -> 0007_stage_5_artifact_registry
  -> 0008_stage_5_authority_loss
  -> 0009_stage_5_label_changes
```

Readiness expects head `0009_stage_5_label_changes`. The Stage 4 revisions
preserve legacy rows, revoke inaccessible plaintext-key identities without
fabricating consent, add temporal current-state indexes, and version
recommendation events. The legacy replacement is exactly
`md5('legacy-revoked-v1:' || anonymous_key) || lpad(to_hex(id), 32, '0')`,
whose ID suffix guarantees uniqueness. Populated `0002` upgrade and populated
downgrade/re-upgrade pass in PostgreSQL.

The Stage 5 migration grants no contribution consent to existing users. It adds
`collaborative_contribution_consents` and a singleton
`collaborative_data_revision`. Statement triggers advance the revision for
source/catalog mutations but exclude recommendation events. Revisions
`0007`–`0009` add live artifact build/contributor lineage, enforce contributor
authority, maintain aggregate contributor count, record cutoff, and invalidate
affected active builds transactionally when authority or an included positive
label is lost.

## Stage 5 Phase 0–2 offline commands

The default command is a supported refusal and does not create a database
engine:

```powershell
make collaborative-audit
```

It reports `integration_blocked` because
`COLLABORATIVE_LIVE_DATA_ENABLED=false` and the contribution-consent version is
unset. Explicitly enabling those settings permits a read-only aggregate audit,
not a build or serving activation.

The authored fixture requires `ENVIRONMENT=test` plus the explicit gate:

```powershell
make collaborative-fixture-audit
```

Both audit paths write no row-level snapshot or artifact and keep
`approved_live_training_eligibility=false`.

Phase 2 adds a separate fixture-only artifact workflow:

```powershell
make collaborative-build
make collaborative-validate
docker compose --profile quality run --rm --no-deps `
    -e COLLABORATIVE_ALLOW_TEST_FIXTURE=true quality `
    python -m app.commands.collaborative_artifact inspect
```

The build command re-audits the fixture, constructs deterministic sparse
item-item cosine neighborhoods, writes a temporary JSON/NPY bundle, validates it
with the production loader, and atomically promotes it only when the configured
path does not exist. Fixture access requires both `ENVIRONMENT=test` and
`COLLABORATIVE_ALLOW_TEST_FIXTURE=true`. `build` defaults to `--source live`,
which fails closed with `unapproved_live_source` before database access.
`validate` and `inspect` are read-only; both enforce member checksums, schema,
resource, semantic, catalog/lifecycle, and expiry contracts and emit only
aggregate metadata. They bind the artifact to the catalog read from `--catalog`,
which defaults to the canonical seed file.

## Stage 5 Phase 5 lifecycle and orchestration

`GET /api/v1/models/status` preserves the top-level content capability contract
and adds `components.content` plus `components.collaborative`. Collaborative
status is one of `not_configured`, `fixture_only`, `insufficient_data`,
`unavailable`, `stale`, or `ready`; `source_kind` is `fixture`, `live`, or null.
The bounded reason set is `not_configured`, `fixture_not_allowed`,
`insufficient_data`, `artifact_missing`, `artifact_corrupt`,
`artifact_incompatible`, `artifact_stale`, `privacy_invalid`,
`artifact_expired`, `catalog_stale`, and `artifact_retired`.

For a loaded live artifact, readiness performs one indexed registry lookup by
build ID. It verifies active status, zero invalidation epoch, registered
revision, contributor count, consent version, catalog and interaction
fingerprints, cutoff, and validity horizon. A nested savepoint turns a database
readiness failure into fail-closed `artifact_incompatible` fallback without
poisoning the required Stage 4 event transaction.

Migrations `0008` and `0009` make privacy invalidation transactional with the
source change. Authority loss includes contribution withdrawal/version change,
session expiry/revocation, and user deletion. Included-label invalidation
covers removal/change of a positive saved-game preference, like, or qualifying
rating under `gamelens-collaborative-labels/1.0.0`. A new positive after the
artifact cutoff does not invalidate the current artifact; it belongs to a
future build.

The internal hybrid orchestrator additionally maps `no_query_sources`,
`no_supported_sources`, `no_candidate_edges`, and `no_eligible_candidates` to
exact Stage 4 fallback. Phase 6 must expose the decision and same fixed-point
values through both the personalized response and `stage-5-v1` event before any
public hybrid result is allowed.

Errors use one envelope:

```json
{
  "error": {
    "code": "game_not_found",
    "message": "Game 999 was not found"
  }
}
```

## Retention and revocation commands

Retention is explicit and preview-only by default. The configured default
event window is 90 days and the default batch size is 500:

```powershell
make retention-preview
docker compose run --build --rm api python -m app.commands.retention
```

Execution requires explicit timezone-aware event and expired-user cutoffs plus
the exact database-fingerprinted confirmation emitted by preview:

```powershell
python -m app.commands.retention `
    --events-before 2026-01-01T00:00:00Z `
    --expired-before 2026-01-01T00:00:00Z `
    --execute --confirm "<exact preview value>"
```

Bulk session revocation is a separate direct command and also previews unless
`--execute` receives its exact confirmation:

```powershell
python -m app.commands.anonymous_sessions `
    --created-before 2026-01-01T00:00:00Z
```

The cutoff selects the identity-creation cohort, not the most recent consent
timestamp. Re-consent deliberately keeps the original credential digest and
may update `consented_at`, so using creation time ensures an old-secret identity
cannot escape a key-retirement cohort by re-consenting.

Key retirement is a coordinated, sequential operation: quiesce anonymous
session creation and re-consent on the old secret, drain in-flight requests,
record the database-time cutoff, switch issuance to the new secret, then preview
and execute `--created-before` until `remaining` is zero before retiring the old
secret. Stage 4 does not implement online dual-key rotation; allowing old- and
new-secret issuers to overlap invalidates this cutoff procedure.

Neither command runs during startup, migration, seed, model build, ordinary
tests, or teardown. Execute only against a deliberately selected database. The
PostgreSQL suite verifies bounded retention and revocation behavior.

## Quality commands

Fast tests:

```powershell
docker compose run --build --rm --no-deps quality python -m pytest tests/unit -q -p no:cacheprovider
docker compose run --build --rm --no-deps quality python -m pytest /workspace/ml/tests -q -p no:cacheprovider
```

PostgreSQL integration tests use a separate Compose project and an in-memory
`tmpfs` data directory. The database has no published host port:

```powershell
docker compose -f infra/docker-compose.test.yml up -d test-db
try {
    docker compose -f infra/docker-compose.test.yml run --build --rm test-api
} finally {
    docker compose -f infra/docker-compose.test.yml down --remove-orphans
}
```

The test service explicitly selects the `integration` marker, requires the
`--run-integration` opt-in, and injects
`GAMELENS_TEST_DATABASE_URL` plus
`GAMELENS_ALLOW_TEST_DATABASE_RESET=true`. The test guard rejects non-test
database identities before Alembic can reset a schema.

The current Phase 5 handoff passes 311 API unit tests and 98 disposable-
PostgreSQL integration tests. The database suite covers the current migration
head, artifact registry/count constraints, authority and included-label
invalidation, additive model status, same-snapshot orchestration, next-request
privacy/retirement fallback, fail-closed readiness errors, and all inherited
Stage 4 persistence behavior. The full ML regression suite passes 331 tests
with one Windows symbolic-link capability skip. No new diagnostic coverage
percentage was recorded for this phase.

Lint, format, and coverage:

```powershell
docker compose run --build --rm --no-deps quality python -m ruff check --no-cache app tests alembic /workspace/ml/src /workspace/ml/tests
docker compose run --build --rm --no-deps quality python -m ruff format --no-cache --check app tests alembic /workspace/ml/src /workspace/ml/tests
docker compose run --build --rm --no-deps quality python -m pytest tests/unit --cov=app --cov-report=term-missing -p no:cacheprovider
docker compose run --build --rm --no-deps quality python -m ruff check --no-cache app tests alembic --fix
docker compose run --build --rm --no-deps quality python -m ruff format --no-cache app tests alembic
```

The `quality` service bind-mounts `apps/api`, so checks always read the current
working tree and formatting writes changes back to the host.

Coverage remains diagnostic; failure-path coverage matters more than an
arbitrary percentage threshold. Ruff lint and format pass across 165 Python
files, generated OpenAPI types have no drift, and the disposable Docker test
stack is removed after the run.

The Stage 3 gate on 2026-08-07 passed 104 fast API tests and 29 disposable
PostgreSQL integration tests; diagnostic API coverage was 92%. The integration
suite proves a successful recommendation leaves users, preferences,
interactions, recommendation events, games, and taxonomy unchanged. Ruff,
artifact validation, `catalog_stale`/`catalog_invalid` agreement, CORS
allow/reject cases, OpenAPI generation, Docker E2E, and `pip check` passed. The
Dockerfile now removes the unused Debian `perl-base` package after all install
steps and fails the build if `dpkg --audit`, `pip check`, or application imports
fail. Rebuilt `gamelens-ai-api:stage4-test` image digest prefix `11b2f940731e`
retains all 49 PostgreSQL integration passes. Docker Scout reports 0 critical,
0 high, 3 medium, 27 low, and 2 unspecified findings across 193 packages; its
only-fixed scan reports no actionable fixed advisory. The earlier `perl-base`
critical/high blocker is resolved, while the remaining base-image findings stay
documented. The development image remains
non-production-oriented, and Stage 7 must choose and rescan a
production-minimal base.

## Seed data

`data/catalog/games.json` contains 30 fictional games and 36 taxonomy records.
Descriptions and synthetic rating signals are project-authored. There are no
cover binaries, external API identifiers, or recommendation-quality claims.
The seed command validates all references and upserts by stable slug.
It emits structured inserted, updated, and unchanged counters.

## Current limitations

- No account authentication, roles, cross-device identity recovery, or
  authorization beyond possession of the anonymous session credential.
- Stage 4 identity, preference, feedback, personalized-event, retention, and
  revocation code is complete and verified; the PostgreSQL and 38/38 exact-host
  browser gates are green.
- Retention and revocation are operator-invoked commands; there is no scheduler
  or startup side effect.
- No online fit, background rebuild, hot reload, or automatic artifact
  promotion. Operators build explicitly and restart the API to activate.
- The ephemeral collaborative extractor and aggregate audit are implemented,
  but live access is default-off and no public contribution-consent route is
  present.
- The collaborative trainer, hardened artifact/loader, pure scorer, hybrid
  policy, live registry/invalidation, bounded readiness, component status, and
  internal saved-request orchestration are implemented. No approved live build
  registration/promotion, product contribution-consent route, Stage 5 public
  personalized response/event schema, lifecycle operator command set, or
  approved real interaction dataset is implemented. Current HTTP responses and
  events therefore preserve exact Stage 4 behavior.
- No formal recommendation-quality evaluation on the synthetic seed; that is
  Stage 6 work.
- No external metadata source is integrated.
- The Docker image is development-oriented; production hardening is Stage 7.
