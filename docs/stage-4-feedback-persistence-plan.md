# GameLens AI

## Stage 4 Engineering Plan: Feedback and Persistence

- **Document status:** Complete and verified on 2026-08-13.
- **Stage 3 prerequisite:** Complete and verified on 2026-08-07.
- **Planning branch:** `docs/stage-4-plan`
- **Target implementation branch:** `feat/stage-4-feedback-persistence`
- **Primary outcome:** An explicit-consent anonymous identity lifecycle with
  durable preferences, state-like feedback, deterministic feedback-aware
  recommendations, bounded recommendation-event logging, and an accessible
  opt-in experience that preserves the Stage 3 stateless contract.

Sections 1–20 retain the approved forward-looking engineering plan. Section 21
records the implemented decisions, Section 22 is the verified Stage 5 handoff,
and Section 23 records the completed acceptance evidence.

### Current implementation snapshot

The `feat/stage-4-feedback-persistence` worktree currently contains:

- Alembic revisions `0003_stage_4_anonymous_identity`,
  `0004_stage_4_interaction_state`, and expected head
  `0005_stage_4_event_contract`.
- Explicit-consent anonymous sessions, protected `/api/v1/me` lifecycle,
  preference, temporal-feedback, and personalized-recommendation routes.
- Feedback policy `gamelens-feedback-adjustment/1.0.0` over the unchanged Stage
  3 model/artifact contract, plus bounded `stage-4-v1` recommendation events.
- An opt-in browser flow for rehydration, saved preferences, feedback,
  personalized results, expiry recovery, and clear-data behavior while the
  request-only branch remains available.
- Dry-run-first retention and separately confirmed bulk-revocation commands,
  plus an exact-host `gamelens.test` E2E topology on ports 3000 and 8000.

Fast API (184 tests, 89% diagnostic coverage), ML (52 tests, 83%), and web (76
tests, 67.15% statements/71.4% lines) checks are passing in the implementation
worktree. All 49 disposable-PostgreSQL integration tests pass in 4.53 seconds,
covering the populated legacy upgrade, Stage 4
constraints/indexes, concurrent feedback serialization, personalized HTTP
event correlation, deletion cascades, and bounded retention. Ruff passes across
112 Python files; strict TypeScript, ESLint, Prettier, production build,
generated OpenAPI drift, production/full npm audits, and all three Compose
definitions pass. The 38-case exact-host Docker browser matrix passes in 1.3
minutes without retry using two workers: 28 Chromium, 5 Firefox, and 5 WebKit.
Final release diff/privacy review is clean.
The Dockerfile removes unused
Debian `perl-base` after all install steps, resolving the earlier two critical
and two high findings. The rebuilt no-cache `gamelens-ai-api:stage4-test` image
with digest prefix `11b2f940731e` passes runtime imports and `pip check`, retains
all 49 PostgreSQL integration passes, and its comprehensive Docker Scout scan
reports 0 critical, 0 high, 3 medium, 27 low, and 2 unspecified findings across
193 packages. Its only-fixed scan reports no actionable fixed advisory. Stage 4
is verified complete.

## 1. Context

Stages 1 through 3 established the repository, FastAPI and PostgreSQL
application, deterministic catalog, Next.js web experience, reproducible
content-model artifact, immutable online ranker, typed recommendation API, and
accessible request-scoped recommendation flow. Their completed behavior and
verification evidence are recorded in the
[Stage 3 engineering plan](stage-3-content-recommendation-mvp-plan.md).

The Stage 3 recommendation path remains deliberately stateless. A request to
`POST /api/v1/recommendations` supplies selected games and positive taxonomy
or platform context for that request only. The route reads one consistent
catalog snapshot, invokes the validated Stage 3 artifact, returns explained
results, and writes no user, preference, interaction, or recommendation-event
row. The browser retains that request-only branch alongside the new opt-in
Stage 4 branch.

The Stage 1 schema introduced future-facing `users`, `user_preferences`,
`interactions`, and `recommendation_events` tables. The Stage 4 implementation
activates them as a persistence contract:

- `users.anonymous_key` is replaced by consent, expiry, revocation, and a keyed
  token-digest lifecycle.
- `user_preferences` has a bounded replace/clear/rehydration contract with
  reference validation and server-owned weights.
- `interactions` has explicit active/superseded like/dislike, played,
  wishlist, and rating semantics with partial unique indexes.
- `recommendation_events` records generation, event-schema, model, catalog
  fingerprint, feedback-policy, bounded context, and compact result identity.

These schema and application boundaries are implemented, and the 49-test
disposable-PostgreSQL gate verifies their populated migration, concurrency,
cascade, event, and retention behavior.

The Stage 3 handoff authorizes Stage 4 to activate those boundaries only after
consent, retention, update, and deletion behavior are defined. It also
requires Stage 4 to preserve observable Stage 3 components and artifact
identity, keep user identity outside model artifacts, and avoid reinterpreting
the existing request-scoped endpoint as persisted history.

Stage 4 therefore adds a separate opt-in vertical slice:

```text
explicit consent
    -> server-generated anonymous session cookie
    -> validated durable preferences and feedback state
    -> personalized recommendation policy over the Stage 3 artifact
    -> bounded model/data/policy-versioned recommendation event
    -> accessible rehydration, feedback, expiry, and clear-data behavior
```

The first feedback policy remains deliberately small. It proves lifecycle,
data, ranking, evidence, and full-stack behavior over the project-authored
30-game fixture. It does not prove that feedback improves recommendation
quality. Collaborative signals begin in Stage 5 and formal comparative
evaluation remains Stage 6 work.

The resulting slice should demonstrate:

- No identity or durable data before an explicit, current-version consent.
- A high-entropy anonymous credential whose raw value is browser-only and
  never persisted, serialized, or logged.
- Fixed, documented consent, expiry, retention, revocation, and deletion
  semantics.
- Atomic, bounded, idempotent preference replacement and feedback-state
  changes with cross-user isolation.
- A deterministic feedback layer that hard-excludes dislikes, applies a
  documented played adjustment, preserves base component observability, and
  exposes its own versioned evidence.
- A personalized endpoint that commits exactly one bounded recommendation
  event for every commit-acknowledged HTTP 200, records none for known
  pre-commit failures, and reports a lost commit acknowledgement as ambiguous.
- An opt-out path that continues to use the Stage 3 stateless endpoint without
  cookies or writes.
- A route-to-service-to-repository boundary with deliberate read-only and
  read-write transaction ownership.
- Credentialed CORS, same-site cookie, origin, CSRF, privacy, migration,
  retention, browser, accessibility, and regression evidence.

## 2. Stage Objectives

Stage 4 will deliver:

1. A reviewed identity and privacy contract covering explicit consent,
   credential generation, cookie transport, token hashing, CSRF, expiry,
   retention, revocation, deletion, and legacy placeholder rows.
2. A safe Alembic migration sequence that preserves existing relational data,
   removes plaintext anonymous-key semantics, activates consent-aware users,
   defines temporal current interaction state, and extends recommendation
   event identity.
3. A cryptographically random anonymous session token generated only by the
   API, returned only in a host-only `HttpOnly` cookie, and looked up through a
   domain-separated digest.
4. A session bootstrap contract that returns consent/expiry metadata and a
   CSRF value without exposing an internal user ID, raw session token, token
   digest, or database details.
5. A user-deletion contract that withdraws consent, deletes the user, cascades
   all owned preferences/interactions/events, clears the cookie, and does not
   delete games or taxonomy.
6. Credentialed CORS and unsafe-request origin/CSRF enforcement for the exact
   configured web origins without wildcard origins or credential reflection.
7. Typed `GET`, `PUT`, and `DELETE` preference contracts with bounded
   replace-all semantics, stable ordering, complete reference validation, and
   server-owned weights.
8. Typed feedback contracts for one canonical per-user/game state containing
   optional liked/disliked reaction, played, wishlisted, and rating values.
9. Temporal interaction semantics that identify at most one active reaction,
   played state, wishlist state, and rating per user/game while preserving
   superseded history for later data work.
10. Atomic, idempotent feedback replacement and clearing with deterministic
    no-op behavior and serialization of concurrent writes for one user.
11. A pure, versioned personalization policy in the ML package that consumes
    saved context and feedback without embedding user identity or mutating the
    Stage 3 artifact.
12. Hard disliked-game exclusion before top-K truncation, bounded positive
    feedback affinity, an explicit played adjustment, and documented neutral
    wishlist behavior.
13. Personalized item responses whose base Stage 3 score, feedback
    contribution, played adjustment, final score, policy identity, and
    structured evidence are independently reconstructible.
14. A separate `POST /api/v1/me/recommendations` endpoint that uses saved
    preferences and feedback, while `POST /api/v1/recommendations` remains
    contract-compatible, request-scoped, cookie-agnostic, and read-only.
15. One bounded recommendation event for each commit-acknowledged personalized
    HTTP 200 generation, including a documented successful empty result, with
    no 200 for validation, identity, artifact, catalog, database, insertion, or
    ambiguous commit-acknowledgement failures.
16. Recommendation events containing event-schema, model, data-fingerprint,
    personalization-policy, effective-context, and compact top-K identity,
    without prose, raw credentials, request headers, IP addresses, or browser
    fingerprints.
17. A browser opt-in path that explains storage before consent, establishes a
    session only after affirmative action, saves and rehydrates preferences,
    manages feedback, survives reload, handles expiry, and clears all data.
18. A fully usable opt-out path that retains the current anonymous Stage 3
    onboarding and result flow without persistence.
19. One project-owned generated browser contract and API client with explicit
    protected-call credentials, CSRF headers, `PUT`/`DELETE`, cancellation,
    stale-response, and safe error handling.
20. An explicit retention preview/purge command with injected clock, bounded
    batches, dry-run default, clear execution confirmation, plus a separate
    guarded bulk-revocation command and no startup or scheduled side effect.
21. PostgreSQL migration, constraint, cascade, concurrency, transaction,
    retention, and cross-session isolation tests against a guarded disposable
    database.
22. ML, API, frontend, OpenAPI, browser, accessibility, responsive, CORS,
    cookie, CSRF, Docker, privacy, security, and complete Stage 1–3 regression
    gates.
23. Updated roadmap, architecture, data model, recommendation design, root,
    API, web, ML, infrastructure, environment, and command documentation that
    distinguishes planned, implemented, and deferred behavior.
24. A precise Stage 5 handoff defining which durable interactions are safe to
    use, what event fields mean, and why neither impressions nor the synthetic
    fixture constitute positive-feedback or quality evidence by themselves.

## 3. Non-Goals

The following work is intentionally excluded from Stage 4:

- Accounts, passwords, email identity, OAuth, social login, cross-device
  identity recovery, roles, permissions, or authorization beyond possession
  of the anonymous session credential.
- Fingerprinting users through IP address, User-Agent, device properties,
  canvas data, or third-party tracking identifiers.
- Creating a user from catalog browsing, model status, the stateless
  recommendation route, a failed request, initial page load, or any action
  other than explicit current-version consent.
- Storing the raw session token, CSRF value, or internal user ID in JSON
  responses, URLs, logs, analytics, model artifacts, `localStorage`, or
  `sessionStorage`.
- Silent sliding expiry, implicit consent renewal, or automatic replacement of
  an invalid/expired session without renewed affirmative consent.
- Preference history or arbitrary client-selected preference weights.
- Unbounded free-form user profile text or natural-language preference input.
- Implicit `viewed` interaction writes from page navigation or card rendering.
- Treating recommendation events as likes, clicks, conversions, or positive
  feedback.
- Collaborative filtering, matrix factorization, nearest-neighbor user
  similarity, or content/collaborative hybrid ranking; these begin in Stage 5.
- Offline Precision@K, Recall@K, Hit Rate@K, NDCG@K, coverage, novelty,
  diversity, causal, uplift, or comparative model-quality claims; these remain
  Stage 6 work.
- Production identity services, managed secrets, scheduled retention jobs,
  monitoring, alerting, CI/CD, deployment, or production cookie-domain design;
  these remain Stage 7 concerns.
- External data ingestion, remote game APIs, cover-image imports, or
  undocumented network access.
- Semantic embeddings, LLM explanations, diversity reranking, exploration,
  contextual bandits, or other advanced Stage 8 candidates.
- Writing preference, feedback, or event data into the model artifact or
  rebuilding/hot-reloading an artifact after each user action.
- Browser-side ranking, score adjustment, candidate filtering, or reordering
  API results.
- Post-processing an already truncated top-K list in the API; filtering and
  personalization must occur before final ordering and truncation.
- Treating wishlist as proven positive preference in the first feedback
  policy without evaluation evidence.
- Deleting or resetting the persistent development database from tests,
  retention commands, migrations, startup, or ordinary Make targets.
- A general background-job system, queue, Kafka, Redis, cache, or additional
  service solely for Stage 4.
- A new frontend state-management or form dependency without a concrete,
  reviewed need.
- Claiming that the 30-game synthetic catalog or development interactions
  represent real users, market behavior, or recommendation quality.

## 4. Engineering Principles

### 4.1 Explicit Consent Before Identity

No route except the dedicated session-creation contract may create a user or
set an identity cookie. Consent must be affirmative and tied to the exact
server-supported policy version. A stale client cannot submit consent for copy
the server no longer recognizes.

### 4.2 Stateless Compatibility Is a Contract

`POST /api/v1/recommendations` remains the Stage 3 request-scoped route. It
ignores an attached Stage 4 cookie, performs no identity lookup, persists
nothing, and returns the existing response/error semantics. Durable behavior
uses a distinct `/me` boundary.

### 4.3 Raw Credentials Are Browser-Only

The raw anonymous token exists only in the browser cookie and transient server
request memory. PostgreSQL stores a domain-separated keyed digest. Application
objects, response models, logs, exception details, retained traces, fixtures,
and committed files must never contain the raw value.

### 4.4 Server-Owned Identity and Weights

The server generates identity, consent timestamps, expiry, preference weights,
policy identity, and event identity. Clients submit bounded selections and
feedback state; they do not select token values, user IDs, timestamps, model
weights, score adjustments, retention cutoffs, or event payloads.

### 4.5 Complete Validation Before Mutation

Preferences and feedback are validated in full—including every catalog and
taxonomy reference—before the first mutation. A use case commits once or rolls
back completely. Partial replacement, silent dropping, and best-effort writes
are prohibited.

### 4.6 Temporal State With Honest History

Like/dislike, played, wishlist, and rating behave as current state to the
product while database rows retain explicit occurrence and supersession time.
At most one active state per defined conflict group is permitted. Repeating an
identical write is a true no-op rather than a duplicate event.

### 4.7 Deterministic Feedback Policy

Every feedback source, bound, precedence rule, exclusion, normalization,
weight, adjustment, fixed-point operation, and tie-break is versioned. The same
artifact, catalog snapshot, saved state, policy, and clock-independent inputs
must produce the same ordered result and evidence.

### 4.8 Preserve Base Observability

Stage 3 content, platform, and popularity values remain reconstructible. The
feedback layer exposes its own affinity and played adjustment instead of
silently modifying a base component. A result without effective feedback must
preserve the Stage 3 base score and order.

### 4.9 Identity Never Enters Artifacts

Artifacts remain catalog-level, immutable, and shareable across users. User
IDs, token digests, preferences, interactions, events, and consent data stay in
PostgreSQL or bounded request memory. Feedback ranking reads artifact vectors
without fitting or writing them.

### 4.10 Transactions Own Meaning

The stateless route retains one `REPEATABLE READ, READ ONLY` catalog snapshot.
The personalized route deliberately owns one bounded `REPEATABLE READ, READ
WRITE` transaction that resolves/locks the user, reads effective context and
catalog, ranks, inserts the matching event, and commits before returning
success. Repository helpers do not change transaction mode after queries have
started.

### 4.11 Data Minimization and Bounded Logging

Recommendation events contain only fields required to correlate or audit the
generation contract; they are not standalone state snapshots. Payload shape,
list counts, strings, top-K, and serialized bytes are bounded. Descriptions,
explanation prose, headers, addresses, credentials, and unrelated profile data
are excluded.

### 4.12 Deletion and Retention Are Product Contracts

User deletion is immediate, transactional, and cascading. Time-based cleanup
is explicit, previewable, bounded, and idempotent. Neither startup nor a broad
test/quality target performs retention. A scheduler is not implied.

### 4.13 Accessible Persistence States

Consent, saving, rehydration, pending feedback, failure, session expiry,
withdrawal, and clear-data behavior require visible text, keyboard operation,
focus management, and useful announcements. Color or icon state alone is
insufficient.

### 4.14 Minimal Dependency and Infrastructure Surface

Python and browser standard-library/platform capabilities are preferred for
tokens, HMAC, cookies, state, and forms. Stage 4 adds no identity provider,
cache, queue, database, frontend store, or cryptography package unless Phase 0
demonstrates a concrete gap.

### 4.15 Incremental Delivery and Regression Safety

Schema precedes writes, identity precedes protected resources, persistence
precedes feedback ranking, API contracts precede UI activation, and every
slice remains testable and truthful. Stage 1–3 gates run throughout the stage,
not only at release.

## 5. Proposed Technical Decisions

### 5.1 Compatibility Boundary

The existing public catalog, metadata, model-status, game-detail, health, and
stateless recommendation contracts remain supported. In particular:

- `POST /api/v1/recommendations` keeps its current request body, response body,
  bounds, standard errors, model readiness behavior, and database read-only
  guarantee.
- A cookie on that route is ignored rather than interpreted as saved context.
- The Stage 3 model `gamelens-content-tfidf` version `1.0.0`, artifact schema
  `1`, data fingerprint, and base component semantics remain identifiable.
- Stage 4 introduces a separate personalization-policy identity rather than
  silently redefining the Stage 3 artifact/model version.
- Generated TypeScript types remain sourced from live OpenAPI. New schemas do
  not replace old stateless request/response schemas.

The implemented personalization identity is
`gamelens-feedback-adjustment` version `1.0.0`. If implementation requires
changing artifact-owned feature or base-ranking configuration, it must instead bump the
content model/code compatibility, rotate `MODEL_ARTIFACT_PATH`, rebuild and
validate a new artifact, and record that decision. An existing `1.0.0`
artifact may never be made to mean something different.

### 5.2 Anonymous Session and Consent Contract

Stage 4 implements:

| Method | Path                         | Purpose                                      |
| ------ | ---------------------------- | -------------------------------------------- |
| POST   | `/api/v1/anonymous-sessions` | Explicit consent, creation, or re-consent    |
| GET    | `/api/v1/me`                 | Session bootstrap, consent, expiry, and CSRF |
| DELETE | `/api/v1/me`                 | Withdraw consent and delete all owned data   |

Session creation accepts only a small exact schema such as:

```json
{
  "consent": true,
  "consent_version": "stage-4-v1"
}
```

Unknown fields are rejected. `consent` must literally be true, and the version
must equal the configured current consent version. A stale version returns a
controlled conflict/validation error and creates no user or cookie.

The server generates at least 256 bits of entropy with the Python standard
library and encodes it as unpadded URL-safe text. The cookie is host-only,
`HttpOnly`, `SameSite=Lax`, scoped to `/api/v1`, and uses `Secure=true` in an
HTTPS/production configuration. Local loopback development HTTP may explicitly
configure `Secure=false`. A second narrow exception permits an allowlisted
reserved `.test` host only when `ENVIRONMENT=test`; all other non-loopback
insecure combinations fail validation. Cookie `Max-Age` and authentication
expiry agree.

PostgreSQL stores only
`HMAC-SHA-256(ANONYMOUS_SESSION_SECRET, "gamelens:session:v1\x00" || raw_token)`
as lowercase hex. CSRF uses the separate `gamelens:csrf:v1\x00` domain with
the same raw token and secret, returned through session bootstrap but never
stored. Changing
the secret makes existing digests unresolvable while the previous secret is
absent; restoring that secret can make them resolvable again. Permanent bulk
revocation therefore requires the explicit revoke operation to set
`revoked_at` before an old secret can be restored. No development default is
accepted in a production configuration.

Initial consent has no CSRF value yet, so `POST /api/v1/anonymous-sessions`
requires an exact allowed `Origin` and `application/json` content type but no
CSRF header when no resolvable cookie is present. The POST handler does not
claim it can prove that an OPTIONS request occurred; browser CORS tests prove
the configured preflight succeeds or fails before the POST. A committed request
returns HTTP 201 and sets the cookie. An invalid or expired cookie is cleared
and the request fails without creating a replacement; the UI must present and
submit consent again deliberately.

When a matching unexpired cookie exists, `GET /api/v1/me` may return only
lifecycle status and a CSRF value if consent is outdated; it does not return
preferences or feedback in that state. `DELETE /api/v1/me` remains available
with that CSRF value so a user can clear retained data. Explicit re-consent with
the matching unexpired cookie, exact Origin, and CSRF keeps the same raw token
and digest, updates consent/version/absolute expiry, reissues the cookie to that
expiry, and preserves owned state. Avoiding credential rotation prevents a
database-commit/lost-`Set-Cookie` split from stranding the user. If commit
acknowledgement or the response is uncertain, the UI re-runs `GET /api/v1/me`
with the still-valid cookie to learn the committed state; this recovery never
extends the database expiry. A valid active current-version session returns
HTTP 200 as an idempotent no-op: it does not change consent time, expiry, token,
or user rows.

An expired or revoked session never receives lifecycle status or CSRF, cannot
delete/re-consent into the old identity, and cannot access owned state. The
server fails closed and clears the stale cookie. A later explicit consent after
that clearing creates a new user; the old row remains inaccessible until the
next eligible cleanup. If the initial identity commit succeeds but its response
is lost, an explicitly consented but inaccessible row may similarly remain; no
HTTP 201 is returned without commit acknowledgement, no client-selected token
is reused, and retention removes the orphan. Session responses expose only
consent status/time, authentication expiry, and CSRF metadata, never internal
identity.

The implemented anonymous-session cookie lifetime is a fixed 180 days
from consent, with no sliding refresh on reads or ordinary writes. At that time
owned data becomes cleanup-eligible; Stage 4 does not claim deletion occurs at
the exact second because it supplies an operator-run command rather than a
scheduler. UI copy must distinguish access expiry from deletion on the next
cleanup run. A production deployment is blocked on the Stage 7 scheduling and
retention-cadence design.

### 5.3 Identity Migration and Legacy Rows

The migration sequence replaces plaintext-key semantics without assuming
that placeholder tables are empty:

1. Add `anonymous_token_digest`, `consent_version`, `consented_at`,
   `expires_at`, and nullable `revoked_at` through revision
   `0003_stage_4_anonymous_identity`.
2. Give every legacy row the deterministic 64-character revocation digest
   `md5('legacy-revoked-v1:' || anonymous_key) || lpad(to_hex(id), 32, '0')`.
   The ID suffix guarantees uniqueness. It is non-authenticating because
   consent is null and `revoked_at` is set, not because the MD5 prefix is an
   authentication primitive.
3. Leave consent fields null and set `revoked_at` to the migration time for
   legacy rows. A null-consent/revoked row is inactive and cannot resolve
   through the protected API.
4. Drop the plaintext `anonymous_key` column and its uniqueness constraint
   only after the replacement digest is populated and verified.
5. Add unique digest, expiry/revocation cleanup, and lifecycle consistency
   indexes and constraints.

The database permits either all consent lifecycle fields present or all null
for preserved legacy rows. New application-created users must always provide
all consent fields, `expires_at` must be later than `consented_at`, and an
active resolver requires `revoked_at IS NULL`. Legacy rows and their related
data are preserved but revoked. Default expiry cleanup never selects their null
expiry; a separate explicit revoked-before preview/execution option is required
to purge them.

The migration must not fabricate consent or silently authenticate a previously
stored plaintext value. Dropping the plaintext column removes it from the
application schema but does not prove physical erasure from old heap pages,
WAL, backups, or storage snapshots. Media/backup sanitization and verified
backup expiry belong to the Stage 7 production data-lifecycle review.

Every new revision updates ORM models, expected Alembic-head checks, readiness
tests, disposable PostgreSQL fixtures, migration documentation, and downgrade
behavior in the same slice.

### 5.4 Persistent Preference Contract

Stage 4 implements:

| Method | Path                     | Purpose                                  |
| ------ | ------------------------ | ---------------------------------------- |
| GET    | `/api/v1/me/preferences` | Rehydrate canonical saved context        |
| PUT    | `/api/v1/me/preferences` | Atomically replace all saved preferences |
| DELETE | `/api/v1/me/preferences` | Atomically clear saved preferences       |

The replace request reuses the Stage 3 selection families and bounds but omits
`top_k`:

```json
{
  "selected_game_ids": [1, 2],
  "preferred_genres": ["strategy"],
  "preferred_tags": ["turn-based"],
  "preferred_platforms": ["linux"]
}
```

Collections are distinct and bounded at 5 games, 5 genres, 10 tags, and 6
platforms. At least one game, genre, or tag is required for a usable saved
content context; platform-only input is rejected. The client cannot provide
weights. The server writes the model-owned positive value and stores canonical
stable slugs in `UserPreference.value`, including conversion from public game
ID to stable slug.

`PUT` means complete replacement, not merge. The service resolves every game
and taxonomy value before mutation, locks the owning user, holds referenced
catalog/taxonomy rows with `FOR SHARE` through commit, computes the exact
set difference, and commits once. Repeating an identical canonical body makes
no row or timestamp change. `DELETE` is idempotent. Responses use stable family
and slug ordering and may include resolved display data needed by the web flow.

If a stored slug no longer exists in the current catalog, `GET` reports a
bounded stale-reference detail rather than silently deleting or ignoring it.
Personalized recommendation returns controlled `saved_preferences_stale`
conflict until the user replaces or clears the stale state. This keeps catalog
changes observable and prevents hidden profile mutation.

### 5.5 Feedback and Temporal Interaction Contract

Stage 4 implements:

| Method | Path                                  | Purpose                             |
| ------ | ------------------------------------- | ----------------------------------- |
| GET    | `/api/v1/me/feedback`                 | Paginate current feedback state     |
| PUT    | `/api/v1/me/games/{game_id}/feedback` | Replace one game's current feedback |
| DELETE | `/api/v1/me/games/{game_id}/feedback` | Clear one game's current feedback   |

The `PUT` body is a full resource rather than a partial patch:

```json
{
  "reaction": "liked",
  "played": true,
  "wishlisted": false,
  "rating": 8.5
}
```

All fields are required. `reaction` is `liked`, `disliked`, or null;
`played` and `wishlisted` are booleans; `rating` is null or a finite value from
0 through 10 in documented half-point increments. An all-empty state is
equivalent to clearing the resource. Rating may coexist with reaction, played,
or wishlist. For ranking classification, explicit reaction takes precedence
over rating; contradictory-looking combinations remain truthful user data
rather than being silently rewritten.

Half-point precision is an API/UI version-1 rule, not a new database check.
The existing numeric 0–10 database contract continues to preserve legacy
two-decimal values without rounding or deletion. Stage 5 must use the stored
exact numeric value and documented policy thresholds rather than assume every
historical rating came from the Stage 4 UI.

The existing `interactions` table becomes a temporal state ledger through
revision `0004_stage_4_interaction_state`:

- Add nullable `superseded_at` and require it to be no earlier than
  `occurred_at`.
- An active row has `superseded_at IS NULL`.
- A partial unique reaction index permits at most one active `liked` or
  `disliked` row per user/game.
- A partial unique state index permits at most one active `played`,
  `wishlisted`, and `rated` row per user/game/type.
- Existing duplicate rows are ordered by `occurred_at` then primary key; older
  rows receive deterministic supersession times while the latest valid row
  remains active. Existing history is not deleted.
- `viewed` remains repeatable and receives no Stage 4 write endpoint.

For a changed field, the service supersedes the prior active row and inserts a
new active row in one transaction. Clearing marks the active row superseded.
An identical replacement is a true no-op. The authenticated user row is locked
so concurrent writes from two tabs cannot leave both liked and disliked active.
Database constraints remain the final race-safety boundary.

`GET /api/v1/me/feedback` returns only current active state in the existing
catalog-style `{items, page, page_size, total}` envelope. `page` defaults to 1
and is bounded from 1 through 1,000,000; `page_size` defaults to 50 and is
bounded from 1 through 100. Aggregated resources order by descending latest
active `occurred_at`, then ascending game ID. Each response computes items and
total from one consistent snapshot.
Concurrent changes between separate page requests may move an item; the client
reloads page 1 after a mutation rather than claiming cross-request snapshot
stability. Historical rows are not exposed by the Stage 4 product API; they
remain an internal data boundary for the Stage 5 handoff.

### 5.6 Effective Personalized Context

`POST /api/v1/me/recommendations` accepts only bounded generation options such
as `top_k` from 1 through 20. It does not accept another copy of preferences or
an identity field. Users who want request-only context continue to use the
Stage 3 endpoint; users who want durable personalization explicitly save
preferences first.

The effective context is constructed as follows:

1. Load canonical saved game, genre, tag, and platform preferences.
2. A disliked game suppresses the same saved game preference for the current
   generation without silently deleting either record.
3. Require at least one remaining game, genre, or tag content signal.
4. Use the saved preferences to produce the unchanged Stage 3 base content,
   platform, and popularity score.
5. Build a bounded positive-feedback profile from active liked games and, only
   when no explicit reaction exists, ratings of at least 7.
6. Treat explicit dislikes as hard exclusions; a rating alone does not become
   a hard exclusion in policy version 1.
7. Exclude the bounded positive-feedback source games from their own result so
   self-similarity cannot recommend the evidence item back to the user.
8. Keep played candidates eligible but apply the documented played adjustment.
9. Persist wishlist but assign it no ranking effect in the first policy.

Positive feedback sources are deduplicated and capped at the five most recent
active states, with stable slug resolving timestamp ties. The cap bounds
inference and evidence. A user with more feedback retains all state in
PostgreSQL; only the policy's versioned effective input is bounded.

### 5.7 Feedback Scoring and Ordering

Feedback adjustment must run inside the pure ML boundary before final top-K
truncation. API-side filtering of an already truncated Stage 3 list is
prohibited because it can return too few items and an incorrect order.

The current `ContentRanker.rank()` truncates internally. Stage 4 will extract a
shared bounded pre-truncation candidate-scoring primitive. The existing Stage 3
method becomes a compatibility wrapper that calls the primitive and applies
its unchanged ordering/top-K contract; the personalized policy consumes the
same candidate scores, applies exclusions/adjustments, and truncates only at
the end.

The planned version-1 policy is:

- Compute the ordinary Stage 3 base score and components for every eligible
  content-supported candidate.
- When a positive-feedback profile exists, compute cosine-equivalent affinity
  between each candidate vector and the normalized positive-profile centroid.
- Combine 90% of the Stage 3 base score with 10% feedback affinity.
- When no positive profile exists, retain 100% of the Stage 3 base score so the
  score and ordering are exactly unchanged before other adjustments.
- Multiply the combined score of an active played candidate by 0.5.
- Exclude dislikes and all context/source games before ordering.
- Quantize every raw score, contribution, factor application, and final score
  to the existing 1,000,000 fixed scale with round-half-up.
- Order by final score, pre-played combined score, base score, feedback
  affinity, Stage 3 content score, Stage 3 popularity score, then stable slug.

The final response must separate:

- `base_ranking_score` and the existing content/platform/popularity details.
- Active base blend weight (1.0 without a profile or 0.9 with one) and exact
  weighted base contribution.
- Personalization policy name/version.
- Feedback affinity raw score, weight, and contribution when active.
- Played factor and exact fixed-unit delta when active.
- Final `ranking_score` and rank.
- Bounded positive-feedback evidence and exclusion/adjustment reason codes.

Serialized fixed units must reconstruct the pre-played and final scores
exactly. Scores remain ranking signals, never probabilities, predicted ratings,
or match percentages. The weights and played factor are functional policy
defaults to be frozen in Phase 0 and verified, not claims that they improve
real-user outcomes.

### 5.8 Personalized Response and Error Contract

The personalized endpoint uses a distinct response schema so legacy clients do
not need to understand feedback-specific fields or response reasons. It retains
the same game summaries and Stage 3 evidence where applicable.

Controlled outcomes include:

- `401 anonymous_session_required` for missing, invalid, revoked, or expired
  identity.
- `403 origin_not_allowed` or `csrf_validation_failed` for unsafe protected
  requests.
- `404 game_not_found` for a feedback resource referencing an unknown game.
- `409 consent_version_outdated` and `saved_preferences_stale`.
- `422` standard validation for body shape, bounds, duplicates, missing saved
  content context, invalid rating step, or unknown current taxonomy.
- `503` for model unavailable, catalog invalid/stale, database failure, event
  insertion failure, or an ambiguous missing commit acknowledgement through
  the existing safe error envelope.
- HTTP 200 with a documented empty reason when the valid personalized context
  leaves no eligible/content-supported candidate.

Protected responses carry `Cache-Control: no-store`. Errors do not reveal
whether another user's token, preference, interaction, or event exists.

### 5.9 Recommendation Event Contract

Revision `0005_stage_4_event_contract` adds:

- A unique server-generated `generation_id` also returned in a successful
  personalized response.
- `event_schema_version`.
- `data_fingerprint`.
- `ranking_policy_name` and `ranking_policy_version`.
- Supporting indexes for user/time and model/policy/time queries.
- Conditional checks that preserve legacy rows without inventing missing
  identity while requiring complete identity for new Stage 4 events.

Application validation bounds both JSON bodies before insertion. The request
context contains canonical effective preference slugs, bounded positive-source
slugs, requested top-K, complete effective-state counts, and a fingerprint of
the full canonical disliked/played/source sets actually used. The complete
dislike/played lists are deliberately not duplicated into potentially large
event JSON. The compact result summary contains at most 20 objects with stable
game slug, rank, base/final fixed units, and feedback/played adjustment units.
It excludes title, description, explanation prose, raw floats not needed for
correlation, headers, addresses, credentials, and database user IDs.

The event is a bounded audit/correlation record, not a standalone reproducible
snapshot. Exact regeneration may require retained interaction history and the
matching catalog/artifact; deletion or retention can intentionally make that
impossible. The fingerprint proves whether a separately reconstructed
canonical effective state matches, but it cannot reveal a deleted state.

An event means that the server committed a personalized generation; it does
not prove that the browser received, viewed, clicked, or liked the result.
Exactly one event is inserted for every personalized HTTP 200 generation,
including a successful empty result. No event is inserted for a 4xx,
pre-commit model/catalog failure, explicit database rollback, failed event
validation, or stateless recommendation.

PostgreSQL commit acknowledgement has an unavoidable failure window: the
database may commit and the connection may fail before the application learns
that it succeeded. In that case the server must not return HTTP 200, but the
event may already exist. The UI does not automatically retry an ambiguous
personalized generation, and `generation_id` supports audit. Exactly-once
deduplication across a user-initiated retry is outside Stage 4 unless Phase 0
adds and fully specifies an idempotency-key contract.

### 5.10 Transaction Ownership

Transaction-mode ownership now sits in the application use case before any
query executes:

- HTTP dependencies may parse cookie/header/origin material and derive a token
  digest, but they do not query for a user. The transaction-owning application
  service establishes isolation first and then resolves/locks identity.

- Stateless recommendation keeps one `REPEATABLE READ, READ ONLY` transaction
  and the existing before/after no-write proof.
- Personalized recommendation opens one bounded `REPEATABLE READ, READ WRITE`
  transaction, resolves the consented unexpired user, locks that row against
  deletion, reads preferences/feedback/catalog, validates the artifact
  fingerprint, ranks, validates the response/event, inserts one event, and
  explicitly commits before returning HTTP 200.
- If event insertion fails or commit acknowledgement is absent, the endpoint
  does not return HTTP 200. An acknowledgement failure is reported as an
  ambiguous generation outcome because the event may have committed.
- `DELETE /api/v1/me` locks the user for update, deletes it with cascades, commits,
  and only then returns 204/clears the cookie.

Inference remains bounded and in memory, so the write transaction does not
perform artifact I/O, fitting, network calls, or browser work. Transaction
duration is measured diagnostically without creating an unsupported service
level objective.

### 5.11 Retention and Deletion

The implemented retention policy is:

- Anonymous authentication expires 180 days after explicit consent with no
  silent sliding extension.
- The corresponding user, preferences, and interactions become purge-eligible
  at `expires_at`; actual deletion occurs on the next explicit cleanup run, not
  at a falsely promised exact wall-clock instant.
- Recommendation events become independently purge-eligible 90 days after
  generation even while a user remains active.
- User-triggered deletion is immediate and cascades all owned data regardless
  of those eligibility windows.
- Expired authentication cannot access profile or lifecycle data, delete, or
  re-consent into the old identity. The stale cookie is cleared; any later
  explicit consent creates a new identity while cleanup timing never extends
  access. Outdated consent may use lifecycle/delete/re-consent only while the
  underlying session is still unexpired.
- Revoked/legacy rows with null expiry are excluded from default expiry purge
  and require an explicit `--revoked-before` preview/execution selection.

The explicit retention command provides preview and execution modes. Preview
is the default and reports only bounded counts and cutoff metadata, not user content
or token digests. Execution requires an unmistakable flag, uses small ordered
batches, rechecks the cutoff in each transaction, and is idempotent. It deletes
eligible events first and expired consented users through cascade. Revoked rows
are included only through the separate explicit cutoff. Tests may run execution
only against a verified disposable database. Ordinary startup, `make up`,
migration, seed, model build, broad tests, and web startup never purge data.
Because Stage 4 provides no scheduler, documentation promises eligibility and
operator behavior rather than exact-time deletion. Production scheduling and
cadence verification remain Stage 7 work.

### 5.12 Browser State and Experience

The `/recommendations` route will retain the opt-out Stage 3 flow and add a
clearly separate durable path:

1. Explain what is saved, for how long, how it affects recommendations, and how
   to delete it before presenting the consent action.
2. Establish a session only after the user explicitly chooses durable
   personalization.
3. Hold the returned CSRF value in memory; after reload, call
   `GET /api/v1/me` with credentials to rehydrate it.
4. Load saved preferences and current feedback through the project-owned API
   client.
5. Let the user replace saved selections deliberately and request a
   personalized result.
6. Expose accessible liked/disliked, played, wishlist, and rating controls on
   the recommendation experience with clear pending, success, failure, and
   superseded-request behavior.
7. Re-run personalized recommendation after deliberate feedback action rather
   than re-ranking the current list in the browser.
8. Offer an explicit clear-data action with confirmation, post-delete focus,
   cookie clearing, and return to the opt-in/stateless state.

The raw session token, digest, user ID, preferences, and feedback are not stored
in URL parameters, `localStorage`, or `sessionStorage`. The browser may keep
resolved state in route-scoped React memory. Native controls and existing
project-owned components are preferred; no global store is planned.

The API client adds `PUT` and `DELETE`, credentialed protected requests, CSRF
headers, response validation, cancellation, and safe categories for identity,
consent, conflict, and forbidden failures. Unprotected catalog/status/stateless
calls remain usable without credentials. Generated OpenAPI types remain the
only frontend contract source.

### 5.13 Cookie, CORS, CSRF, and Privacy Boundary

Credentialed CORS uses exact normalized origins, `allow_credentials=true`,
explicit `GET`, `POST`, `PUT`, and `DELETE` methods, and only required headers.
Wildcard origins are invalid. Every unsafe cookie-authenticated route verifies
the exact `Origin` and the domain-separated CSRF token before mutation.
Initial session creation has no CSRF value, so the server requires exact Origin
and JSON content type as the sole CSRF bootstrap exception. Browser tests prove
the configured preflight behavior; the POST handler does not treat prior
preflight as authentication evidence. JSON-only body handling and custom CSRF
headers cause browser preflights where applicable. CORS is defense-in-depth and
is not described as authentication.

Configuration covers:

- Session HMAC secret and current consent version.
- Cookie name, path, SameSite, Secure, and TTL.
- Exact CORS/unsafe-origin allowlist.
- Retention durations and batch cap.
- Environment mode required for secure-cookie validation, including the narrow
  allowlisted reserved `.test` host exception available only in tests.

No configuration contains a user token. Settings validators reject blank or
weak secrets, invalid cookie names/paths, wildcard credentialed origins,
non-positive/broad TTL or batch values, and unsafe production combinations.
Log redaction and final scans cover cookie/header names, raw/token-like values,
CSRF values, JSON context, error details, Web Storage, retained browser output,
and committed fixtures.

### 5.14 Docker and Same-Site Browser Topology

The current E2E stack addresses web and API with the exact hostname
`gamelens.test`: web origin `http://gamelens.test:3000` and API URL
`http://gamelens.test:8000`. The web service shares the API network namespace
so both browser-visible ports resolve to one endpoint. This keeps the cookie
first-party while still exercising a credentialed cross-origin request across
ports. `WEB_BASE_URL`, `NEXT_PUBLIC_API_URL`, CORS origins, and cookie tests use
this same documented topology.

Disposable E2E continues to use a tmpfs PostgreSQL database and a disposable
model artifact volume. HTTP test configuration may use `Secure=false` only for
the isolated test hostname, while fast configuration tests prove that the
production/HTTPS profile requires `Secure=true`. Teardown removes only the E2E
project's containers, network, artifact volume, and browser output.

Protected-cookie browser projects disable Playwright network traces by default
because traces can contain `Set-Cookie`, `Cookie`, CSRF headers, and bootstrap
JSON. A developer may opt into a local diagnostic trace only as an explicitly
disposable sensitive artifact; it remains ignored, is never attached or
committed, and is removed after the investigation. Screenshots and reports must
not render credential values.

### 5.15 Delivery and Branch Topology

This planning branch merges into `main` before implementation. The target
integration branch is then created from that updated `main`:

```text
docs/stage-4-plan
        |
        `-- merge --> main (updated planning baseline)
                         |
                         `-- feat/stage-4-feedback-persistence
                             |-- feat/stage-4-identity-lifecycle
                             |-- feat/stage-4-preferences-feedback-api
                             |-- feat/stage-4-feedback-ranking
                             |-- feat/stage-4-recommendation-events
                             |-- feat/stage-4-web-persistence
                             |-- test/stage-4-full-stack-acceptance
                             `-- docs/stage-4-completion
```

Each child branch is created from the latest integration branch only when its
dependency is ready and merges back into the integration branch through a
reviewable PR. They are not all created in parallel. The final integration PR
to `main` is opened only after the complete acceptance gate and documentation
record pass. Tightly coupled migration/model/service changes may share one PR
when splitting them would leave a misleading or untestable intermediate state.

## 6. Target Repository Structure

```text
apps/api/
|-- alembic/versions/
|   |-- 0003_stage_4_anonymous_identity.py
|   |-- 0004_stage_4_interaction_state.py
|   `-- 0005_stage_4_recommendation_event_contract.py
|-- app/
|   |-- api/
|   |   |-- dependencies.py
|   |   `-- v1/routes/
|   |       |-- anonymous_sessions.py
|   |       |-- feedback.py
|   |       |-- preferences.py
|   |       `-- personalized_recommendations.py
|   |-- commands/
|   |   |-- anonymous_sessions.py
|   |   `-- retention.py
|   |-- core/
|   |   `-- security.py
|   |-- repositories/
|   |   |-- anonymous_users.py
|   |   |-- interactions.py
|   |   |-- preferences.py
|   |   `-- recommendation_events.py
|   |-- schemas/
|   |   |-- anonymous_sessions.py
|   |   |-- feedback.py
|   |   |-- preferences.py
|   |   `-- personalized_recommendations.py
|   `-- services/
|       |-- anonymous_identity.py
|       |-- feedback.py
|       |-- personalized_recommendation.py
|       |-- preferences.py
|       `-- retention.py
`-- tests/
    |-- integration/
    |   |-- test_stage_4_migrations.py
    |   `-- test_stage_4_persistence.py
    `-- unit/
        |-- test_anonymous_identity.py
        |-- test_feedback_api.py
        |-- test_personalized_recommendations.py
        |-- test_preferences_api.py
        `-- test_retention.py

ml/
|-- src/gamelens_recommender/
|   |-- feedback.py
|   `-- schemas.py
`-- tests/
    `-- test_feedback.py

apps/web/
|-- src/
|   |-- features/recommendations/
|   |   |-- consent-panel.tsx
|   |   |-- feedback-controls.tsx
|   |   |-- persistent-recommendation-flow.tsx
|   |   `-- recommendation-flow.tsx
|   `-- lib/api/
|       |-- client.ts
|       `-- generated.ts
`-- e2e/
    `-- persistence.spec.ts

infra/
`-- docker-compose.e2e.yml

docs/
|-- architecture.md
|-- data-model.md
|-- recommendation-design.md
|-- roadmap.md
`-- stage-4-feedback-persistence-plan.md
```

Exact filenames may evolve during implementation. The required ownership
boundaries are identity/security primitives, user-scoped repositories,
transaction-owning application services, pure feedback ranking, generated
browser contracts, accessible product state, guarded retention operations,
and disposable acceptance fixtures.

The existing API and ML packages remain the only Python runtime boundaries.
Stage 4 does not create an identity microservice or a second model service.
The web application continues to communicate only through the project-owned
API client. Generated OpenAPI output remains the only committed generated
contract; session values, database data, browser traces, and retention output
remain ignored/disposable.

## 7. Implementation Phase 0: Preflight, Contract, Privacy, and Threat Baseline

### Objective

Re-establish the complete Stage 3 baseline, audit every future-facing
persistence boundary, and freeze externally observable identity, data,
ranking, event, privacy, and branch contracts before any schema or runtime
write is introduced.

### Work

1. Confirm a clean `main`, the merged Stage 4 plan, and the exact integration
   branch base.
2. Re-run and record the Stage 3 gates: ML tests, API fast tests, disposable
   PostgreSQL integration tests, web tests/build/static checks, OpenAPI drift,
   Docker Compose validation, and browser acceptance.
3. Record the existing verified counts as a comparison baseline: 25 ML tests,
   104 fast API tests, 29 PostgreSQL integration tests, 45 web tests, and 25
   Playwright passes, without assuming future counts.
4. Inspect existing `users`, `user_preferences`, `interactions`, and
   `recommendation_events` rows in a disposable upgraded fixture and define
   the legacy-row preservation/revocation policy.
5. Audit every hard-coded expected Alembic revision and every model/table
   readiness assertion before introducing a new head.
6. Freeze endpoint paths, methods, request/response shapes, status codes,
   standard error codes, cookie attributes, CORS methods/headers, origin
   validation, CSRF derivation, and protected-response cache policy.
7. Freeze session-token entropy/encoding, HMAC domain separation, secret
   minimum, collision retry cap, consent version, 180-day identity expiry,
   90-day event retention, and no-sliding-refresh semantics.
8. Freeze preference family bounds, canonical storage, replace-all/no-op/stale
   semantics, and client-weight rejection.
9. Freeze feedback full-resource semantics, rating step, reaction precedence,
   supersession model, current-state queries, concurrency lock, and `viewed`
   non-goal.
10. Freeze positive-feedback source classification/cap, dislike/source
    exclusions, wishlist neutrality, 90/10 affinity blend, played factor,
    fixed-point reconstruction, and complete tie-break.
11. Freeze personalized transaction ownership, event meaning, event success/
    failure policy, JSON field allowlists, item/byte limits, and legacy-event
    compatibility.
12. Produce a small threat/privacy checklist covering implicit tracking, raw
    token leakage, CSRF, origin spoofing, session fixation, session collision,
    cross-user access, stale consent, expired-session resurrection, logging,
    Web Storage, retained trace output, and destructive cleanup.
13. Confirm that Python standard-library `secrets`, `hmac`, `hashlib`, cookie,
    and existing framework capabilities are sufficient; add no dependency
    merely for token generation.
14. Define the exact environment validation matrix for local loopback HTTP,
    isolated E2E HTTP, and future production HTTPS.
15. Record which feature branches depend on which prior merges and agree that
    generated OpenAPI/client changes land after backend contracts stabilize.

### Verification

- `git status --short --branch` identifies the expected clean branch base.
- Existing direct and Docker commands run from their documented directories.
- Current `POST /api/v1/recommendations` passes its database before/after
  no-write integration test.
- Current OpenAPI and committed TypeScript output agree.
- All three Compose definitions validate without rendering secrets.
- A schema/query inventory names every existing constraint, index, cascade,
  JSON check, expected revision constant, CORS method, and browser client method
  that Stage 4 will change.
- The reviewed contract document contains no unresolved implicit-write,
  retention, or deletion behavior.

### Exit Criteria

- Stage 1–3 baseline behavior is green or every unrelated pre-existing failure
  is documented and resolved before Stage 4 implementation.
- Consent, identity, preferences, feedback, personalized ranking, events,
  retention, and deletion have one reviewed contract.
- The stateless endpoint compatibility and no-write guarantee are explicit.
- Proposed cryptographic and browser controls have a concrete test plan.
- No dependency, migration, endpoint, cookie, or write has been introduced.

## 8. Implementation Phase 1: Schema, Migration, and Persistence Invariants

### Objective

Create a data-preserving PostgreSQL foundation for consent-aware anonymous
identity and temporal feedback state before exposing any write endpoint.

### Work

1. Add `0003_stage_4_anonymous_identity` with token-digest, consent, expiry,
   revocation, consistency checks, unique lookup, and retention indexes.
2. Backfill legacy rows with non-authenticating revocation digests, preserve
   related rows, leave consent null, verify the backfill, then remove the
   plaintext-key column and uniqueness contract.
3. Update the `User` ORM model so new rows require complete consent lifecycle
   values through the application boundary.
4. Add `0004_stage_4_interaction_state` with `superseded_at`, temporal checks,
   current reaction/state partial unique indexes, and user/game current-state
   lookup indexes.
5. Reconstruct legacy supersession deterministically by occurrence time and
   primary key without deleting historical rows; resolve liked/disliked in one
   reaction timeline.
6. Update ORM mapping and relationship behavior without changing user-delete
   cascades or the game foreign-key `RESTRICT` policy.
7. Keep recommendation-event migration in the owning personalized-event phase
   so its final identity/payload contract cannot drift from code.
8. Update the expected Alembic revision in application readiness and
   integration fixtures after each merged revision.
9. Add migration tests from an empty database, `0001`, `0002`, and a populated
   legacy fixture containing users, preferences, duplicate/conflicting
   interactions, and recommendation events.
10. Add upgrade, downgrade/re-upgrade, `alembic check`, model/metadata, index,
    check-constraint, uniqueness, cascade, and data-preservation assertions.
11. Confirm seed behavior remains catalog-only and never creates a user or
    rewrites Stage 4 state.
12. Update data-model documentation with planned/implemented truth as each
    migration lands.

### Verification

- A fresh disposable PostgreSQL instance upgrades to the new expected head.
- A populated `0002` fixture upgrades without losing user-owned or catalog
  rows; legacy sessions cannot authenticate.
- The plaintext anonymous-key column is absent from the application schema and
  no longer addressable by runtime queries; physical heap/WAL/backup erasure is
  not claimed by `DROP COLUMN`.
- Digest uniqueness, consent all-or-none, expiry ordering, temporal ordering,
  active reaction uniqueness, and active per-type uniqueness fail invalid SQL
  directly.
- Deterministic duplicate fixtures produce the same active/superseded rows on
  repeated rebuilds.
- Deleting a user cascades owned rows while games and taxonomy remain.
- Downgrade behavior and any intentionally irreversible security transition
  are documented honestly rather than simulated unsafely.

### Exit Criteria

- The schema can represent identity and temporal current feedback without an
  API write.
- Legacy placeholder data is preserved and revoked through a tested policy.
- Application readiness agrees with the real Alembic head.
- Database constraints enforce the final race-sensitive invariants.
- Stage 1–3 schema, seed, catalog, artifact, and recommendation tests remain
  green.

## 9. Implementation Phase 2: Anonymous Identity, Consent, Cookie, and CSRF

### Objective

Activate one explicit, secure, testable anonymous identity lifecycle without
creating implicit tracking or exposing credentials.

### Work

1. Add validated settings for session secret, consent version, cookie name/
   path/SameSite/Secure/TTL, environment mode, origin allowlist, and retention
   caps.
2. Implement domain-separated token-digest and CSRF derivation with
   constant-time comparisons, bounded collision retry, and injectable
   entropy/clock fixtures.
3. Add anonymous-user repository operations for create, resolve active,
   resolve unexpired lifecycle-only, lock, re-consent without credential
   rotation, revoke, and delete without returning raw token data.
4. Add a dependency that only parses/validates protected cookie, Origin, and
   CSRF material and derives the lookup digest. It performs no database query;
   the transaction-owning service establishes isolation before resolving and
   locking the user. The dependency does not run globally or on stateless
   routes.
5. Implement `POST /api/v1/anonymous-sessions` with exact consent validation,
   exact-Origin/JSON bootstrap, browser preflight coverage, 201 create,
   CSRF-protected idempotent active reaffirmation, unexpired outdated-session
   re-consent without credential rotation, and no replacement creation on
   invalid/expired-cookie errors.
6. Implement `GET /api/v1/me` bootstrap metadata/CSRF and `DELETE /api/v1/me`
   transactional cascade/clear-cookie behavior.
7. Emit exact cookie and clearing attributes; ensure the raw token appears only
   in `Set-Cookie` and request-cookie parsing.
8. Enable credentialed CORS only for exact configured origins and required
   methods/headers.
9. Enforce exact unsafe `Origin` and CSRF on protected `POST`, `PUT`, and
   `DELETE` requests before repository mutation.
10. Apply `Cache-Control: no-store` to session and protected user responses.
11. Add standard safe error mappings for missing, malformed, invalid, expired,
    outdated-consent, forbidden-origin, CSRF, collision, and database cases.
12. Add structured log redaction tests and verify that identity/CSRF values do
    not appear in normal access, error, startup, or exception output.
13. Document local/E2E settings without committing a real session secret.

### Verification

- No catalog, detail, metadata, health, model-status, stateless recommendation,
  malformed, unready-model, or page-load path creates a user or sets a cookie.
- Explicit current-version consent creates exactly one user and one correct
  cookie; repeating with a valid session creates no second user.
- Unexpired outdated-consent re-consent preserves the token/digest, updates the
  absolute lifecycle once, and recovers an uncertain response through
  bootstrap without extending expiry on that read.
- An expired token receives no lifecycle/CSRF, is cleared, and cannot recover
  the old row; a later deliberate consent creates a distinct user while the
  old row remains cleanup-eligible.
- Raw tokens are absent from database columns, response JSON, application
  logs, exception details, generated OpenAPI examples, and committed fixtures.
- Missing, altered, legacy, expired, revoked, and wrong-secret tokens fail
  closed and expose no lifecycle/CSRF or owned data. Only an unexpired
  outdated-consent session may use the exact lifecycle/delete/re-consent
  behavior from Section 5.2.
- Missing/wrong CSRF and rejected/missing browser origin change no data.
- Allowed and rejected credentialed preflights cover `POST`, `PUT`, and
  `DELETE`; wildcard origin configuration is rejected.
- Session A cannot resolve, delete, or observe session B.
- A successful delete commits all cascades, returns 204, and expires the exact
  cookie attributes.

### Exit Criteria

- Identity exists only after explicit consent.
- Credential, consent, expiry, CSRF, origin, delete, and error semantics are
  complete and test-backed.
- The server never accepts a client-selected identity or exposes internal IDs.
- Stateless Stage 3 behavior remains cookie-agnostic and write-free.

## 10. Implementation Phase 3: Preferences and Feedback Write Contracts

### Objective

Persist and rehydrate bounded positive preferences and canonical current
feedback through atomic, idempotent, user-isolated contracts.

### Work

1. Add preference and feedback Pydantic schemas with exact fields, bounds,
   distinctness, rating step, unknown-field rejection, and stable responses.
2. Implement preference repositories for current-set reads, set-difference
   replacement, clearing, and stale-reference inspection scoped by user.
3. Implement feedback repositories that aggregate active temporal rows into
   one current resource, apply the exact page/page-size/order envelope,
   supersede changed state, and clear current state.
4. Resolve every public game ID and taxonomy slug against one consistent
   catalog view before any mutation and hold referenced rows with
   `FOR SHARE` through preference commit so slug updates as well as deletion
   cannot invalidate the just-validated state before commit.
5. Lock the owning user for replacement and feedback state transitions; rely
   on partial uniqueness as final concurrent-race protection.
6. Store canonical stable slugs and server-owned preference weights; reject
   every client weight or unknown field.
7. Make repeated identical preference/feedback `PUT` and empty `DELETE` true
   no-ops with no timestamp or history change.
8. Preserve rating plus reaction/played/wishlist combinations and document
   ranking precedence without silently normalizing user data.
9. Expose bounded stale preference details and reject personalized use until
   stale state is corrected.
10. Add thin authenticated routes and standard 401/403/404/409/422/503 error
    behavior.
11. Extend OpenAPI and API tests but defer frontend type regeneration until
    the protected contract stabilizes.
12. Confirm no route automatically writes `viewed`.

### Verification

- Preference `GET`/`PUT`/`DELETE` cover empty, create, replace, shrink, clear,
  canonical ordering, exact bounds, duplicate, unknown reference, stale
  reference, and rollback behavior.
- Feedback covers every reaction/played/wishlist/rating combination, half-step
  bounds, full replacement, reaction transition, clearing, and stable
  pagination.
- Identical requests do not add interaction rows or change timestamps.
- Like and dislike cannot both remain active under concurrent requests.
- Played, wishlist, and rating remain independent active dimensions.
- Failed reference validation leaves the complete prior state unchanged.
- Session A cannot read or mutate session B state even when IDs overlap.
- User deletion cascades active and superseded interactions and preferences.
- Catalog/model/stateless recommendation table counts remain unchanged.

### Exit Criteria

- Durable context and feedback can be written and rehydrated safely.
- Database and application semantics agree under repeated and concurrent use.
- No personalized ranking or recommendation event is active yet.
- OpenAPI describes the complete backend write contract truthfully.

## 11. Implementation Phase 4: Pure Feedback-Aware Ranking Policy

### Objective

Implement independently testable dislike filtering, positive-feedback affinity,
and played adjustment over the immutable Stage 3 artifact without identity,
database, or HTTP coupling.

### Work

1. Add frozen ML schemas for saved context, active feedback input, policy
   identity, adjustment components, evidence, and personalized results.
2. Define policy configuration for source classification/cap, 90/10 blend,
   played factor, fixed scale, rounding, source/exclusion behavior, and
   tie-breaking.
3. Resolve saved and feedback database values to stable artifact slugs in the
   API adapter; the ML package receives no user ID or token material.
4. Extract a shared pre-truncation base candidate-scoring primitive and keep
   the existing Stage 3 `rank()` method as a compatibility ordering/top-K
   wrapper over it.
5. Classify positive sources from liked or reaction-free rating >=7 state,
   with reaction precedence, recent-five cap, deterministic timestamp/slug
   tie behavior, and deduplication.
6. Construct a normalized positive centroid from existing artifact vectors
   and compute bounded cosine-equivalent affinity.
7. Exclude dislikes, saved example games, and positive source games before
   final ordering; retain the zero-primary-content rule.
8. Blend base/affinity only when a profile exists; otherwise preserve exact
   Stage 3 score/order.
9. Apply the played factor through fixed units and preserve wishlist as an
   explicit no-ranking-effect state.
10. Emit reconstructible base raw units, active base weight/contribution,
    affinity raw/weight/contribution, pre-played units, played factor/delta,
    final units, policy identity, source evidence, and final rank.
11. Keep candidate filtering/scoring over the shared complete bounded
    candidate set before `top_k`; never wrap an already truncated result.
12. Add adversarial fixtures for all exclusions, top-K refill, conflicts,
    caps, near ties, constant/zero affinity, played boundaries, and exact
    fixed-unit reconstruction.
13. Confirm whether the separate policy can use the existing artifact without
    a model rebuild. If artifact-owned behavior changes, follow the explicit
    model/version/path rotation instead.

### Verification

- Every disliked game is absent for every top-K/tie arrangement.
- Filtered candidates are replaced by the next eligible ranked candidates
  rather than shortening a result incorrectly.
- Positive sources and self-source exclusions match the reviewed precedence
  and cap.
- Base raw/weight/contribution, feedback affinity/weight/contribution,
  pre-played units, played factor/delta, and final score reconstruct exactly
  from fixed units.
- No profile and no played state yields the exact Stage 3 ordered slugs and
  serialized base scores.
- Wishlist alone changes neither score nor order.
- Feedback cannot reintroduce a selected/source/zero-content candidate.
- Repeated inputs produce identical rank, score, components, evidence, and
  tie resolution on supported runtimes.
- Artifact members, checksums, arrays, and data fingerprint are not mutated.
- ML inputs/results contain no database user ID, token, digest, consent, or
  cookie value.

### Exit Criteria

- The personalization policy is pure, deterministic, versioned, bounded, and
  independently observable.
- Base Stage 3 behavior remains reproducible and separately testable.
- No API route or database event write depends on unfinished ranking behavior.
- Exact policy limitations are documented without a quality claim.

## 12. Implementation Phase 5: Personalized Orchestration and Event Logging

### Objective

Expose saved-context recommendations through a deliberate read-write
transaction and commit one bounded identity-correct event for every successful
personalized generation.

### Work

1. Add `0005_stage_4_event_contract` with unique generation ID,
   event-schema, data-fingerprint, policy identity, conditional legacy/new-
   event integrity, and query indexes.
2. Update ORM models and event repository with typed context/result builders,
   canonical JSON, item/string/byte limits, and no arbitrary caller-provided
   JSON.
3. Refactor catalog repository transaction ownership so the stateless caller
   retains read-only behavior and the personalized caller establishes
   read-write repeatable-read before its first query.
4. Implement personalized orchestration: validate model readiness, resolve and
   lock identity, load saved preferences/feedback/catalog, reject stale
   context, compare artifact fingerprint, rank, serialize response/event,
   insert event, and commit.
5. Include the exact base model name/version/data fingerprint and separate
   policy name/version in response and event.
6. Compute the fingerprint over the full canonical effective dislike, played,
   and bounded source state used by the policy; store bounded source detail and
   counts/fingerprint rather than claiming a standalone event snapshot.
7. Log successful empty personalized generations with an empty result array
   and documented response reason.
8. Return no HTTP 200 if event validation, insertion, foreign-key locking, user
   expiry/deletion race, or commit acknowledgement fails; surface the
   post-commit acknowledgement window as an ambiguous generation outcome.
9. Keep `POST /api/v1/recommendations` on its existing service path, ignore
   cookie/CSRF, and extend its table-count proof with an attached valid cookie.
10. Add event-response correlation assertions without claiming that commit
    means browser receipt/impression.
11. Extend generated OpenAPI schemas only after final response/error shapes are
    stable.

### Verification

- Every personalized HTTP 200 has exactly one committed event whose model,
  fingerprint, policy, context, result slugs, ranks, and fixed units match the
  response.
- A successful empty result records one event with an empty bounded summary.
- 4xx, model unavailable, catalog invalid/stale, event-limit failure, and
  explicit pre-commit rollback record zero events and return no success.
- Missing commit acknowledgement returns no HTTP 200; the matching event may
  exist if PostgreSQL committed before the connection failed. The UI does not
  automatically retry, and the unique generation ID supports audit.
- Stateless recommendation records zero events/preferences/interactions/users,
  even when a valid Stage 4 cookie is attached.
- Request/result JSON obey exact fields, shape, top-K, string, and byte limits;
  raw tokens, CSRF, headers, prose, descriptions, and internal user IDs are
  absent.
- Concurrent deletion and personalized generation serialize into documented
  outcomes with no orphan event or post-delete owned row.
- Event cleanup and user cascade preserve games, taxonomy, and artifacts.
- OpenAPI generation does not require a user session or ready artifact.

### Exit Criteria

- Personalized generation and event commit form one explicit success contract.
- The stateless transaction and response contract remain unchanged.
- Event identity is sufficient for Stage 5/6 audit without overstating user
  behavior.
- Backend contracts are stable for frontend type generation.

## 13. Implementation Phase 6: Opt-In, Rehydration, Feedback, and Clear-Data UX

### Objective

Add an accessible durable-personalization experience while retaining the
fully usable opt-out Stage 3 recommendation flow and keeping ranking in the
API/ML boundary.

### Work

1. Regenerate committed TypeScript contracts from the stable live OpenAPI
   document and fail on handwritten duplicate interfaces.
2. Extend the project-owned client with protected `GET`, `POST`, `PUT`, and
   `DELETE`, `credentials: "include"`, CSRF headers, no-store handling,
   cancellation, and standard identity/forbidden/conflict errors.
3. Keep public/stateless client calls uncredentialed unless a reviewed browser
   requirement proves otherwise; the stateless backend remains safe even if a
   browser supplies a cookie.
4. Add an explicit consent panel describing stored data, ranking use, fixed
   duration, clear-data control, opt-out alternative, and current consent
   version in plain language.
5. Ensure initial render and opt-out actions make no session or persistence
   request beyond deliberate bootstrap behavior that cannot create identity.
6. Establish a session only after affirmative action, keep CSRF in route memory,
   and rehydrate it through `GET /api/v1/me` after reload.
7. Load saved preferences and current feedback with cancellation and a single
   current-session key so stale or prior-session responses cannot win.
8. Separate request-only onboarding from save-and-personalize actions; no copy
   may imply that a stateless submission was saved.
9. Add preference save/replace/clear behavior with review, pending, success,
   stale-catalog, session-expiry, retry, and rollback states.
10. Add labeled reaction, played, wishlist, and rating controls to personalized
    results with full keyboard operation, disabled/pending state, and explicit
    persistence result.
11. Request a new personalized result from the API after deliberate feedback;
    never filter, adjust, or re-sort the current result in the browser.
12. Render base score, feedback contribution, played adjustment, final ranking
    score, policy identity, and evidence without percentages or quality claims.
13. Handle expired/invalid sessions by clearing stale route state and returning
    to an explicit new-consent choice; only an unexpired outdated session may
    re-consent into its existing state.
14. Add a confirmable clear-data action that deletes the current user, clears
    in-memory state, returns focus to a useful heading/action, and preserves the
    opt-out flow.
15. Keep token, digest, internal user ID, preferences, feedback, and CSRF out of
    URL/search parameters and browser persistent storage.
16. Update landing/navigation claims only after the real durable path passes
    integration tests.

### Verification

- A fresh browser context uses the complete stateless flow without `Set-Cookie`
  or any identity-visible UI state; PostgreSQL integration tests prove that the
  same routes create no user row.
- Explicit consent sets the expected cookie, saves preferences, generates a
  personalized result, and survives reload with rehydrated state.
- Feedback survives reload and a dislike is absent from the next server-ranked
  result; played adjustment/evidence is visible and reconstructible.
- A second browser context cannot see the first context's saved state.
- Clear data removes the cookie and returns to a useful consent/stateless state;
  PostgreSQL integration and the isolated full-stack audit prove that all
  user-owned rows were removed.
- Invalid/expired cookie, stale preferences, rejected origin, CSRF, network,
  validation, unavailable model, malformed response, and unexpected failure
  states are recoverable and truthful.
- Rapid save/feedback/recommend/delete actions cannot let superseded responses
  overwrite current state.
- Browser URL, `localStorage`, and `sessionStorage` contain no user identity or
  durable preference/feedback copy.
- Frontend renders API order and does not reconstruct ranking weights itself.

### Exit Criteria

- Opt-in and opt-out experiences are both complete and accurately labeled.
- Durable state can be created, rehydrated, changed, expired, and deleted
  accessibly.
- All browser access remains through generated types and the one API client.
- No client-side persistence or ranking boundary has been introduced.

## 14. Implementation Phase 7: Retention and Safe Operational Commands

### Objective

Provide an explicit, bounded, reviewable way to inspect and purge expired
events/users without hiding destructive work in startup, migration, tests, or
general development commands.

### Work

1. Add a retention service with injected UTC clock, separate event/user
   cutoffs, stable primary-key ordering, and bounded batch size.
2. Add a command module with dry-run/preview default and an unmistakable
   execution subcommand that requires explicit cutoff, bounded batch size,
   resolved database fingerprint, and typed confirmation.
3. Report aggregate eligible/processed/remaining counts and cutoffs without
   printing token digests, contexts, result summaries, or user-level data.
4. Purge expired recommendation events independently before expired consented
   users; let tested user cascades remove remaining owned state. Include revoked
   users only when the operator supplies the separate `--revoked-before` cutoff.
5. Recheck cutoff and eligibility inside each execution transaction and commit
   one bounded batch at a time.
6. Make interruption/retry idempotent; do not hold one unbounded transaction or
   broad table lock.
7. Require the same guarded database identity protections used by destructive
   integration setup when execution is invoked in automated tests.
8. Add an optional read-only `make retention-preview` wrapper. Keep execution
   as an explicit direct Python/Compose command so a broad Make target cannot
   accidentally purge the configured development database.
9. Add a separate preview/execute bulk-revocation command, with no Make wrapper,
   that selects the immutable identity-creation cohort through
   `--created-before` and marks selected active sessions with `revoked_at`. Key
   retirement must quiesce creation/re-consent on the old secret, drain in-flight
   requests, capture the database-time cutover while switching issuance to the
   new secret, preview/execute the cohort until `remaining` is zero, and only
   then retire the old secret. It preserves owned data until explicit
   deletion/retention.
10. Confirm `make up`, API/web startup, migration, seed, model build, and broad
    test targets never call purge or revocation execution.
11. Document that Stage 4 provides no scheduler and that production scheduling,
    alerting, backup coordination, media sanitization, and legal-policy review
    remain Stage 7 work.

### Verification

- Preview changes no row and reports stable bounded counts for a fixed clock.
- Execute deletes only events/users at or before the documented cutoff and
  leaves newer state untouched.
- User purge cascades preferences, active/superseded interactions, and events
  while preserving catalog/taxonomy/artifact data.
- Interrupted execution resumes without duplicate work or expanded scope.
- Concurrent renewal/delete/generation follows documented locking and cutoff
  behavior.
- Bulk-revocation preview changes no row; `--created-before` remains stable when
  re-consent updates `consented_at`; confirmed execution marks only the selected
  active creation cohort; `remaining` reaches zero before old-secret retirement;
  and restoring an old HMAC secret cannot reactivate revoked rows.
- Batch size, duration, cutoff, confirmation, and unsafe database identity are
  validated and bounded.
- Execution acceptance runs only against disposable PostgreSQL.

### Exit Criteria

- Retention behavior is explicit, previewable, bounded, and idempotent.
- No ordinary command performs hidden deletion.
- User-triggered deletion and time-based retention remain distinct contracts.
- Production scheduling is not implied.

## 15. Implementation Phase 8: Docker, Configuration, and Full-Stack Fixtures

### Objective

Exercise real cookie, origin, CSRF, persistence, artifact, event, and deletion
behavior on a disposable full stack without touching persistent development
data.

### Work

1. Extend `.env.example` with documented non-secret consent, cookie, origin,
   session-secret placeholder, expiry, event-retention, and batch settings.
2. Validate secure/insecure environment combinations in API settings and
   Compose interpolation without printing real secret values.
3. Preserve explicit migrate, seed, model-build, model-validate, and startup
   ordering; none may create an anonymous user.
4. Add one reserved-domain E2E hostname for web and API on distinct ports and
   align browser base URL, public API URL, CORS origins, and cookie expectations.
5. Keep the E2E database in `tmpfs`, model artifact in a disposable named
   volume, API artifact mount read-only, and all app/test workloads non-root
   after the existing narrow volume-init step.
6. Add deterministic E2E setup for consent/session settings without committing
   the secret or exposing it in browser output.
7. Add isolated opt-out and opted-in browser fixtures with one browser context
   and one user per test; avoid suite-global user-count assertions under
   parallel execution.
8. Add a one-shot read-only database audit for a dedicated isolated full-stack
   scenario to prove no implicit-user write and clear-data cascades. Do not add
   a test-only HTTP endpoint or use global row counts in parallel browser tests.
9. Exercise retention and revocation execution only through a separate
   disposable fixture, not as part of normal E2E startup or teardown.
10. Update Make help/labels from Stage 3 while preserving all existing command
    meanings and direct equivalents.
11. Ensure teardown removes only E2E containers, network, artifact volume,
    browser results, and tmpfs data.

### Verification

- Development, PostgreSQL-test, and E2E Compose definitions validate.
- A fresh stack migrates to the Stage 4 head, seeds, builds/validates the
  artifact, starts ready API/web services, completes opt-out and opt-in flows,
  commits an event, reloads state, changes feedback, and clears data.
- The dedicated post-flow database audit proves the stateless path created no
  user and clear-data left no owned row, without exposing database state to the
  browser application.
- Browser cookie transport works through exact host `gamelens.test` on ports
  3000/8000 rather than a mocked header.
- HTTP E2E uses its explicit insecure test setting while production-profile
  configuration tests reject `Secure=false`.
- Persistent development database/artifact/web volumes are never mounted into
  disposable tests or removed by teardown.
- No runtime package installation, migration, seed, artifact build, user
  creation, or retention purge is hidden in web/API startup.

### Exit Criteria

- Real full-stack identity and persistence behavior is reproducible from a
  fresh checkout with explicit commands.
- Cookie/CORS/CSRF behavior is proven in a browser-relevant topology.
- Test resources remain isolated, bounded, and disposable.
- Existing direct host workflows remain documented and viable.

## 16. Implementation Phase 9: Test Matrix and Quality Gate

### Objective

Prove migration safety, privacy, deterministic personalization, contract
compatibility, accessible product behavior, and complete earlier-stage
regression before release documentation claims completion.

### Identity, Configuration, and API Fast Suite

Cover:

- Cookie name/path/SameSite/Secure/TTL and consent-version validation.
- Production refusal of weak secrets and insecure cookie/origin combinations.
- Deterministic clock and entropy fixtures without fixed production secrets.
- Token creation, valid reuse, collision retry, malformed, invalid, expired,
  revoked, legacy, wrong-secret, and clear-cookie behavior; unexpired
  outdated-consent re-consent keeps the digest, and uncertain response recovery
  performs no sliding extension.
- Raw token/CSRF absence from JSON, database-facing objects, logs, exceptions,
  OpenAPI examples, and fixtures.
- No implicit identity on every public/stateless/error path.
- Exact-Origin and JSON/preflight enforcement on initial consent before any
  identity write, with no claim that a pre-session CSRF value exists.
- Standard 401/403/404/409/422/503 envelopes.
- Exact allowed/rejected credentialed preflights and unsafe Origin/CSRF for
  `POST`, `PUT`, and `DELETE`.
- Explicit commit/rollback ownership for every write use case.

### Persistence Service and Repository Suite

Cover:

- Preference replace/get/delete, bounds, canonical order, stale references,
  no-op timestamp behavior, client-weight rejection, and atomic rollback.
- Feedback create/change/clear, reaction precedence, rating half-steps,
  played/wishlist independence, temporal history, stable pagination, repeated
  writes, and unknown/deleted games.
- Concurrent like/dislike and multi-tab replacements.
- Cross-session read/write/delete isolation.
- No implicit viewed interaction.

### PostgreSQL Integration Suite

Cover:

- Empty and populated migration paths, current Alembic head, `alembic check`,
  downgrade/re-upgrade, constraints, partial indexes, and preserved legacy
  data.
- Digest uniqueness, consent/expiry checks, temporal state uniqueness, JSON
  shape checks, and event application bounds.
- Preference/feedback atomicity and concurrent transactions under PostgreSQL,
  not only SQLite/unit metadata.
- User deletion and retention cascades with catalog preservation.
- Exactly one matching event per personalized 200, zero on each documented
  pre-commit failure, and the specified ambiguous outcome when commit succeeds
  but acknowledgement is lost.
- Stateless table counts unchanged with and without a valid cookie.
- Guarded disposable database reset and retention execution.

### ML and Ranking Suite

Cover:

- Disliked/source/saved-example exclusion before top-K under tie and refill
  cases.
- Positive-source classification, reaction precedence, recent-five cap, stable
  timestamp/slug tie, centroid, affinity, and zero/constant behavior.
- 90/10 conditional blend, no-feedback exact base compatibility, played factor,
  wishlist neutrality, fixed-point bounds, finiteness, reconstruction, and
  complete ordering.
- Feedback cannot promote zero-primary-content candidates.
- Repeated deterministic output across supported Windows/Linux numerical
  runtime fixtures.
- Base artifact/member/checksum/fingerprint immutability and complete absence
  of identity data.

### Frontend Fast Suite

Cover:

- Generated typed protected contracts and one client with credentials,
  `PUT`/`DELETE`, CSRF, cancellation, and error categorization.
- Consent state machine and proof of no creation request before affirmation.
- Session bootstrap/rehydration, preference save/replace/clear, feedback state,
  personalized results, expiry, stale consent/catalog, retry, and clear data.
- Superseded request protection and pending/rollback behavior.
- Opt-out/stateless fallback and accurate saved/not-saved copy.
- No identity/profile data in URL, `localStorage`, or `sessionStorage`.
- API order/component/evidence rendering without browser ranking.

### Browser, Accessibility, and Responsive Suite

The complete Chromium path and critical Firefox/WebKit smoke paths cover:

- Fresh-context stateless use with no identity cookie or identity-visible UI;
  database non-creation is proved in the PostgreSQL suite.
- Explicit consent, save, personalized generation, reload rehydration, feedback
  persistence, dislike exclusion, played evidence, and clear data.
- A second isolated browser context with no cross-user data.
- Invalid-cookie recovery, API/network failure, and rapid/double-action
  behavior. A hybrid re-consent case injects an outdated `GET /me` response
  while its protected `POST` uses the real stack. Real Origin and CSRF
  rejections are also browser-tested; expiry/re-consent mutation remains
  API/PostgreSQL evidence.
- Keyboard-accessible consent, selections, feedback, retry, delete, and focus
  recovery. Rating bounds and keyboard-operable control semantics are covered
  by component/API tests rather than claimed as a dedicated browser path.
- Useful status/live-region announcements and no serious/critical axe findings.
- No page-level overflow at 320, 768, and 1440 CSS pixels.
- No unhandled page errors, hydration failures, console credential output, or
  identity data in storage.

### OpenAPI, Regression, Operations, and Privacy Suite

Cover:

- OpenAPI generation without a ready artifact or active user.
- Generated TypeScript drift and no handwritten duplicate contracts.
- All Stage 1–3 API, ML, web, browser, CORS, artifact, seed, readiness, and
  Docker regressions.
- All Compose definitions and fresh explicit full-stack lifecycle.
- Dependency locks, `pip check`, npm audits, licenses, vulnerability findings,
  secret scan, ignored-output review, and final diff inspection.
- Logs, manifests, Web Storage, screenshots, coverage, and retained test
  artifacts scanned for raw tokens, CSRF, secrets, unexpected context, database
  dumps, and personal data. Protected-cookie Playwright traces stay disabled by
  default; any explicit diagnostic trace is sensitive, disposable, ignored,
  access-limited, and deleted after the investigation.
- Diagnostic query/generation/event/retention timings and coverage gaps without
  unsupported SLO or quality claims.

### Exit Criteria

- Every acceptance criterion in Section 19 has direct automated or documented
  manual evidence.
- Complete Stage 1–3 regression gates remain green.
- Serious/critical security, privacy, data-loss, isolation, deterministic, or
  accessibility failures block completion.
- Coverage remains diagnostic; meaningful lifecycle/error/concurrency gaps are
  fixed rather than hidden behind a percentage.
- Disposable resources are removed and persistent development resources remain
  untouched.

## 17. Implementation Phase 10: Documentation and Release Preparation

### Objective

Synchronize verified implementation behavior, commands, privacy boundaries,
evidence, known limitations, and the Stage 5 handoff without converting planned
claims into facts prematurely.

### Work

1. Update the root README current status, implemented experience, architecture,
   setup, command, environment, verification, documentation, and limitations.
2. Update `apps/api/README.md` with exact session, preference, feedback,
   personalized recommendation, event, transaction, cookie, CORS/CSRF,
   retention, migration, error, and quality contracts.
3. Update `apps/web/README.md` with opt-in/opt-out ownership, rehydration,
   protected transport, feedback, clear-data, expiry, storage, accessibility,
   and browser behavior.
4. Update `ml/README.md` with final policy identity, source classification,
   exclusions, blend, played adjustment, numeric/tie behavior, fixtures, and
   artifact-identity boundary.
5. Update `infra/README.md` with exact-host topology, environment-aware cookie
   settings, disposable lifecycle, retention-test safety, and teardown scope.
6. Update architecture, data model, recommendation design, and roadmap from
   planned to verified behavior only after tests pass.
7. Record exact migration revisions, runtime/dependency versions, final tests,
   diagnostic coverage/timings, security/privacy findings, and known gaps in
   Section 21 and the completion record.
8. Record a representative deterministic personalized request/state and result
   only as functional/reproducibility evidence, not a quality claim.
9. Document event semantics precisely: committed generation, not impression,
   view, click, conversion, like, or success.
10. Replace the provisional Stage 5 handoff with exact current/temporal
    interaction and event fields that downstream collaborative work may use.
11. Verify every documented command from its stated working directory and
    remove any command that has not actually passed.
12. Review final Git diff/status for generated artifacts, DB dumps, cookies,
    secrets, traces, local paths, unrelated changes, and accidental personal
    data.

### Suggested Commit Structure

1. `feat(api): establish consented anonymous identity lifecycle`
2. `feat(api): persist preferences and temporal feedback state`
3. `feat(ml): add deterministic feedback adjustment policy`
4. `feat(api): log personalized recommendation generations`
5. `feat(web): add opt-in persistence and feedback experience`
6. `chore(data): add guarded retention operations`
7. `test(stage-4): add full-stack persistence acceptance`
8. `docs(stage-4): record verification and Stage 5 handoff`

Actual commits may combine tightly coupled migration/service/tests, but every
commit must leave the repository migratable, testable, and truthful. Generated
OpenAPI output lands with the backend contract it represents. Formatting-only
or unrelated cleanup does not belong in the Stage 4 integration diff.

### Exit Criteria

- Roadmap, root, architecture, data, recommendation, API, web, ML,
  infrastructure, environment, command, and Stage 4 plan docs agree.
- Planning language has changed to implemented language only for verified
  behavior.
- All commands in documentation have passed exactly as written.
- Section 21 contains resolved implementation decisions and Section 23 contains
  measured evidence rather than placeholders.
- The final diff contains only intentional Stage 4 source, migration, generated
  contract, tests, config examples, and documentation.

## 18. Command Interface Target

Exact module names and flags are confirmed in Phase 0. The target command
capabilities are:

| Capability                         | Optional Make wrapper                      | Direct equivalent required                                |
| ---------------------------------- | ------------------------------------------ | --------------------------------------------------------- |
| Validate all Compose definitions   | `make config`                              | Existing quiet validation for all three Compose files     |
| Build API/web development images   | `make build` / `make build-web`            | Existing explicit Docker Compose builds                   |
| Upgrade schema                     | `make migrate`                             | Existing Alembic container command                        |
| Seed deterministic catalog         | `make seed`                                | Existing catalog-only seed command                        |
| Build/validate model artifact      | `make model-build` / `make model-validate` | Existing explicit immutable artifact commands             |
| Run ML fast tests                  | `make test-ml`                             | pytest against `ml/tests`                                 |
| Run API fast tests                 | `make test`                                | Existing quality-container pytest command                 |
| Run PostgreSQL integration tests   | `make test-integration`                    | Existing guarded disposable Compose command               |
| Run web quality gate               | `make test-web`                            | Existing npm type/lint/format/test/build/drift commands   |
| Run isolated browser acceptance    | `make test-web-e2e`                        | E2E Compose command with exact-host Stage 4 topology      |
| Lint/format Python and web         | Existing lint/format targets               | Existing Ruff/Prettier direct commands                    |
| Refresh generated OpenAPI types    | `make api-types`                           | Existing npm generation command                           |
| Preview expired data               | `make retention-preview`                   | Explicit Python/Compose dry-run retention command         |
| Purge eligible expired data        | —                                          | Explicit confirmed Python/Compose execute command only    |
| Preview/revoke active sessions     | —                                          | Explicit direct preview/confirmed bulk-revocation command |
| Start configured development stack | `make up`                                  | Existing explicit Compose startup after prerequisites     |

Existing command meanings remain stable. `make up` may load configured
settings and an existing validated artifact; it must not migrate, seed, build
an artifact, create a user, renew consent, purge data, or revoke sessions.
`make test` and broad quality targets must not call retention or revocation
execution.

Retention preview is read-only and the default direct mode. The executing
command must require an explicit confirmation flag/subcommand, validate
cutoffs and batch size, require the resolved server/database/schema fingerprint
and typed confirmation, refuse unsafe test-reset configuration, and print no
user-level context. Bulk revocation has the same guard and no Make wrapper. If
Make portability makes confirmation ambiguous, only the direct retention
preview is wrapped and all execution remains direct.

GNU Make remains optional. Direct PowerShell, Python, npm, and Docker commands
are mandatory documentation. No wrapper hides a destructive action, network
installation, database reset, migration, seed, artifact build, or credential.

## 19. Acceptance Criteria

Stage 4 is complete only when all of the following are true:

- Stage 1, Stage 2, and Stage 3 acceptance gates remain green.
- `POST /api/v1/recommendations` retains its request/response/error contract,
  uses one read-only consistent catalog snapshot, ignores attached Stage 4
  identity, and writes no user-owned table.
- No catalog, metadata, detail, health, model-status, stateless recommendation,
  page-load, malformed, unavailable, or failed path creates a user or sets a
  session cookie.
- A user exists only after explicit true consent for the exact current consent
  version.
- Session tokens contain at least 256 bits of server-generated entropy and are
  never accepted from a client-selected identity field.
- The raw token is returned only in the documented host-only `HttpOnly` cookie
  and never appears in database state, JSON, URLs, logs, errors, fixtures, Web
  Storage, model artifacts, retained test artifacts, or committed output.
- PostgreSQL lookup uses a unique domain-separated keyed digest and
  constant-time verification where comparison is application-owned.
- Session and CSRF derivations are domain-separated and secret validation is
  environment-safe.
- Missing, malformed, altered, legacy, expired, revoked, and wrong-secret
  tokens fail closed without silent user creation or renewal.
- Active current-version consent reaffirmation is an exact no-op. An unexpired
  outdated-consent session exposes only the documented lifecycle/delete/
  re-consent path without credential rotation; expired and revoked sessions
  expose none of it and cannot recover the old identity.
- Cookie name, path, host-only scope, SameSite, Secure, Max-Age, clearing, and
  expiry semantics agree across API, browser, docs, and tests.
- Local/E2E insecure-cookie exceptions are explicit and production/HTTPS
  configuration refuses `Secure=false`.
- Credentialed CORS has exact origins, no wildcard, explicit methods/headers,
  and correct allowed/rejected preflight behavior.
- Every unsafe browser route, including initial consent, rejects a disallowed
  or missing Origin before mutation. Cookie-authenticated unsafe routes also
  reject missing/incorrect CSRF; initial consent instead requires the exact
  Origin plus JSON content-type contract because no session-derived CSRF
  exists; browser tests separately prove allowed/rejected preflight behavior.
- Protected responses use the documented no-store behavior.
- Session A cannot read, change, rank from, delete, or infer session B state.
- Consent version/time, fixed expiry, event retention, revocation, re-consent,
  and deletion use timezone-aware UTC with an injected test clock.
- No ordinary read or write silently extends the fixed session expiry.
- Legacy placeholder users are preserved/revoked without fabricated consent,
  plaintext-key authentication, or silent data loss.
- The migration chain upgrades empty, `0001`, `0002`, and populated legacy
  databases to the expected head.
- Alembic model/check output, readiness expected head, constraints, indexes,
  downgrade/re-upgrade behavior, and migration docs agree.
- No plaintext anonymous-key column or application-addressable legacy key
  remains after the identity migration; production backup/media erasure is an
  explicit Stage 7 lifecycle obligation rather than an unprovable migration
  claim.
- Preference requests are bounded, distinct, exact-field, fully
  reference-validated, and reject client-selected weights.
- Preferences store canonical stable slugs and server-owned positive weights.
- Preference `PUT` is atomic replace-all; identical replacement and empty
  deletion are idempotent no-ops.
- Stored stale references are reported rather than silently dropped or
  deleted; personalized generation fails with the documented recoverable
  conflict until correction.
- Feedback `PUT` is a full canonical resource and supports reaction, played,
  wishlist, and half-step rating 0–10 as documented.
- Feedback listing enforces the documented bounded page contract, stable
  ordering/tie-break, response envelope, and per-request snapshot behavior.
- At most one active liked/disliked reaction and one active played/wishlist/
  rating state exists per user/game under concurrent PostgreSQL writes.
- Changed feedback preserves occurrence/supersession history; identical writes
  create no duplicate/history/timestamp change.
- Rating/reaction coexistence and ranking precedence are explicit and tested.
- Stage 4 does not create implicit `viewed` interactions.
- All preference/feedback references validate before mutation and any failure
  rolls back the complete use case.
- User deletion cascades preferences, active and superseded interactions, and
  recommendation events while preserving games, taxonomy, and artifacts.
- Personalized generation uses saved preferences rather than reinterpreting a
  Stage 3 body as persisted history.
- A disliked game never appears in personalized results, including top-K refill
  and tie cases.
- Saved example and positive feedback source games do not recommend themselves.
- Positive feedback source classification, reaction precedence, recent-source
  cap, timestamp/slug tie behavior, and deduplication are deterministic.
- Wishlist behavior is explicitly persisted but neutral in policy version 1.
- Played adjustment is versioned, bounded, observable, and exactly
  reconstructible.
- Base Stage 3 content/platform/popularity components remain observable and
  reconstructible.
- Feedback affinity, weight, contribution, played factor/delta, pre-adjustment
  score, final score, and complete ordering use documented fixed units and
  round-half-up.
- No effective feedback and no played state produces exact Stage 3 base scores
  and ordered slugs.
- Feedback cannot reintroduce a selected, excluded, source, stale, or
  zero-primary-content candidate.
- Candidate filtering and personalization occur before top-K truncation.
- The same artifact, catalog, saved state, feedback, policy, and request option
  produce the same rank, scores, components, evidence, and reason.
- Ranking scores are not represented as probabilities, predicted ratings,
  percentages, or evidence of recommendation quality.
- Personalization policy identity is separate from the unchanged Stage 3
  artifact identity unless implementation explicitly bumps/rebuilds/rotates
  the artifact and records that decision.
- User identity, consent, preference rows, feedback rows, and events never
  enter or mutate model artifact members.
- Personalized recommendation owns the documented bounded repeatable-read
  read-write transaction from identity resolution through event commit.
- The stateless route retains its distinct repeatable-read read-only
  transaction.
- Every personalized HTTP 200 generation, including documented successful
  empty output, commits exactly one matching recommendation event.
- No documented 4xx, pre-commit model/catalog/database failure, event
  validation failure, explicit rollback, or stateless request commits a
  recommendation event.
- Event validation/insertion and acknowledged commit are required before HTTP 200. A lost commit acknowledgement returns the documented ambiguous error and
  may leave one committed event identified by `generation_id`; the UI does not
  automatically retry it.
- Recommendation events record exact event schema, model name/version, data
  fingerprint, policy name/version, bounded effective context/fingerprint, and
  compact top-K fixed-unit summary.
- Event JSON excludes token/CSRF, internal user ID, headers, IP/User-Agent,
  descriptions, explanation prose, and unrelated state.
- Event object/list/string/byte limits are enforced before insertion and top-K
  never exceeds 20.
- Event documentation states committed generation rather than impression,
  view, click, conversion, like, or quality.
- Event documentation calls the bounded record audit/correlation data, not a
  standalone reproducible snapshot after source state is deleted or retained
  detail is unavailable.
- Concurrent personalized generation and deletion produce only documented
  serialized outcomes with no orphan/post-delete owned row.
- The web creates no identity before consent and clearly distinguishes opt-out
  request-only behavior from saved personalization.
- Opt-in can establish a session, save preferences, generate personalized
  results, rehydrate after reload, change feedback, handle expiry, and clear
  all data.
- A second browser context is isolated from the first.
- Browser protected methods use generated contracts, credentials, CSRF,
  cancellation, and safe error categories through the one API client.
- Browser code never ranks, filters, reweights, or reorders recommendations.
- Token, internal user ID, preferences, feedback, and CSRF are absent from URL,
  `localStorage`, and `sessionStorage`.
- Consent, saving, feedback, retry, withdrawal, and clear data are
  keyboard-accessible with visible focus and useful announcements. Expiry and
  stale-state recovery semantics are additionally verified at component and
  API/PostgreSQL layers.
- Automated accessibility checks pass under the documented serious/critical
  policy.
- Complete Chromium and critical Firefox/WebKit opt-in/opt-out flows pass.
- Stage 4 layouts have no page-level overflow at 320, 768, and 1440 CSS pixels.
- E2E proves real first-party cookie transport through exact host
  `gamelens.test` on ports 3000/8000 and does not replace it with a fabricated
  authentication header.
- Fresh full-stack setup migrates, seeds, builds/validates the artifact, starts
  ready services, completes stateless and persistent flows, writes an event,
  rehydrates feedback, and deletes state.
- E2E and integration resources use only disposable databases/artifacts and
  teardown removes only project-scoped resources.
- Retention preview is read-only, deterministic for a fixed clock, and reveals
  only bounded aggregate metadata.
- Retention execution is explicit, bounded, batch-transactional, idempotent,
  cutoff-safe, and accepted only against a verified disposable database in
  automated tests.
- Authentication expires at the documented fixed time; owned data becomes
  purge-eligible then and is removed on the next explicit operator run. No
  exact-time storage deletion is claimed without the deferred scheduler.
- Bulk revocation is separately previewable and confirmed, records
  `revoked_at`, selects the immutable creation cohort with `--created-before`,
  has no general Make wrapper, reaches zero remaining rows before old-secret
  retirement, and cannot be undone by restoring an old HMAC secret.
- No startup, migration, seed, model, broad test, or ordinary Make target
  performs retention execution.
- Production scheduling is not claimed or implemented.
- All Python/Node dependencies, exact locks, licenses, `pip check`, npm audits,
  vulnerability findings, and known base-image advisories are reviewed and
  documented honestly.
- Diagnostic coverage, migration/generation/event/retention timings, and
  meaningful gaps are recorded without unsupported service or quality claims.
- OpenAPI generation works without an active user or ready artifact and the
  committed TypeScript contract has no drift.
- No secret, raw credential, database dump, user context, generated model,
  browser trace, coverage output, local path, or unrelated artifact is
  committed.
- Root and application documentation contains only commands and behavior that
  were actually verified.
- Known limitations and the exact Stage 5 data handoff are documented.

## 20. Risks and Mitigations

**Risk:** A raw anonymous credential is persisted, logged, copied into a URL,
or captured in a test artifact.

**Mitigation:** Generate a 256-bit token, store only a domain-separated keyed
digest, use a host-only HttpOnly cookie, redact sensitive headers, prohibit Web
Storage/URLs, use synthetic one-test tokens, disable protected-flow traces by
default, and scan retained artifacts/diffs before completion.

**Risk:** Normal browsing silently creates an identity and becomes implicit
tracking.

**Mitigation:** Restrict user creation and `Set-Cookie` to the exact explicit
consent route and add negative write/cookie assertions for every public,
stateless, loading, and failure path.

**Risk:** An old frontend records consent for text or retention terms that the
server no longer supports.

**Mitigation:** Require the exact current consent version in the create body,
reject stale versions without writes, return current metadata only through the
controlled bootstrap, and test version rollout behavior.

**Risk:** Credentialed CORS is mistaken for authentication or leaves protected
writes vulnerable to CSRF.

**Mitigation:** Use a host-only SameSite cookie, exact allowed Origin checks,
domain-separated CSRF header, JSON/custom-header preflight, explicit methods,
no wildcard origins, and mutation-count tests for every rejection.

**Risk:** Local browser tests pass with mocked headers but real browser cookie
transport fails under Docker hostnames.

**Mitigation:** Use exact host `gamelens.test` for web/API on distinct ports,
exercise real browser cookies, align public/CORS URLs, and separately validate
secure production cookie configuration.

**Risk:** Session fixation, token collision, or secret rotation attaches state
to the wrong user.

**Mitigation:** Never accept a client token/user ID, use server CSPRNG, unique
keyed digests and bounded collision retry, and treat secret change only as a
coordinated key-retirement operation. Quiesce creation/re-consent, drain
in-flight requests, capture a database-time cutover while switching issuance to
the new secret, revoke the immutable `--created-before` creation cohort until
`remaining` is zero, retire the old secret, and prove an old key cannot
resurrect revoked rows.

**Risk:** Expired or invalid identity is silently replaced and unexpectedly
resumes tracking.

**Mitigation:** Fail closed, clear invalid/expired browser state safely, require
new affirmative consent for a new identity after expiry, allow retained-state
re-consent only for an unexpired outdated session, and never create/renew
inside the protected resolver.

**Risk:** Re-consent rotates the credential before the browser receives the new
cookie, so a lost response permanently strands retained state.

**Mitigation:** Keep the server-generated token/digest unchanged during
unexpired outdated-consent re-consent, update only consent lifecycle fields,
and recover an uncertain response with an authenticated lifecycle read that
does not extend the absolute expiry.

**Risk:** Migrating plaintext legacy keys either authenticates them as consented
sessions or destroys related data.

**Mitigation:** Backfill non-authenticating revocation digests, preserve rows
with null consent, drop plaintext only after verification, and test a populated
legacy upgrade plus explicit later retention.

**Risk:** Current-state and repeatable-interaction semantics remain ambiguous.

**Mitigation:** Add explicit supersession time, partial active uniqueness,
deterministic migration ordering, current-state queries, no-op rules, and
temporal-history documentation before exposing writes.

**Risk:** Concurrent like/dislike requests leave both reactions active.

**Mitigation:** Lock the user/state transition, supersede within one
transaction, enforce one active reaction with a partial unique index, and run
real concurrent PostgreSQL tests.

**Risk:** A preference or feedback replacement partially commits after an
unknown catalog value.

**Mitigation:** Resolve and validate the complete request before mutation,
compute a canonical change set, commit once, and assert rollback preserves the
exact prior state.

**Risk:** Repeating a UI action creates duplicate event history or changes
timestamps even though state is identical.

**Mitigation:** Compare canonical current state before writing, define
identical PUT/DELETE as no-op, and test counts/timestamps under retries.

**Risk:** A stored preference becomes stale after a catalog change and is
silently ignored, changing user intent.

**Mitigation:** Report bounded stale references and reject personalized use
until explicit replace/clear rather than mutating state implicitly.

**Risk:** Feedback is applied after top-K truncation, yielding missing or
incorrectly ordered candidates.

**Mitigation:** Run exclusions, affinity, and adjustments over the complete
bounded candidate set in the pure ranking boundary before final truncation.

**Risk:** Positive feedback double-counts content invisibly or silently changes
the Stage 3 model identity.

**Mitigation:** Preserve base components, expose a separate policy identity and
affinity contribution, conditionally blend with fixed units, and require an
artifact/model bump only if artifact-owned semantics change.

**Risk:** A liked/high-rated source recommends itself because its vector has
maximum similarity.

**Mitigation:** Treat bounded positive sources as evidence/context and exclude
them from their own candidate set before ordering.

**Risk:** Wishlist is assumed to mean liking and biases results without
evidence.

**Mitigation:** Persist and expose wishlist state but give it zero ranking
effect in policy version 1; revisit only with evaluation evidence.

**Risk:** Played adjustment or rounding makes response scores impossible to
reconstruct.

**Mitigation:** Quantize base, affinity, blend, factor, delta, and final values
with one scale/mode and return enough typed units/components to prove exact
reconstruction.

**Risk:** No-feedback users receive a different Stage 3 order merely because a
new policy layer exists.

**Mitigation:** Bypass the affinity blend when no positive profile exists,
retain 100% of the base score, and lock exact Stage 3 fixtures as regression
tests.

**Risk:** User identity or mutable state leaks into a singleton ranker/artifact
and crosses sessions.

**Mitigation:** Pass immutable bounded feedback context per call, prohibit
identity fields in ML schemas, keep artifacts read-only, and test interleaved
users against one application instance.

**Risk:** Event logging weakens the Stage 3 read-only transaction or logs a
different snapshot/result than the response.

**Mitigation:** Keep stateless and personalized transaction owners separate;
personalized ranking/event use one repeatable-read write transaction and assert
event fingerprint/slugs/units equal the response before commit.

**Risk:** Event failure still returns success, creating unaudited personalized
output.

**Mitigation:** Make event validation, insertion, and acknowledged commit part
of HTTP 200 success. Roll back known pre-commit failures; for a lost commit
acknowledgement, return an ambiguous error, avoid automatic retry, and use the
server-generated `generation_id` for audit because the event may exist.

**Risk:** A committed event is misread as an impression, click, conversion, or
positive label.

**Mitigation:** Name and document it as a committed server generation, omit
behavioral claims, and require explicit interactions for Stage 5 labels.

**Risk:** Event JSON grows without bound or captures sensitive context/prose.

**Mitigation:** Build JSON from typed allowlists, cap strings/lists/top-K/
serialized bytes, store compact stable identities/fixed units only, and reject
over-limit inserts before the database.

**Risk:** Concurrent clear-data and generation leave an event after deletion.

**Mitigation:** Lock the user through personalized commit and deletion,
preserve foreign-key cascades, define serialized outcomes, and test both lock
orders in PostgreSQL.

**Risk:** Cross-user data leaks through an unscoped repository query, cache, or
frontend stale response.

**Mitigation:** Require user ID predicates in every repository, use no
user-state cache/singleton, associate browser responses with the current
session key, and run two-session isolation tests.

**Risk:** Browser optimistic feedback shows saved state after an API rollback.

**Mitigation:** Prefer explicit pending state or retain prior state for rollback,
ignore superseded responses, announce failures, and reload authoritative state
when outcome is uncertain.

**Risk:** Session/profile data is copied into browser persistent storage for
convenience.

**Mitigation:** Keep credential in HttpOnly cookie and rehydrate route memory
from protected APIs; test URL and Web Storage remain empty.

**Risk:** Clear-data UI is difficult to discover or operate with a keyboard/
screen reader.

**Mitigation:** Use explicit text, native controls, confirmation, focus return,
live status, keyboard/browser tests, and automated accessibility checks.

**Risk:** Retention command deletes development or newer data through a broad
cutoff, retry, or accidental wrapper.

**Mitigation:** Default to preview, validate fixed bounded cutoffs/batches,
require explicit execution, recheck each transaction, guard automated database
identity, omit hidden invocation, and accept execution only on disposable data.

**Risk:** Temporal history and recommendation events are treated as a clean
real-world collaborative dataset in Stage 5.

**Mitigation:** Record synthetic/manual provenance, consent/deletion/retention
effects, active/superseded semantics, event meaning, and label rules in the
handoff; require Stage 5 to audit data suitability before modeling.

**Risk:** New credential/persistence code adds heavy dependencies or services.

**Mitigation:** Use standard library plus existing FastAPI/SQLAlchemy/browser
capabilities, justify every new direct dependency, and record lock/license/
vulnerability impact.

**Risk:** Stage 4 UI and plausible personalized results are presented as proof
that feedback improved quality.

**Mitigation:** Limit claims to lifecycle, determinism, integration, isolation,
and explainability; keep the synthetic-data warning and defer comparative
metrics to Stage 6.

## 21. Implementation-Time Decisions

The verified implementation resolves these contract decisions:

1. The host-only cookie is `gamelens_session`, scoped to `/api/v1`, HttpOnly,
   `SameSite=Lax`, fixed at 15,552,000 seconds (180 days), and configurable as
   Secure. Production requires Secure, HTTPS CORS origins, and a non-default
   secret; loopback development and reserved `.test` origins may use HTTP.
2. Sessions use 32 random bytes encoded as a 43-character URL-safe token.
   PostgreSQL stores only HMAC-SHA-256 with domain
   `gamelens:session:v1\x00`; CSRF uses the same token and separate domain
   `gamelens:csrf:v1\x00`. Secrets are 32-512 characters and token allocation
   retries a digest collision three times.
3. Consent version is `stage-4-v1`. New consent creates identity; a current
   unexpired session is a no-op; an unexpired outdated session requires its
   derived CSRF value, keeps the token, updates consent/time/expiry, and
   reissues the cookie. Missing, revoked, malformed, or expired credentials do
   not recover the old state. Session/deletion responses are `no-store`, and
   deletion expires the same cookie path.
4. Revisions are `0003_stage_4_anonymous_identity`,
   `0004_stage_4_interaction_state`, and
   `0005_stage_4_event_contract`; readiness expects the last identifier.
   Legacy plaintext identities receive exactly
   `md5('legacy-revoked-v1:' || anonymous_key) || lpad(to_hex(id), 32, '0')`
   plus revocation timestamps without fabricated consent; the ID suffix makes
   the 64-character value unique. The downgrade recreates unique
   non-authenticating placeholder keys.
5. Active reaction uniqueness covers null-`superseded_at` liked/disliked rows;
   active state-type uniqueness covers played/wishlisted/rated rows. Legacy
   duplicates are ordered by occurrence then ID, older rows are superseded,
   and application writes lock the user and affected state before one commit.
6. Preferences use bounded replace-all semantics with maximums 5 games, 5
   genres, 10 tags, and 6 platforms. At least one game/genre/tag is required;
   all references are validated before mutation, weights remain server-owned,
   responses are stable, and stale stored references are explicit conflicts.
7. Feedback represents nullable liked/disliked reaction, booleans for played
   and wishlisted, and an optional 0-10 rating in half-point increments.
   `GET /me/feedback` is ordered and bounded to page sizes 1-100. Replacement,
   clearing, mutual exclusion, and identical-write no-ops retain temporal
   history rather than deleting superseded rows.
8. Protected routes are `/api/v1/me`, `/api/v1/me/preferences`,
   `/api/v1/me/feedback`, `/api/v1/me/games/{game_id}/feedback`, and
   `/api/v1/me/recommendations`; identity creation is
   `/api/v1/anonymous-sessions`. Unsafe requests require exact normalized
   Origin plus `X-CSRF-Token`. Credentialed CORS permits explicit origins and
   `GET`, `POST`, `PUT`, and `DELETE`; protected successes are `no-store`.
9. Positive sources are likes or ratings at least 7 only when no reaction is
   active. The policy selects at most five sources by newest occurrence with a
   stable-slug tie-break, hard-excludes dislikes and positive source games,
   leaves wishlist neutral, blends base/affinity 90/10, and applies a 0.5
   played factor before top-K.
10. The policy is `gamelens-feedback-adjustment/1.0.0`. Fixed-point scale,
    half-up contributions, and final/pre-played/base/affinity/content/
    popularity/slug tie-break are explicit. The Stage 3 model
    `gamelens-content-tfidf/1.0.0`, artifact schema `1`, and compatibility
    `stage-3-v1` remain unchanged.
11. Personalized requests accept only `top_k` 1-20. Responses expose generation,
    model/data/policy identity, response reason, positive sources, base and
    affinity contributions, pre-played score, played factor/delta, final score,
    base evidence, and deterministic explanations. Empty eligible results are
    successful bounded generations.
12. New recommendation events use schema `stage-4-v1`, a unique 32-character
    generation ID, complete model/data/policy identity, bounded effective
    context plus SHA-256 effective-state fingerprint, and at most 20 compact
    result identities. Existing events become `legacy-v1`. Events are server
    generation audit/correlation records, not impressions or feedback labels.
13. Personalized work uses one repeatable-read read-write transaction from
    locked identity through catalog/context/feedback reads, ranking, event
    insertion, flush, and commit. A DBAPI commit error maps to an outcome-unknown
    error carrying the generation ID; no automatic retry or idempotency-key
    contract is added in version 1.
14. Recommendation events are cleanup-eligible after 90 days; sessions have a
    fixed 180-day expiry; default batches are 500 with a hard maximum of 10,000.
    `app.commands.retention` previews by default and requires explicit event and
    user cutoffs plus a database-fingerprinted confirmation to execute.
    `app.commands.anonymous_sessions` separately previews or confirms bounded
    bulk revocation selected by immutable identity `created_at` through
    `--created-before`. Key retirement quiesces old-secret creation/re-consent,
    drains requests, captures the database-time cutover while switching new
    issuance, revokes the cohort until `remaining` is zero, and then retires the
    old secret; online dual-key rotation is not implemented.
15. `make retention-preview` is the only Make retention wrapper. Startup,
    migration, seed, artifact, broad test, and teardown paths contain no purge
    or revocation execution. There is no scheduler.
16. The web owns Stage 4 state inside the recommendations feature, uses the
    generated contract and one project API client, rehydrates through `/me`,
    rolls back failed feedback updates, clears route memory after deletion, and
    keeps credentials/profile state out of URLs and Web Storage.
17. E2E uses exact host `gamelens.test` with web on port 3000 and API on port
    8000. The web service shares the API network namespace so both ports resolve
    to one endpoint; exact matching origins, `stage-4-v1`, a test-only secret,
    and Secure disabled only in the test profile remain explicit. The API
    remains network-only and the database/artifact lifecycle stays disposable.
18. No new direct Python or browser runtime dependency was required. The API
    package version advances to `0.3.0`. The Dockerfile removes unused Debian
    `perl-base` after all install steps, resolving its earlier two critical and
    two high findings. Rebuilt no-cache image `gamelens-ai-api:stage4-test` with
    digest prefix `11b2f940731e` passes runtime imports, `pip check`, and all 49
    PostgreSQL integration tests. Its comprehensive Docker Scout scan reports 0
    critical, 0 high, 3 medium, 27 low, and 2 unspecified findings across 193
    packages; its only-fixed scan reports no actionable fixed advisory. The
    remaining findings stay documented.

The populated `0002` upgrade and downgrade/re-upgrade, partial indexes,
transaction/concurrency, event/delete correlation, cascades, and bounded
retention pass in the 49-test PostgreSQL suite. The browser matrix covers real
first-party cookie transport, isolation, rehydration, feedback,
invalid-cookie recovery, clear-data, real Origin/CSRF rejection, and
stateless/active axe behavior. Its re-consent case is deliberately hybrid: an
injected outdated `GET /me` drives the UI while the protected `POST` reaches a
real current session. Actual expiry and re-consent mutation are proved by the
API/PostgreSQL suites. The implementation is published as commit `c96b6c2` in
draft PR [#5](https://github.com/Khang206206/gamelens-ai/pull/5).

## 22. Stage 5 Handoff

Stage 4 leaves the collaborative and hybrid-ranking stage with:

- Explicit-consent anonymous identities with documented credential, expiry,
  retention, revocation, and deletion semantics.
- Canonical saved positive preferences keyed by stable catalog identity.
- Current like/dislike, played, wishlist, and rating state plus preserved
  occurrence/supersession history and exact conflict/no-op behavior.
- Deterministic hard dislike exclusion, positive-feedback affinity, played
  adjustment, and wishlist-neutral policy with independent evidence.
- Stable base model/artifact/data identity and a separate personalization-policy
  identity.
- Bounded recommendation-generation events with exact model/data/policy,
  effective-context fingerprint, and compact result identity.
- A verified distinction between committed recommendation generation and
  actual user feedback.
- User-scoped deletion and time-based retention that downstream datasets must
  honor.
- PostgreSQL concurrency/isolation/cascade evidence and disposable full-stack
  fixtures.
- An accessible persisted-feedback product flow and generated client contract.
- Complete Stage 1–4 regression commands and recorded known limitations.

Stage 5 may then:

- Define a reproducible, consent/retention-aware interaction snapshot for
  collaborative experiments.
- Select explicit positive/negative labels from active and/or temporal feedback
  without treating recommendation events as labels.
- Establish minimum user/item interaction thresholds and cold-start behavior.
- Implement and independently test a collaborative baseline.
- Compare collaborative and content baselines before combining them.
- Add a versioned hybrid policy whose content, collaborative, popularity, and
  feedback components remain separately observable.

Stage 5 must first audit whether available interactions are sufficient and
representative. Project-authored seed data, developer-generated feedback, and
small local sessions are functional fixtures, not evidence of real-user
quality. Deleted/expired user data may not be resurrected from events, caches,
artifacts, fixtures, or derived datasets. Formal comparative evaluation and
quality claims remain Stage 6 work.

## 23. Verified Completion Record

Stage 4 completed on 2026-08-13. Planning used `docs/stage-4-plan`; implementation
used `feat/stage-4-feedback-persistence`. The verified implementation commit is
`c96b6c2`, published in draft PR
[#5](https://github.com/Khang206206/gamelens-ai/pull/5).

- Runtime/locks: Python 3.12.13, API 0.3.0, PostgreSQL 16.14, Node.js 24.18.0,
  npm 11.16.0, Next.js 16.2.12, React 19.2.8, TypeScript 5.9.3, Playwright
  1.62.0, Git 2.47.0.windows.2, gh 2.96.0, and exact committed Python/npm
  locks. `pip check`, runtime imports, and both
  production/full npm audits pass; npm reports zero vulnerabilities. Reviewed
  dependency licenses remain MIT, Apache-2.0, MPL-2.0, and BSD-family as
  documented in the repository.
- Image: no-cache `gamelens-ai-api:stage4-test` digest prefix `11b2f940731e`
  passes runtime checks and the 49 PostgreSQL tests. Docker Scout reports 0
  critical, 0 high, 3 medium, 27 low, and 2 unspecified findings across 193
  packages; the only-fixed scan reports no actionable fixed advisory. Final
  E2E API/web digest prefixes are `a7c94365` and `aadf9c3d`.
- Schema: Alembic head is `0005_stage_4_event_contract` after revisions `0003`
  and `0004`. Empty/populated upgrade and populated downgrade/re-upgrade pass;
  legacy identities are preserved but revoked without fabricated consent.
  Current-state partial indexes, temporal supersession, constraints, cascades,
  event correlation, concurrency, retention, and revocation pass.
- Identity/privacy: the host-only `gamelens_session` cookie is HttpOnly,
  `SameSite=Lax`, scoped to `/api/v1`, 180 days, and Secure in production.
  HMAC-SHA-256 lookup and CSRF domains are distinct; consent is `stage-4-v1`.
  Exact Origin/CORS and CSRF checks, no implicit identity, stateless-with-cookie
  no-write, expiry/revocation, deletion, and secure-profile validation pass.
  Final scans found no raw token/CSRF, credential, personal data, database dump,
  trace, coverage output, browser artifact, local path, or unrelated file in
  committed output. Protected traces stay disabled by default.
- Data/policy: bounded replace-all preferences and temporal reaction, played,
  wishlist, and half-step rating state pass reference, no-op, concurrency,
  isolation, stale-catalog, and cascade tests. Policy
  `gamelens-feedback-adjustment/1.0.0` preserves no-feedback Stage 3 order,
  excludes dislikes/sources, blends base/affinity 90/10, applies played 0.5,
  leaves wishlist neutral, and exposes deterministic fixed-point evidence.
  Base model `gamelens-content-tfidf/1.0.0`, artifact schema 1, and
  compatibility `stage-3-v1` remain unchanged.
- Events/operations: `stage-4-v1` events record one bounded committed
  generation with model/data/policy identity and correlation ID; they are not
  impressions or labels. Retention preview is read-only and completed in
  6.305 ms on the disposable stack; purge and revocation require explicit
  fingerprinted confirmation and bounded batches. No scheduler or startup
  purge exists.
- Automated gates: 52 ML tests pass with 83% diagnostic coverage; 184 API
  tests pass with 89%; 49 PostgreSQL tests pass in 4.53 seconds; 76 web tests
  pass with 67.15% statements and 71.4% lines. Ruff checks 112 files. Strict
  TypeScript, ESLint, Prettier, production build, generated OpenAPI drift, and
  all three Compose definitions pass.
- Browser: 38/38 pass in 1.3 minutes without retry with two workers: 28
  Chromium, 5 Firefox, and 5 WebKit. Coverage includes opt-out/opt-in,
  persistence, isolation, reload, feedback, dislike/played evidence,
  invalid-cookie recovery, clear-data, responsive and stateless/active axe
  paths. WebKit active axe creates a real session with `201`; real Origin and
  CSRF rejections return `403`. The re-consent UI case is hybrid; real expiry
  and re-consent mutation are API/PostgreSQL evidence.
- Full-stack lifecycle: tmpfs PostgreSQL migrates/seeds, the artifact builds,
  API/web become ready, browser scenarios complete, and teardown removes only
  E2E containers, network, and volume. The final Compose process list is empty;
  persistent development database, artifact, and web volumes are untouched.

Known limitations: the anonymous session is possession-based and same-device,
with no account, role model, recovery, identity provider, scheduler, online
dual-key rotation, production deployment, or quality claim. The 30-game seed
is functional evidence only. Stage 5 receives consent/retention-aware feedback
semantics and bounded generation events but must audit interaction sufficiency
before collaborative or hybrid modeling; formal evaluation remains Stage 6.
