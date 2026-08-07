# GameLens AI

## Stage 3 Engineering Plan: Content Recommendation MVP

- **Document status:** Complete and verified on 2026-08-07; Sections 21–23
  record final decisions, evidence, known findings, and the Stage 4 handoff.
- **Stage 2 prerequisite:** Complete and verified on 2026-07-30.
- **Target branch:** `feat/stage-3-content-recommendation-mvp`
- **Primary outcome:** A deterministic, artifact-backed content recommender
  exposed through typed API contracts and an accessible anonymous onboarding
  and results experience.

Sections 1–20 preserve the approved forward-looking engineering plan. Sections
21–23 are the authoritative as-built decision, handoff, and completion record.

## 1. Context

Stage 1 established the FastAPI, PostgreSQL, catalog, migration, seed,
repository, service, error, and recommendation-protocol foundations. Its
recommendation service deliberately reports `not_configured` and exposes no
recommendation endpoint.

Stage 2 established the responsive Next.js application, generated OpenAPI
types, project-owned browser API client, accessible shared UI, catalog and
detail experiences, and an isolated full-stack browser-test workflow. Its
handoff explicitly allows recommendation controls only after a real backend
contract and validated model exist.

The completed prerequisites are recorded in the
[Stage 1 engineering plan](stage-1-backend-database-plan.md) and
[Stage 2 engineering plan](stage-2-frontend-foundation-plan.md). The intended
algorithm progression and evidence contract are described in
[Recommendation design](recommendation-design.md).

Stage 3 activates the first project-owned recommendation vertical slice:

```text
catalog snapshot
    -> offline deterministic preprocessing and model build
    -> validated versioned artifact
    -> API-owned online inference
    -> typed recommendation response
    -> anonymous onboarding and explained results
```

The current development catalog contains 30 project-authored fictional games,
10 genres, 20 tags, and 6 platforms. Every seed game has a title, description,
developer, publisher, rating signals, and taxonomy references suitable for a
small deterministic content-model fixture. That catalog is sufficient to
prove reproducibility, integration, and explanation behavior. It is not
sufficient to support claims about real-world recommendation quality.

The Stage 3 user remains anonymous. Selected games and positive taxonomy or
platform preferences are supplied with the current recommendation request.
Stage 3 does not create a user, persist preferences, record interactions, log
recommendation events, or adjust future results from feedback. Those stateful
capabilities remain Stage 4 work even though the Stage 1 schema already
contains future-facing tables.

The resulting slice should demonstrate:

- Reproducible offline preprocessing and artifact creation.
- A popularity baseline and TF-IDF content model that can be tested
  independently.
- Stable artifact identity, integrity, compatibility, and catalog-fingerprint
  checks.
- A replaceable API service that loads a validated artifact once rather than
  fitting a model inside request handling.
- Bounded, typed request context and deterministic top-K ranking.
- Component scores and structured evidence that explain the ranked order.
- Deterministic user-facing explanations generated without an LLM.
- Accessible onboarding and results that call the real API and never rank in
  the browser.
- Explicit missing, corrupt, incompatible, stale, insufficient-context,
  empty-candidate, network, and unexpected-error states.
- Host and Docker workflows that keep artifact creation explicit and do not
  modify persistent development data during tests.
- Complete Stage 1 and Stage 2 regression protection.

## 2. Stage Objectives

Stage 3 will deliver:

1. A Python 3.12 machine-learning project under `ml` with exact direct
   dependency pins, a reproducible container dependency lock, linting, tests,
   and documented package boundaries.
2. A read-only catalog-snapshot boundary that produces a canonical,
   deterministically ordered feature dataset keyed by stable game slug.
3. Validation for missing or malformed feature fields, duplicate slugs,
   unresolved taxonomy references, empty vocabulary, and unsupported catalog
   shapes before artifact promotion.
4. A documented and versioned popularity baseline that accounts for rating
   quality, rating volume, and the existing synthetic popularity signal.
5. Deterministic text preprocessing over title, genres, tags, developer,
   publisher, and description.
6. A sparse TF-IDF feature space and cosine-similarity content ranker.
7. A user vector derived from selected example games and positive genre/tag
   preferences, with preferred platforms retained as a separate observable
   score component.
8. A versioned ranking configuration whose component normalization, weights,
   score precision, candidate policy, and tie-break rules are explicit.
9. A generated artifact bundle containing the feature matrix, vectorizer
   state, stable row mapping, manifest, file checksums, data fingerprint,
   feature and ranking configuration, creation time, and code/library
   compatibility metadata.
10. An artifact validator that rejects missing, malformed, integrity-failing,
    incompatible, or out-of-policy bundles before allocating numerical model
    state, plus request/status orchestration that rejects catalog-stale
    artifacts before ranking.
11. A replaceable, immutable online recommendation service injected through
    the existing API boundary and loaded once per application lifecycle.
12. An extended model-status contract that distinguishes an unconfigured model
    from a configured-but-unavailable model and reports `ready` only after
    artifact and current-catalog validation succeeds.
13. A typed `POST /api/v1/recommendations` contract with bounded selections,
    bounded top-K, controlled domain validation, standard error envelopes, and
    no database writes.
14. Recommendation responses containing rank, final ranking score, model
    identity, observable component score details, matching genres/tags,
    preferred-platform evidence, similar selected games, popularity evidence,
    and deterministic explanation text.
15. Generated TypeScript contracts and an extension of the existing
    project-owned browser API client for JSON `POST` requests.
16. A `/recommendations` experience with accessible, responsive, anonymous
    onboarding, deliberate validation, submission, results, restart, and
    recovery behavior.
17. ML, artifact, ranking, API, database-integration, frontend, browser,
    accessibility, responsive, OpenAPI-drift, Docker, and earlier-stage
    regression gates.
18. Explicit host and Docker commands for building, inspecting, validating,
    and testing artifacts without training during ordinary API or web startup.
19. Updated architecture, recommendation, ML, roadmap, root, and application
    documentation that distinguishes planned, implemented, and deferred
    behavior.

## 3. Non-Goals

The following work is intentionally excluded from Stage 3:

- Creating persistent anonymous users from onboarding.
- Writing `user_preferences`, `interactions`, or
  `recommendation_events`.
- Like, dislike, played, wishlist, rating, or other feedback endpoints.
- Feedback-based score adjustment, disliked-game exclusion, or played-game
  demotion; these begin in Stage 4.
- Preference history, cross-device state, long-term browser memory, accounts,
  authentication, or authorization.
- Collaborative filtering or a collaborative/content hybrid; these remain
  Stage 5 work.
- Precision@K, Recall@K, Hit Rate@K, NDCG@K, coverage, novelty, diversity, or
  comparative recommendation-quality claims; formal evaluation remains
  Stage 6 work.
- Production deployment, CI/CD, monitoring, registry promotion, scheduled
  retraining, or production image hardening; these remain Stage 7 work.
- Semantic embeddings, natural-language preference prompts, diversity
  reranking, LLM-authored explanations, or other selected advanced
  capabilities; these remain Stage 8 candidates.
- Fitting, rebuilding, downloading, or mutating a model inside an API request.
- Silently building an artifact during ordinary API or web startup.
- Browser-side ranking, browser-side score recomputation, or a fabricated
  popularity fallback when the API model is unavailable.
- External game metadata services, remote datasets, cover-image imports, or
  undocumented network access.
- A remote artifact registry or runtime artifact download.
- Arbitrary user-supplied floating-point weights. Stage 3 accepts positive
  selections and applies versioned model-owned weights.
- Approximate-nearest-neighbor infrastructure, distributed training, a model
  microservice, GPUs, queues, or large-catalog optimization without a measured
  need.
- A database migration unless Phase 0 finds a genuine blocker that cannot be
  resolved through the existing catalog schema and a read-only snapshot.
- Treating the 30-game synthetic catalog as market evidence or a
  recommendation-quality benchmark.

## 4. Engineering Principles

### 4.1 Contract-First Recommendation Boundary

The request, response, model-status, artifact, and explanation shapes must be
agreed before integration code is written. Python schemas and the live OpenAPI
document remain the external source of truth; frontend types are generated
rather than copied by hand.

### 4.2 Offline Build, Online Inference

Catalog extraction, feature fitting, matrix generation, and artifact writing
run only through an explicit offline command. Request handling loads immutable
validated state and performs bounded inference. Training never runs in a route,
startup hook, browser, or database migration.

### 4.3 Determinism and Reproducibility

Canonical input ordering, normalization, feature configuration, random seeds
where applicable, floating-point policy, score serialization, and tie-breaking
must be explicit. The same input snapshot, configuration, dependency graph,
and clock fixture must produce the same semantic artifact identity and ordered
rankings. Raw floating-point values are quantized into a canonical fixed-scale
integer ranking key before ordering so last-bit runtime differences do not
silently redefine near-ties.

### 4.4 Honest Model Readiness

`ready` means a configured artifact passed manifest, checksum, compatibility,
and current-catalog validation. An absent configuration, missing bundle,
corrupt file, incompatible schema, or stale catalog must be reported
distinctly. Catalog endpoints should remain available when recommendation
capability is unavailable; recommendation requests must fail clearly rather
than invent results.

### 4.5 Artifact Integrity and Compatibility

The artifact is a versioned contract, not an incidental pickle. Its manifest
must identify every content file, checksum, schema version, data fingerprint,
feature and ranking configuration, stable item mapping, compatible code and
library versions, and creation metadata. Stage 3 will use transparent,
non-executable JSON and NumPy/SciPy numeric formats rather than
pickle-compatible deserialization. The configured operator-controlled local
artifact root is the provenance trust boundary.

### 4.6 Baseline-First Ranking

The popularity baseline must work and be tested before TF-IDF results are
integrated. Every final component is independently observable and normalized
before combination. Adding a content component does not erase the baseline or
make it untestable.

### 4.7 Structured Evidence Before Prose

Ranking emits typed evidence first: component scores, matching taxonomy,
preferred platforms, similar selected games, and popularity contribution.
User-facing prose is a deterministic presentation of that evidence. It may
not introduce a reason that did not affect or support the result.

### 4.8 Stateless Stage 3 User Context

Onboarding selections belong to the current UI flow and recommendation
request. They do not create server-side identity or durable history. Copy,
tests, storage choices, and network behavior must not imply saved
personalization.

### 4.9 Sparse and Bounded Computation

Feature matrices remain sparse. Selection counts, string lengths, top-K, and
request payloads are bounded at the API boundary. Candidate work is bounded by
validated hard limits on artifact items, vocabulary, matrix dimensions,
non-zero entries, member sizes, and evidence. Dense conversion of the full
matrix, per-request fitting, and unbounded artifacts or payloads are
prohibited.

### 4.10 Stable Identity and Candidate Safety

Artifacts use stable game slugs rather than environment-specific integer
primary keys. The API resolves request IDs through PostgreSQL, aligns current
records with artifact slugs, excludes selected examples, and rejects unknown
or incompatible context deliberately. Stable slug ordering resolves final
ties.

### 4.11 Minimal Dependency Surface

NumPy, SciPy, scikit-learn, and an artifact serialization dependency may be
introduced only after the complete host/container compatibility and license
review. pandas is optional and must have a concrete need. No notebook,
experiment-tracking, serving, or orchestration framework is added merely
because the work involves ML.

### 4.12 Safe Local Operations

Artifact commands may write only beneath an explicit artifact output
directory. Integration and browser tests use disposable database and artifact
locations. They must not reset the persistent development database, delete
development model bundles, or load model files selected by request input.

### 4.13 Incremental Delivery and Regression Safety

Each phase must leave the repository importable, testable, and truthful. Model
code precedes API activation; API contracts precede UI activation. Stage 1
and Stage 2 behavior is rerun throughout the stage, not only at the end.

## 5. Proposed Technical Decisions

### 5.1 Runtime and Dependency Boundary

The offline and online recommendation paths will use Python 3.12, matching the
verified API runtime. The planned numerical stack is:

- NumPy for deterministic numeric arrays.
- SciPy for sparse matrix storage and operations.
- scikit-learn for TF-IDF fitting and cosine-compatible normalization.
- pytest and Ruff for ML tests, linting, and formatting.

The first artifact will serialize vectorizer configuration, vocabulary,
inverse-document-frequency values, sparse features, and catalog evidence
through checksum-covered JSON, NPY, and NPZ members that do not execute Python
objects while loading. Pickle-compatible joblib model loading is outside the
Stage 3 trust model.

Exact versions will be selected and pinned only after Phase 0 verifies:

- Host Windows/Python 3.12 installation and imports.
- Linux/Python 3.12 container installation and imports.
- Transparent JSON/NPY/NPZ artifact write/read round trips.
- Repeated ranking equivalence.
- Compatibility with the existing API dependency graph.
- License and vulnerability review.

The `ml` project will own preprocessing, feature construction, artifact
contracts, offline build logic, and pure ranking primitives. The API will own
PostgreSQL snapshot orchestration, HTTP validation, lifecycle injection, and
online use-case behavior. Shared Python packaging must be explicit so the
offline builder and API use the same preprocessing, artifact, and scoring
implementation rather than drifting copies.

The browser retains the verified Stage 2 dependency stack unless a concrete
accessible onboarding need justifies a small reviewed addition. Native
checkboxes, fieldsets, buttons, and existing project-owned primitives are the
default.

### 5.2 Canonical Catalog Snapshot and Feature Input

The offline builder will read the current PostgreSQL catalog through a
read-only snapshot adapter after migrations and deterministic seed have run.
It will not fit directly from ORM objects or depend on route response
serialization.

Each canonical snapshot row will contain:

- Stable game slug. The adapter may retain the current database ID for
  request-time resolution or safe diagnostics, but it does not enter the ML
  snapshot, artifact identity, or artifact row mapping.
- Title.
- Genres and tags as sorted stable slugs plus display names where required for
  evidence.
- Developer and publisher.
- Description.
- Platforms as a separate sorted taxonomy list.
- Average rating, rating count, and popularity score.

Canonicalization will:

- Normalize Unicode and line endings using one documented policy.
- Trim and collapse insignificant whitespace.
- Preserve meaningful text while applying one documented case policy.
- Sort records by stable slug.
- Sort and deduplicate taxonomy values by stable slug.
- Serialize decimals and dates consistently where included.
- Reject duplicate game slugs and unresolved taxonomy references.
- Reject missing content fields required by the Stage 3 feature contract.
- Calculate a SHA-256 fingerprint over the canonical semantic snapshot rather
  than environment-specific database IDs or JSON formatting.

The snapshot policy follows the existing Stage 1 schema instead of requiring
every nullable field to be populated. Stable slug, title, description,
rating count, and popularity remain required under their existing contracts.
A null or blank developer/publisher contributes no studio token; an empty
genre, tag, or platform collection contributes no token for that family; and a
null average rating follows the versioned popularity missing-value policy.
Such a valid catalog row is rejected only if the complete documented content
representation is empty or invalid, not merely because one optional field is
absent.

The current seed is the deterministic acceptance fixture, but the snapshot
contract must not hard-code a count of 30 into production ranking logic.

### 5.3 Popularity Baseline

The first independently testable baseline will combine:

- A Bayesian or IMDb-style weighted rating using average rating, rating count,
  a documented catalog mean, and a documented minimum-vote prior.
- A normalized form of the existing non-negative popularity signal.

The exact prior definition, missing-value policy, normalization method,
combination weights, constant-range behavior, and output precision must be
selected in Phase 0, stored in the ranking configuration, and recorded in
Section 21. The formula must prevent a title with one perfect rating from
automatically dominating a well-supported title.

The popularity score will be bounded and independently rankable. It may
contribute a small documented prior to the content result. It must not become
a silent runtime fallback when the configured content artifact is missing or
invalid.

### 5.4 TF-IDF Feature Space

The content representation will use:

- Title.
- Genre slugs or names.
- Tag slugs or names.
- Developer.
- Publisher.
- Description.

Categorical fields will use explicit field-aware tokens so a taxonomy value
cannot silently collide with unrelated prose. Title, taxonomy, studio, and
description contributions may use documented repetition or transformer
weights, but exact choices must be versioned rather than scattered through
code.

The initial vectorizer will use a deterministic word-level TF-IDF
configuration suitable for the small English synthetic corpus. Analyzer,
token pattern, n-gram range, case normalization, accent policy, stop-word
policy, document-frequency bounds, sublinear term frequency, dtype, and vector
normalization must all appear in artifact metadata.

The fitted vocabulary, inverse-document-frequency vector, and complete
vectorizer configuration will be stored transparently and reconstructed
without loading an executable Python object.

The full game matrix remains a SciPy sparse matrix. An empty vocabulary,
non-finite value, zero-norm catalog row, or matrix/row-map mismatch is a
controlled build failure.

### 5.5 Request Context and User-Vector Construction

The initial request context will contain:

- `selected_game_ids`: zero through five distinct IDs from 1 through
  2,147,483,647, matching the existing database-integer contract.
- `preferred_genres`: zero through five distinct taxonomy slugs.
- `preferred_tags`: zero through ten distinct taxonomy slugs.
- `preferred_platforms`: zero through six distinct taxonomy slugs.
- `top_k`: an integer from 1 through 20, default 10.

Every taxonomy slug will contain 1 through 100 characters and match the
existing lowercase alphanumeric, single-hyphen-separated slug pattern. The
collection caps and scalar limits jointly bound the JSON body before any
database query.

The recommendation request schema will reject unknown fields instead of
silently ignoring them.

At least one selected game, preferred genre, or preferred tag is required.
Platform-only context is insufficient because platform remains a secondary
signal rather than the content query itself.

Duplicate values and unknown game or taxonomy references will return a
controlled validation error rather than being silently ignored. The frontend
will prevent them during normal use, but the API owns final enforcement.

The user content vector will combine:

- The normalized centroid of selected-game vectors.
- A vectorized synthetic preference document built from the same field-aware
  genre and tag tokens as the artifact.

The relative selected-game and taxonomy weights, normalization, and zero-vector
policy must be versioned. A valid request that cannot produce a meaningful
content vector returns an actionable insufficient-context error rather than a
popularity-only result.

Preferred platforms do not enter the TF-IDF document. They produce their own
bounded platform-match component so the response can explain their effect.
The client cannot send arbitrary weights.

### 5.6 Candidate Filtering and Deterministic Ranking

Before scoring, the service will:

- Resolve selected database IDs to stable artifact slugs.
- Reject unknown selected games.
- Exclude selected example games from recommendation candidates.
- Reject the model as stale when the validated current-catalog fingerprint
  does not match the configured artifact.
- Reject the artifact before readiness when a candidate feature is non-finite
  or structurally invalid.

Stage 3 has no persisted dislike or played signal. Feedback-derived exclusion
and demotion remain Stage 4 work.

Each candidate will expose normalized raw components for:

- Content similarity.
- Explicit genre/tag preference overlap where it is not already fully
  represented by the content vector.
- Preferred-platform match.
- Popularity prior.

The final ranking score is a versioned weighted sum of bounded components.
Weight units must be non-negative and sum exactly to the configured fixed
scale, whose decimal representation is one. Exact components and weights will
be confirmed in Phase 0 so taxonomy is not accidentally counted twice without
a documented reason.

Raw floating-point components are not ranking keys. Each component is clamped
and converted through one versioned rounding rule into fixed-scale integer
score units. Model weights are stored as fixed-scale integer units, weighted
contributions are calculated with deterministic integer rounding, and the
final ranking key is the exact integer sum of contribution units. The scale
and rounding mode will be selected in Phase 0 and tested on adversarial
near-ties in every supported runtime.

Candidates whose quantized content-similarity units are zero are not promoted
by platform or popularity alone. If no positively content-supported candidate
remains after selected-game exclusion, the API returns a successful empty
result with a stable `no_content_support` response reason and a recovery
prompt.

Ordering is:

1. Final contribution units descending.
2. Quantized content-similarity units descending.
3. Quantized popularity-baseline units descending.
4. Stable game slug ascending.

The service returns at most `top_k` candidates and may return fewer when the
compatible candidate set is smaller. A request with no remaining candidates
returns a successful empty result with an explicit response state; it is not a
server error.

### 5.7 Component Scores and Structured Explanations

Each recommendation item will include:

- One-based rank.
- Final ranking score, explicitly not a probability or calibrated match
  percentage.
- The existing `GameSummary` contract.
- A score breakdown for each active component with raw normalized score,
  configured weight, and weighted contribution.
- Matching genre and tag evidence.
- Matching preferred platforms.
- Similar selected games and their content similarity where applicable.
- Popularity evidence sufficient to explain its contribution.
- A deterministic explanation summary and ordered reason list derived only
  from the structured evidence.

The API serializes raw score, weight, contribution, and final score as decimal
values derived from their canonical integer units. Serialized contribution
units must sum exactly to serialized final-score units; clients can therefore
reconstruct the wire result without access to unrounded floats. Ordering uses
the same integer units and never display-formatted floats.

Explanation templates will:

- Prefer the strongest positive evidence.
- Use stable priority and tie rules.
- Avoid claiming causality, quality, certainty, or popularity beyond the
  supplied signals.
- Avoid naming a preference that did not contribute.
- Provide a truthful generic explanation when only weak evidence exists.
- Remain useful without JavaScript-only visual encodings.

An LLM is neither required nor called.

### 5.8 Artifact Manifest and Lifecycle

A generated artifact bundle will contain at least:

```text
<artifact-directory>/
|-- manifest.json
|-- vectorizer-config.json
|-- vocabulary.json
|-- inverse-document-frequency.npy
|-- feature-matrix.npz
`-- catalog-items.json
```

The exact filenames may change after the Phase 0 serialization smoke test. The
manifest must contain:

- Artifact-schema version.
- Model name and semantic model version.
- Build timestamp in UTC.
- Canonical data fingerprint and item count.
- Stable slug row mapping or a checksum-covered reference to it.
- Full preprocessing and vectorizer configuration.
- Vocabulary size, sparse matrix shape and non-zero count, and numeric dtype.
- Popularity and ranking configuration.
- Score serialization and tie-break policy.
- Compatible Python, NumPy, SciPy, scikit-learn, and application schema/code
  versions.
- Relative content filenames, sizes, and SHA-256 checksums.
- Optional recorded random seed even when the current algorithm has no random
  operation.

Phase 0 will define hard upper limits for artifact item count, vocabulary
size, matrix dimensions and non-zero entries, member count, individual member
size, total bundle size, and evidence-string lengths. Manifest values outside
those limits are rejected before numeric allocation where the selected format
allows it, and loaded shapes are revalidated afterward. Online candidate work
is therefore bounded by a validated artifact, not merely by response
`top_k`.

The builder writes into a temporary sibling directory, validates the complete
bundle, and promotes it atomically only after success. It must not overwrite a
different existing semantic version without an explicit safe policy.

Generated development artifacts remain ignored by Git. A deliberately small
fixture may be committed under tests only when it is required for deterministic
loader or API tests and its provenance, size, and regeneration command are
documented.

`MODEL_ARTIFACT_PATH` is the planned backend-only configuration. It must never
enter the browser bundle. The API loads only this configured local bundle,
never a request-selected path or remote URL. JSON parsing and numeric array
loading must disable object dtypes and pickle-compatible behavior.

Checksums in the manifest detect accidental corruption but do not authenticate
the producer because an actor who can replace the whole bundle can also replace
its manifest. Stage 3 therefore assumes the configured artifact root is
operator-controlled, validates that every member remains within it, mounts it
read-only at runtime, and uses only non-executable formats. External signing or
registry provenance is deferred to the Stage 7 production trust design.

The API loads and validates one immutable artifact during its application
lifecycle. It does not watch, hot-swap, or mutate the bundle. Activating a new
artifact requires a deliberate process restart.

### 5.9 Model Status and Failure Semantics

The model-status contract will support:

- `not_configured`: no artifact path was configured.
- `unavailable`: a path was configured but the bundle is missing, corrupt,
  incompatible, outside the artifact path policy, or stale relative to the
  current catalog.
- `ready`: artifact integrity, compatibility, current-catalog alignment, and
  model construction all succeeded.

When ready, status exposes safe model name/version, artifact schema,
data-fingerprint identifier, feature families, and recommendation/explanation
capabilities. When unavailable, it exposes a stable safe reason code without
leaking filesystem paths, stack traces, or dependency internals.

Recommendation unavailability does not make the existing catalog health check
lie or disable Stage 1 and Stage 2 routes. A recommendation request made while
the model is not ready returns the standard error envelope with HTTP 503 and a
stable error code. There is no hidden popularity-only response.

Application startup establishes only the immutable artifact's intrinsic state:
unconfigured, intrinsically unavailable, or loaded. For a loaded artifact,
both `GET /api/v1/models/status` and
`POST /api/v1/recommendations` open one read-only `REPEATABLE READ`
transaction, build one canonical current-catalog snapshot, and compare its
fingerprint before returning `ready` or ranking. The recommendation request
uses that same snapshot to resolve IDs and serialize game summaries. A
database failure remains a database/readiness failure rather than being
misreported as artifact corruption. No request reloads or mutates the
artifact.

Model construction will be injected through an application factory or
dedicated dependency so tests can supply ready, unconfigured, corrupt, and
incompatible services without patching global state.

### 5.10 Recommendation API Contract

Stage 3 will add:

| Method | Path                      | Purpose                                      |
| ------ | ------------------------- | -------------------------------------------- |
| POST   | `/api/v1/recommendations` | Rank compatible games from anonymous context |

The request body follows the bounds in Section 5.5. Domain validation will
distinguish:

- Structurally invalid JSON or field bounds.
- Duplicate selections.
- Unknown game IDs.
- Unknown taxonomy slugs.
- Insufficient positive content context.
- Context that produces a zero vector.
- A model that is not configured or unavailable.

Pydantic/FastAPI validation and domain validation will use the existing
standard error envelope and stable error codes. Safe validation messages may
identify invalid request values but must not expose internal paths or model
objects.

The endpoint is read-only with respect to PostgreSQL. It obtains a consistent
catalog snapshot, invokes the API-owned recommendation use case, and serializes
typed results. It does not create a user, save request context, write an
interaction, or create a recommendation event.

The API CORS allow-method configuration must add `POST` deliberately and
retain its explicit origin allowlist. Allowed and rejected preflight behavior
will be contract-tested.

### 5.11 Web Route and State Ownership

Stage 3 will add:

| Route              | Purpose                                                 |
| ------------------ | ------------------------------------------------------- |
| `/recommendations` | Anonymous onboarding, submission, and explained results |

The route will use a focused client feature boundary and the existing
project-owned API client. A local reducer or equivalent component state owns
the current onboarding step, bounded selections, submission, and returned
results. No global store, cookie, server session, user record, `localStorage`,
or durable browser identifier is required.

The onboarding flow will:

1. Explain that selections are used for the current request and are not saved.
2. Let users select up to five known example games through a bounded catalog
   search/browse interaction.
3. Let users choose positive genres and tags through native, labeled,
   keyboard-operable controls.
4. Let users optionally choose preferred platforms as a separate signal.
5. Summarize selections before submission and provide clear removal/restart
   controls.
6. Require enough positive content context before enabling submission.

The results experience will:

- Identify the active model without exposing implementation clutter.
- Render ordered game summaries and structured reasons returned by the API.
- Label the numeric value as a ranking score, never a probability or
  percentage match.
- Allow game-detail navigation without moving ranking logic into the browser.
- Offer an explicit restart or adjust-preferences action.
- Distinguish no candidates, insufficient context, validation failure,
  model unavailable, network failure, malformed response, and unexpected
  error.
- Announce submission and result updates to assistive technology.

The landing page and navigation may expose the recommendation call to action
only after the real API and ready-artifact path pass integration tests. The
Stage 2 assertion that no recommendation button exists is baseline evidence,
not a permanent requirement.

### 5.12 Quality Tooling and Numeric Policy

The Stage 3 quality stack will include:

- Pure preprocessing, baseline, artifact, ranking, and explanation tests.
- Repeated-build and repeated-ranking determinism tests.
- Property or invariant tests where they add value without a large framework.
- Artifact corruption, checksum, schema, library, and data-drift fixtures.
- Fast API contract and failure-path tests.
- Disposable-PostgreSQL integration tests for snapshot alignment and proof of
  no writes.
- Generated OpenAPI drift checks.
- Frontend reducer, validation, client, and rendering tests.
- Real-browser onboarding-to-results flows against a real artifact and API.
- Keyboard, automated accessibility, console-error, and responsive checks.
- Stage 1 and Stage 2 regression suites.
- Host and container dependency, license, vulnerability, and artifact review.

Floating-point tests will compare raw calculations with a documented tolerance.
Ranking and wire-contract tests will compare canonical fixed-scale integer
units and their decimal serialization exactly. Near-tie fixtures must exercise
the quantization boundary on every supported runtime; ordering never relies on
platform-specific last-bit differences.

No quality metric or coverage percentage alone completes the stage. Tests must
cover meaningful success, boundary, corruption, unavailable, and recovery
paths.

## 6. Target Repository Structure

```text
ml/
|-- src/
|   `-- gamelens_recommender/
|       |-- __init__.py
|       |-- artifacts.py
|       |-- baseline.py
|       |-- features.py
|       |-- ranking.py
|       |-- schemas.py
|       `-- training.py
|-- tests/
|   |-- fixtures/
|   |-- test_artifacts.py
|   |-- test_baseline.py
|   |-- test_features.py
|   `-- test_ranking.py
|-- artifacts/                  # Generated and ignored
|-- pyproject.toml
|-- requirements.lock
`-- README.md

apps/api/
|-- app/
|   |-- api/
|   |   `-- v1/
|   |       `-- routes/
|   |           `-- recommendations.py
|   |-- commands/
|   |   `-- build_recommendation_artifact.py
|   |-- repositories/
|   |   `-- recommendation_catalog.py
|   |-- schemas/
|   |   |-- model_status.py
|   |   `-- recommendations.py
|   `-- services/
|       `-- recommendation/
|           |-- lifecycle.py       # API adapter over ML-owned artifact code
|           |-- base.py
|           |-- content.py
|           `-- not_configured.py
`-- tests/
    |-- integration/
    `-- unit/

apps/web/
|-- src/
|   |-- app/
|   |   `-- recommendations/
|   |       |-- error.tsx
|   |       |-- loading.tsx
|   |       `-- page.tsx
|   |-- features/
|   |   `-- recommendations/
|   |       |-- onboarding.tsx
|   |       |-- recommendation-flow.tsx
|   |       `-- recommendation-results.tsx
|   `-- lib/
|       `-- api/
|           |-- client.ts
|           `-- generated.ts
`-- e2e/
    `-- recommendations.spec.ts

infra/
`-- docker-compose.e2e.yml

docs/
`-- stage-3-content-recommendation-mvp-plan.md
```

Exact module and component filenames may evolve during implementation. The
required boundaries are canonical snapshot extraction, reusable ML logic,
versioned artifact validation, API lifecycle and contracts, browser API
access, onboarding/results presentation, and isolated tests.

The existing ignore policy for `ml/artifacts`, generated reports, processed
data, caches, and local environments remains in force. Any test fixture
exception must be narrow and documented.

## 7. Implementation Phase 0: Preflight, Contract, and Compatibility Baseline

### Objective

Confirm the Stage 2 handoff, current repository state, dataset suitability,
external contracts, and compatible numerical toolchain before adding model or
product code.

### Work

1. Confirm the worktree is understood and create the target branch from the
   latest verified `main`.
2. Re-read the Stage 1 and Stage 2 completion records and preserve unrelated
   user changes.
3. Run the complete existing API fast suite, PostgreSQL integration suite,
   Ruff checks, frontend clean install, type check, lint, format check, fast
   tests, production build, OpenAPI drift check, browser suite, accessibility
   checks, and Compose validation.
4. Start the migrated and seeded stack and verify the current catalog,
   taxonomy, detail, health, OpenAPI, and `not_configured` model-status
   contracts.
5. Audit the current seed for:
   - Required content and rating fields.
   - Valid nullable developer, publisher, rating, and empty-taxonomy cases.
   - Unique stable slugs.
   - Deterministic taxonomy references.
   - Expected field types and finite numeric values.
   - Enough vocabulary and taxonomy variation for functional tests.
6. Record the baseline catalog count and taxonomy counts as fixture evidence,
   not production invariants.
7. Write a reviewed request/response example covering:
   - Bounds and duplicate policy.
   - Unknown-reference behavior.
   - Insufficient context.
   - Top-K behavior.
   - Score-component structure.
   - Explanation evidence.
   - Empty-candidate response.
8. Write the model-status transition matrix for unconfigured, missing,
   corrupt, incompatible, stale, and ready artifacts.
9. Write the canonical snapshot, transparent artifact member, resource-limit,
   operator-trust, and manifest specifications before implementation.
10. Define the popularity formula candidates, TF-IDF configuration candidates,
    user-vector formula, component normalization, fixed-point score scale,
    deterministic rounding, weighting, serialized precision, positive-content
    policy, and tie rules.
11. Smoke-test candidate NumPy, SciPy, scikit-learn, pytest, and Ruff versions
    together on host Python 3.12 and Linux Python 3.12.
12. Build and reload a tiny sparse artifact in both environments.
13. Compare two repeated fits and ranking runs, including adversarial
    quantization-boundary and near-tie fixtures, across both environments.
14. Review direct and transitive dependency licenses and known
    vulnerabilities.
15. Confirm the shared-package/install strategy works for:
    - Direct host ML development.
    - Direct host API development.
    - API container builds.
    - Quality containers.
    - Isolated E2E model builds.
16. Confirm no database migration is needed. If a blocker exists, document
    the reason and obtain explicit scope approval before changing the schema.
17. Confirm the read-only `REPEATABLE READ` snapshot transaction and
    concurrent-catalog-mutation policy with PostgreSQL.
18. Define the `/recommendations` route state matrix, focus transitions,
    validation behavior, responsive viewports, and browser acceptance paths.
19. Record the proposed decisions in a reviewable Phase 0 note before feature
    implementation.

### Verification

- The existing Stage 1 and Stage 2 gates pass before Stage 3 changes.
- The running model status is still truthfully `not_configured`.
- The live OpenAPI document contains no recommendation endpoint yet.
- The seed audit accounts for all current games and taxonomy values without
  silently repairing input.
- The request, response, status, artifact, scoring, and route-state matrices
  contain no unresolved ownership ambiguity.
- Candidate ML dependencies import and round-trip the transparent sparse
  artifact on host and in the intended container.
- Repeated fixture ranking is stable under the proposed numeric policy.
- The dependency, artifact resource, and operator-trust review has a documented
  result.
- A concurrent catalog mutation cannot produce a mixed snapshot.
- PostgreSQL persistence is not required for Stage 3 onboarding or results.

### Exit Criteria

- Stage 2 is a clean, reproducible baseline.
- External and artifact contracts are reviewable before implementation.
- One compatible pinned-toolchain candidate is selected.
- Scoring and explanation inputs are explicit enough to implement without
  inventing behavior inside routes or components.
- No recommendation control or `ready` status has been exposed prematurely.

## 8. Implementation Phase 1: ML Workspace and Reproducibility Skeleton

### Objective

Create an installable, pinned, testable ML boundary without implementing
ranking behavior prematurely.

### Work

1. Add `ml/pyproject.toml` with Python 3.12 compatibility, project metadata,
   exact direct dependency pins, package discovery, pytest, coverage, and Ruff
   configuration.
2. Generate and commit the complete intended Linux/Python 3.12 dependency
   lock after the Phase 0 compatibility smoke test.
3. Create the `gamelens_recommender` package and test directories.
4. Define immutable internal schemas or dataclasses for:
   - Canonical catalog items.
   - Snapshot identity.
   - Feature and ranking configuration.
   - Artifact manifest.
   - User context.
   - Component scores.
   - Structured evidence.
   - Ranked results.
5. Define package dependency direction so pure ML modules do not import
   FastAPI routes, Pydantic HTTP schemas, SQLAlchemy models, environment
   settings, or frontend code.
6. Establish one supported shared-package installation path for the offline
   builder and API runtime.
7. Add a minimal CLI or module entrypoint boundary that can report help without
   reading the database, fitting a model, or writing an artifact.
8. Add import, schema-validation, configuration, and package-boundary tests.
9. Extend repository ignore rules only if the existing artifact, cache, and
   report patterns do not cover the actual generated paths.
10. Update `ml/README.md` with implemented installation and quality commands
    only after they run successfully.

### Verification

- A clean host environment installs the ML project from declared metadata.
- The locked Linux container environment installs without floating
  dependencies.
- Importing the package has no database, network, filesystem-write, or model
  build side effect.
- The package help/import smoke test works on host and container Python 3.12.
- pytest and Ruff can run against `ml/src` and `ml/tests`.
- The API can import the shared package through the selected supported
  installation path.
- Generated caches, local virtual environments, and artifact output remain
  ignored.

### Exit Criteria

- The ML workspace is reproducible and independently testable.
- Dependency ownership and cross-project import direction are explicit.
- No ranking, artifact, or HTTP behavior is represented as complete yet.

## 9. Implementation Phase 2: Canonical Snapshot and Artifact Contract

### Objective

Create a deterministic read-only feature snapshot and a validated,
checksum-covered artifact lifecycle before fitting the real model.

### Work

1. Add an API-side read-only repository or adapter that loads all model feature
   fields and taxonomies in one explicit PostgreSQL `REPEATABLE READ, READ
ONLY` transaction.
2. Convert persistence records into ML-owned canonical catalog schemas without
   exposing ORM objects across the boundary.
3. Sort games and taxonomy values by stable slug.
4. Implement the documented Unicode, whitespace, case, numeric, and null
   canonicalization policy.
5. Reject missing required content, duplicate slugs, duplicate taxonomy
   values, unresolved references, non-finite signals, and unsupported shapes.
6. Calculate the semantic SHA-256 data fingerprint without database IDs or
   formatting noise.
7. Define and validate artifact-schema version 1.
8. Implement manifest serialization with:
   - Model and artifact versions.
   - Data fingerprint and item count.
   - Feature, baseline, ranking, precision, and tie-break configuration.
   - Dependency and code compatibility.
   - Stable item mapping.
   - File sizes and hashes.
   - UTC build metadata.
9. Implement safe relative artifact path validation. Reject traversal,
   absolute manifest members, duplicate filenames, missing files, unexpected
   required-file types, size mismatches, and checksum mismatches.
10. Enforce the Phase 0 hard limits for bundle members, bytes, items,
    vocabulary, matrix dimensions, non-zero entries, dtypes, and evidence
    strings before allocation where possible and after numeric loading.
11. Reject object dtypes, pickle-enabled array loads, executable serializers,
    archive expansion beyond policy, and numeric shapes that disagree with the
    manifest.
12. Implement temporary-directory writing and atomic promotion constrained to
    an explicit output root.
13. Validate all transparent metadata, paths, declared limits, and checksums
    before loading numeric model members.
14. Add a small deliberately committed manifest fixture only if hand-built
    transparent fixtures cannot cover the loader contract.
15. Inject the build clock and any random seed so deterministic tests do not
    depend on wall time.
16. Normalize JSON key order and numeric archive member order, timestamps, and
    compression settings so fixed-input content hashes are byte-stable. If the
    selected NPZ writer cannot provide that guarantee, store the sparse
    components in deterministic transparent members instead.
17. Add an inspect/validate API that reports safe metadata without importing
    FastAPI or starting the server.

### Verification

- Reordering source queries does not change canonical output or fingerprint.
- Database IDs do not affect semantic fingerprint or artifact row identity.
- A meaningful feature or taxonomy change changes the fingerprint.
- Missing fields, duplicates, unresolved taxonomy, and non-finite values fail
  with actionable offline errors.
- Traversal, corrupt manifests, checksum mismatches, incompatible schema
  versions, and missing members are rejected.
- Resource-limit, dtype, pickle/object-array, archive-expansion, and shape
  violations are rejected.
- Numeric members are not loaded after an earlier path, manifest, limit, or
  integrity failure.
- Failed builds leave no partially promoted artifact.
- Repeated fixed-clock manifest and checksum-covered member generation is
  byte-stable.
- The snapshot operation performs no database write.
- Concurrent catalog changes cannot mix versions inside one canonical
  snapshot.

### Exit Criteria

- One canonical catalog contract is shared by build and runtime validation.
- Artifact identity and integrity can be checked independently of the model.
- Stable slug mapping removes database-ID coupling.
- Out-of-policy, integrity-failing, or incomplete output cannot be activated.

## 10. Implementation Phase 3: Popularity Baseline and TF-IDF Artifact

### Objective

Build the first reproducible ranking baseline and content feature artifact
from the canonical catalog.

### Work

1. Implement the reviewed Bayesian/IMDb-style weighted-rating formula.
2. Implement the reviewed popularity-signal normalization and baseline
   combination.
3. Define behavior for missing ratings, zero rating counts, constant ranges,
   small catalogs, non-finite input, and deterministic ties.
4. Produce independently inspectable popularity scores for every catalog row.
5. Implement field-aware content-document construction for title, genre, tag,
   developer, publisher, and description.
6. Keep platforms outside the text document.
7. Fit the exact versioned TF-IDF vectorizer against stable-slug-ordered
   documents.
8. Reject empty vocabulary, zero-width matrices, row-count drift, non-finite
   output, and zero-norm rows under the chosen policy.
9. Persist the sparse matrix, transparent vectorizer configuration,
   vocabulary, inverse-document-frequency values, popularity values, and
   stable catalog evidence in the artifact bundle.
10. Record complete preprocessing, vectorizer, baseline, and dependency
    configuration in the manifest.
11. Validate the newly built bundle through the same loader contract used by
    runtime code.
12. Build twice from the same fixed snapshot, configuration, and clock fixture
    and compare semantic identity, manifest, sparse contents, and baseline
    outputs.
13. Add golden fixtures that are small enough to review and recalculate by
    hand.

### Verification

- A one-vote perfect rating cannot dominate solely because of its raw rating.
- Baseline outputs are finite, bounded, independently rankable, and
  deterministically tied.
- Every required content field affects the documented feature pipeline.
- Platforms do not enter the TF-IDF vocabulary.
- The matrix stays sparse and aligns exactly with the stable slug row map.
- Two fixed-input builds produce the same fingerprint, feature vocabulary,
  numeric matrix under the documented tolerance, and popularity outputs.
- A meaningful feature-configuration change requires a new semantic model
  version or is rejected as incompatible.
- The builder performs no network access and writes only to its output root.

### Exit Criteria

- The popularity baseline is independently usable and tested.
- The content artifact is deterministic, sparse, versioned, and validated.
- No API status or UI has been activated yet.

## 11. Implementation Phase 4: Online Ranking and Structured Evidence

### Objective

Turn a validated immutable artifact and bounded anonymous context into
deterministic recommendations with traceable evidence.

### Work

1. Implement typed user-context validation independent of HTTP.
2. Resolve selected current database IDs to artifact slugs through the API
   orchestration boundary.
3. Construct and normalize the selected-game centroid.
4. Construct the field-aware genre/tag preference document and transform it
   with the fitted vectorizer.
5. Combine selected-game and taxonomy vectors using the versioned
   configuration.
6. Reject a zero or non-finite user vector with an actionable
   insufficient-context result.
7. Calculate sparse cosine similarity against compatible candidates.
8. Calculate explicit genre/tag overlap only if the reviewed scoring design
   requires it and records how double-counting is avoided.
9. Calculate preferred-platform match as a separate bounded component.
10. Add the versioned popularity prior.
11. Exclude selected example games before top-K selection.
12. Quantize raw component scores into canonical fixed-scale integer units.
13. Reject candidates with zero quantized content support so side signals
    cannot create a popularity-only list.
14. Apply non-negative fixed-scale weights, verify their exact configured sum,
    and calculate integer contribution and final-score units with the
    documented rounding mode.
15. Sort using final, content, and popularity units plus stable slug in the
    documented order.
16. Generate one-based rank after final ordering.
17. Produce serialized raw score, weight, contribution, and final score
    directly from canonical units.
18. Produce matching genre/tag, preferred-platform, similar-selected-game, and
    popularity evidence.
19. Render deterministic explanation summary and ordered reasons from that
    evidence.
20. Keep the loaded matrix, vectorizer configuration, vocabulary,
    inverse-document-frequency values, and row maps immutable across
    concurrent requests.

### Verification

- The same context and artifact produce the same order, serialized scores, and
  explanations repeatedly.
- Selected games never recommend themselves.
- Unknown selections are rejected before ranking.
- Platform preferences affect only the platform component.
- Final scores are finite and bounded.
- Serialized contribution units sum exactly to serialized final-score units.
- Adversarial raw-float near-ties use the same quantized ranking keys and
  stable ordering on supported Windows and Linux runtimes.
- A quantized score tie follows the complete stable tie-break sequence.
- `top_k` smaller than, equal to, or larger than the remaining candidate count
  behaves as documented.
- No remaining or positively content-supported candidate produces the
  appropriate explicit successful empty result.
- Explanation text contains only evidence present in the typed result.
- Ranking does not mutate the artifact or query PostgreSQL directly.
- Sparse inference does not densify the full feature matrix.

### Exit Criteria

- Ranking behavior is pure, deterministic, bounded, and independently tested.
- Every visible reason can be traced to structured evidence.
- The model makes no persistence or quality claim.

## 12. Implementation Phase 5: Recommendation Service and Model Lifecycle

### Objective

Replace the placeholder-only lifecycle with an injectable service that loads a
validated artifact honestly while preserving catalog availability.

### Work

1. Replace the `dict[str, object]` and `list[object]` recommendation protocol
   boundary with typed domain input and output.
2. Retain a tested `NotConfiguredRecommendationService`.
3. Add explicit unavailable outcomes with stable reason codes for:
   - Configured path missing.
   - Manifest invalid.
   - Checksum failure.
   - Artifact path outside the configured root policy.
   - Resource, archive, dtype, or shape limit failure.
   - Artifact schema incompatible.
   - Library/code compatibility failure.
   - Catalog fingerprint mismatch.
   - Model construction failure.

   Intrinsic failures construct an unavailable service; catalog mismatch is a
   request/status orchestration outcome over an otherwise loaded artifact.

4. Add validated backend-only `MODEL_ARTIFACT_PATH` configuration without a
   browser-public equivalent.
5. Build the recommendation service through an injectable factory.
6. During application lifecycle:
   - Resolve and validate the configured operator-controlled artifact root.
   - Validate intrinsic manifest, path, resource, checksum, schema, library,
     and code compatibility.
   - Load transparent numeric members with object/pickle behavior disabled.
   - Construct one immutable loaded service.
   - Convert expected intrinsic artifact failures into an unavailable service.
7. For a loaded service, make model status and recommendation orchestration
   obtain one current `REPEATABLE READ, READ ONLY` catalog snapshot and compare
   its fingerprint before reporting `ready` or ranking.
8. Do not catch database readiness failures as model-only errors.
9. Keep existing catalog health semantics independent from optional
   recommendation capability.
10. Extend model status with `unavailable`, safe reason codes, artifact
    metadata, feature families, and truthful capabilities.
11. Ensure unavailable status never leaks configured paths, stack traces,
    secret environment values, or numeric loader internals.
12. Add lifecycle disposal only if a selected library owns a real disposable
    resource; do not invent cleanup for immutable arrays.
13. Verify the loaded service is constructed once rather than once per
    request, while catalog freshness is checked on both status and
    recommendation paths.

### Verification

- No configured path returns `not_configured`.
- A configured missing, corrupt, incompatible, or stale bundle returns
  `unavailable` with the expected safe code.
- A valid matching bundle returns `ready`, the active model name/version, and
  `recommend=true`, `explanations=true`.
- The intrinsically loaded service is reused across requests and remains
  immutable; `ready` is recomputed from each status/request snapshot.
- A catalog mutation after startup makes both status and recommendation return
  the same stale-artifact outcome on their next consistent snapshot.
- A concurrent mutation cannot mix pre-change and post-change catalog rows in
  one fingerprint or response.
- Expected artifact failure does not crash the catalog application.
- Database readiness behavior remains unchanged.
- Tests can inject each service state without filesystem or global monkeypatch
  coupling.
- No model build, download, or artifact mutation occurs during startup.

### Exit Criteria

- Model readiness is honest and fully typed.
- Catalog functionality survives recommendation unavailability.
- Only an intrinsically valid artifact matching the request-time catalog
  snapshot can activate inference.

## 13. Implementation Phase 6: Recommendation HTTP and OpenAPI Contracts

### Objective

Expose bounded anonymous recommendations through a stable, documented HTTP
contract before enabling the web experience.

### Work

1. Add Pydantic request schemas with the Section 5.5 bounds,
   at-least-one-positive-content-signal rule, and unknown-field rejection.
2. Enforce the existing 32-bit positive database-ID bound and the taxonomy
   slug length/pattern before repository queries.
3. Reject duplicate selection values through controlled validation.
4. Add typed response schemas for:
   - Model identity.
   - Normalized request summary where required.
   - Ranked game item.
   - Score components.
   - Structured evidence.
   - Deterministic explanation.
   - Empty-candidate result.
5. Reuse `GameSummary` rather than defining a divergent game-card shape.
6. Add a recommendation application service that:
   - Opens one `REPEATABLE READ, READ ONLY` transaction.
   - Builds one canonical current-catalog snapshot.
   - Resolves IDs and taxonomy slugs through repositories.
   - Validates artifact/current-catalog compatibility.
   - Calls the injected ranker.
   - Serializes game summaries from the same snapshot.
   - Performs no database write.
7. Refactor `GET /api/v1/models/status` so a loaded artifact uses the same
   snapshot and fingerprint policy before reporting `ready`.
8. Add `POST /api/v1/recommendations`.
9. Return HTTP 200 with a stable response reason for a valid request with zero
   remaining or positively content-supported candidates.
10. Map malformed or insufficient context to controlled HTTP 422 error codes.
11. Map unconfigured or unavailable model state to controlled HTTP 503 error
    codes.
12. Preserve the centralized standard error envelope.
13. Add `POST` to the explicit CORS method allowlist.
14. Test allowed-origin and rejected-origin preflight requests.
15. Register every new schema and response in OpenAPI.
16. Regenerate the committed TypeScript contract only after the live endpoint
    tests pass.
17. Add API documentation examples whose game IDs are derived from fixtures
    rather than implied production constants where practical.

### Verification

- The OpenAPI document contains the exact typed request, success, validation,
  and unavailable contracts.
- Boundaries for selection counts, slug shapes, IDs, and `top_k` are enforced.
- Duplicate and unknown values follow the documented error semantics.
- Insufficient and zero-vector contexts are distinguishable and recoverable.
- Ready requests return ordered items with reconstructable component details
  and evidence.
- Unconfigured and unavailable services return HTTP 503 without a fabricated
  fallback.
- A post-startup catalog change produces the same stale-artifact reason through
  status and recommendation paths.
- One request cannot mix rows across a concurrent catalog mutation.
- Allowed web origins can preflight and send JSON `POST`; unknown origins
  receive no allow-origin grant.
- Recommendation requests leave preferences, interactions, recommendation
  events, and users unchanged.
- Existing health, catalog, detail, taxonomy, model-status, error, and CORS
  contracts remain green.
- Generated frontend types match the live document.

### Exit Criteria

- The real recommendation capability is usable without the frontend.
- Contract and failure semantics are stable enough for Stage 3 UI work.
- The API remains the only ranking owner.

## 14. Implementation Phase 7: Onboarding, Results, and Product States

### Objective

Turn the verified recommendation contract into an accessible, responsive,
truthful anonymous product flow.

### Work

1. Extend the project-owned API client with one reusable typed JSON request
   path that supports:
   - `POST` bodies.
   - JSON accept and content-type headers.
   - Abort signals.
   - Successful JSON parsing.
   - Existing standard error-envelope normalization.
   - Non-JSON and malformed-response handling.
2. Export recommendation request and response types from the generated
   OpenAPI contract rather than hand-copying them.
3. Add the `/recommendations` route and one focused client feature boundary.
4. Define a local reducer or equivalent state machine for:
   - Current onboarding step.
   - Selected games, genres, tags, and platforms.
   - Search draft and available options.
   - Review state.
   - Submission state.
   - Results.
   - Recoverable and terminal failures.
5. Use existing catalog search and metadata contracts to populate choices.
6. Reuse project-owned buttons, notices, loading states, game summaries,
   taxonomy presentation, focus styles, shell, and error boundaries.
7. Implement a bounded example-game chooser that prevents duplicate selection
   and clearly reports the five-game limit.
8. Use semantic `form`, `fieldset`, `legend`, labels, native checkboxes, and
   buttons for taxonomy and platform choices unless Phase 0 proves a custom
   composite control is necessary.
9. Explain before submission that:
   - Selections are used for the current recommendation request.
   - They are not saved to an account or used as durable feedback.
   - Results come from the named project-owned content model.
10. Prevent submission until at least one selected game, genre, or tag exists.
11. Present a review step with clear edit, remove, submit, and start-over
    actions.
12. Abort superseded catalog-search or recommendation requests.
13. Prevent stale or out-of-order requests from replacing the current state.
14. Render recommendation items in API rank order without re-sorting or
    recomputing scores.
15. Present:
    - Rank.
    - Game summary and detail link.
    - Human-readable evidence.
    - Deterministic explanation.
    - A ranking-score label that does not imply probability.
    - Optional accessible score-detail disclosure for component raw score,
      weight, and contribution.
16. Add an adjust-selections action that preserves the current in-memory draft
    during the mounted flow.
17. Add a start-over action that clears the current request state deliberately.
18. Implement distinct experiences for:
    - Initial onboarding.
    - Catalog-search loading and partial failure.
    - Insufficient input.
    - API validation failure.
    - Submitting.
    - Populated results.
    - Valid empty candidates.
    - Model not configured.
    - Model unavailable, including a stale-artifact reason.
    - Network/database unavailability.
    - Malformed response.
    - Unexpected failure.
19. Move landing-page and primary-navigation recommendation calls to action
    from future copy to active behavior only after full-stack integration
    passes.
20. Replace the Stage 2 no-recommendation-control regression deliberately; do
    not weaken unrelated truthful-copy assertions.
21. Preserve catalog and detail routes and their existing URL behavior.
22. Add route metadata and no-script/failure copy that does not claim
    persistent personalization.
23. Verify mobile, tablet, laptop, and wide layouts from the first feature
    slice rather than after visual completion.

### Verification

- Generated OpenAPI types are the client contract source.
- No feature component issues an independent raw recommendation request.
- The browser sends the exact bounded request and renders the returned order.
- The browser does not calculate final scores, apply weights, or invent
  explanations.
- Duplicate and over-limit selections are prevented accessibly.
- Keyboard users can complete, review, submit, inspect, adjust, restart, and
  open a result.
- Labels, legends, heading order, focus movement, error associations, and live
  status announcements are meaningful.
- Superseded search and recommendation responses cannot overwrite current
  state.
- Loading, insufficient, validation, empty, unavailable, network, malformed,
  and unexpected states expose a relevant recovery action.
- Model-unavailable copy does not imply that catalog browsing is unavailable.
- Result scores are labeled as ranking scores rather than probabilities or
  calibrated percentages.
- The flow creates no local durable identity and makes no API write.
- Catalog and detail regression behavior remains intact.
- Representative viewports have no page-level horizontal overflow.

### Exit Criteria

- An anonymous user can move from onboarding to real explained recommendations
  using only the verified API.
- The flow is truthful, keyboard accessible, responsive, and recoverable.
- Ranking and persistence remain outside the browser.

## 15. Implementation Phase 8: Docker and Explicit Artifact Commands

### Objective

Provide reproducible host and Docker workflows for artifact build, validation,
API loading, and isolated browser acceptance without hidden training or
destructive state changes.

### Work

1. Adapt the API build context only as far as required to install the pinned
   shared ML package and runtime numerical dependencies.
2. Preserve strict Docker ignore behavior for secrets, local environments,
   caches, untracked data, and generated artifacts.
3. Keep the API runtime non-root and the artifact mount read-only.
4. Add backend-only `MODEL_ARTIFACT_PATH` to the tracked environment example
   with a safe development path and no secret value.
5. Add an explicit offline model-build command that:
   - Requires a migrated compatible database.
   - Reads a consistent catalog snapshot.
   - Writes only to the explicit artifact output.
   - Validates before promotion.
   - Prints safe structured model/version/fingerprint/item counters.
6. Add an explicit artifact-inspect or validate command that performs no
   database or artifact mutation.
7. Add a model-focused fast-test command.
8. Add optional root Make wrappers only after the direct PowerShell, Python,
   and Docker commands work.
9. Do not add model building to Alembic, seed, ordinary `api`, ordinary `web`,
   or application startup.
10. Document the ready development order:
    - Start PostgreSQL.
    - Apply migrations.
    - Seed the catalog.
    - Build and validate the artifact explicitly.
    - Start or restart API and web with the configured artifact.
11. Extend the isolated E2E topology with a one-shot model setup stage after
    migration and seed and before API readiness.
12. Give the E2E model setup a disposable artifact location visible read-only
    to its API service.
13. Keep the E2E PostgreSQL database on `tmpfs` with no published host port.
14. Ensure E2E teardown removes only its disposable project resources.
15. Validate development, API-test, and E2E Compose definitions without
    printing interpolated secrets.
16. Verify that a development API can still start in honest
    `not_configured` or `unavailable` mode when the model path is absent or
    invalid.
17. Verify that a fresh ready-stack workflow reaches `ready` only after the
    explicit model build and API restart.
18. Document Windows PowerShell equivalents for every acceptance command; GNU
    Make remains optional.

### Verification

- The API image contains the exact locked ML runtime and shared package.
- Generated local artifacts and datasets are not copied into images
  accidentally.
- The runtime container reads but cannot mutate the mounted artifact.
- Ordinary API/web startup never fits or writes a model.
- The explicit build produces a validated artifact from the migrated seeded
  database.
- Inspect/validate performs no mutation.
- Missing or bad artifact configuration yields the documented status without
  breaking catalog startup.
- The isolated E2E stack orders migrate, seed, artifact build, API, web, and
  browser services correctly.
- E2E uses only its disposable database and artifact locations.
- No command deletes the persistent development database or development
  artifacts.
- Direct PowerShell commands work without GNU Make.
- All Compose configurations pass quiet validation.

### Exit Criteria

- A fresh clone has a documented explicit path to a ready local recommender.
- Artifact lifecycle operations are reproducible and never hidden.
- Browser acceptance is isolated from persistent development state.

## 16. Implementation Phase 9: Test Matrix and Quality Gate

### Objective

Verify functional correctness, determinism, artifact safety, contract
fidelity, accessibility, operational behavior, and earlier-stage regression
before Stage 3 is considered complete.

### ML and Ranking Fast Suite

Test at least:

- Canonical Unicode, whitespace, case, ordering, and taxonomy normalization.
- Stable semantic fingerprint under irrelevant source-order changes.
- Fingerprint change under meaningful feature changes.
- Duplicate, missing, unresolved, non-finite, and malformed snapshot input.
- Popularity prior formula, rating-volume protection, normalization, constant
  ranges, missing values, and ties.
- Field-aware document creation across every required feature family.
- Platform exclusion from TF-IDF text.
- Empty-vocabulary, zero-row, matrix-shape, and row-map failures.
- Artifact-schema validation, relative paths, checksums, compatibility, and
  atomic promotion.
- Artifact resource caps, archive expansion, numeric dtype/shape, transparent
  loader ordering, and disabled object/pickle behavior.
- Selected-game centroid and taxonomy preference vector construction.
- Zero-vector context.
- Non-zero context with no positively content-supported remaining candidate.
- Platform component isolation.
- Component bounds, non-negative weights, and weight-sum invariant.
- Fixed-scale raw, weight, contribution, and final-score units.
- Selected-candidate exclusion.
- Stable top-K, adversarial near-ties, and complete quantized tie-break order
  across supported host and container runtimes.
- Exact wire-level final-score reconstruction from serialized contributions.
- Evidence and explanation consistency.
- Repeated fixed-input build and ranking determinism.

### API Fast Suite

Test at least:

- Unconfigured, unavailable, and ready status responses.
- Missing, corrupt, out-of-policy, over-limit, incompatible, stale, and valid
  artifact injection.
- Safe unavailable reason codes and secret/path redaction.
- Request scalar/collection bounds, unknown-field rejection, and
  at-least-one-content-signal validation.
- Duplicate and unknown game/taxonomy handling.
- `top_k` lower and upper bounds.
- Insufficient, zero-vector, and no-positive-content-support contexts.
- Populated and empty-candidate success responses.
- Exact rank, fixed-scale component, and wire-reconstruction response schema.
- Read-only behavior.
- HTTP 422 and 503 standard error envelopes.
- JSON content-type and malformed body behavior.
- Allowed and rejected CORS preflight for `POST`.
- OpenAPI inclusion and schema examples.
- Existing health, catalog, detail, taxonomy, error, logging, configuration,
  launcher, seed-safety, and session behavior.

### PostgreSQL Integration Suite

Use the existing disposable guarded PostgreSQL topology to verify:

- Alembic upgrades and deterministic seed still succeed.
- Canonical snapshot extraction matches the seeded catalog.
- Artifact/current-catalog fingerprint alignment succeeds.
- A meaningful catalog change produces stale-artifact behavior.
- Status and recommendation agree after a post-startup catalog change.
- A concurrent catalog mutation cannot produce a mixed canonical snapshot or
  mixed recommendation response.
- Integer request IDs resolve to stable artifact slugs.
- Unknown IDs and taxonomy slugs fail as documented.
- A recommendation request performs no insert, update, or delete on users,
  preferences, interactions, recommendation events, games, or taxonomy.
- Database constraint and repository regressions remain green.
- Test reset guards still reject unsafe targets.

### Frontend Fast Suite

Test at least:

- Onboarding reducer/state transitions.
- Selection caps, duplicate prevention, removal, review, adjust, and restart.
- At-least-one-content-signal validation.
- Typed JSON `POST`, headers, body, abort, and error normalization.
- Superseded-response protection.
- Populated and empty result rendering in API order.
- Ranking-score terminology.
- Structured evidence and explanation rendering.
- Unconfigured, unavailable, validation, network, malformed, and unexpected
  recovery states.
- Truthful landing and navigation activation.
- No browser-side ranking or durable-persistence copy.
- Existing route parsing, formatting, API-client, catalog, detail, and shared
  UI behavior.

### Browser and Accessibility Suite

Run the complete recommendation flow in the pinned Chromium engine and
critical smoke paths in pinned Firefox and WebKit. Cover:

- Landing or primary navigation to onboarding.
- Game search and bounded example selection.
- Genre/tag and optional platform selection.
- Review, submit, and populated results.
- Rank and structured-reason presentation.
- Game-detail navigation from a result.
- Adjust and start-over actions.
- Insufficient input and selection limits.
- Empty-candidate behavior.
- Model unavailable and retry/recovery.
- API/network failure and recovery.
- Rapid request supersession.
- Console and page-error collection on happy paths.
- Keyboard-only completion.
- Visible focus and focus movement after validation/submission.
- Automated accessibility scans under the documented severity policy.
- No page-level horizontal overflow at 320, 768, and 1440 CSS pixels.

### OpenAPI and Contract Drift

- Regenerate the committed TypeScript contract from the live API in any honest
  model state; OpenAPI generation must not require a ready artifact.
- Fail when generated output differs.
- Verify the client imports generated recommendation types.
- Verify no handwritten response interface duplicates the backend schema.
- Retain existing catalog contract checks.

### Stage 1 and Stage 2 Regression Suites

- Re-run all fast API tests.
- Re-run disposable-PostgreSQL integration tests.
- Re-run Ruff lint and format checks.
- Re-run clean frontend install, strict TypeScript, ESLint, Prettier, fast
  tests, and production build.
- Re-run the existing catalog/detail browser and accessibility scenarios.
- Re-run development, API-test, and E2E Compose validation.
- Re-run healthy full-stack catalog and detail smoke checks.
- Update only baseline assertions that Stage 3 deliberately changes, such as
  `not_configured` or the absence of recommendation controls; preserve the
  rest of their intent.

### Dependency, Artifact, and Secret Review

- Inspect exact direct and locked transitive ML/API dependencies.
- Record licenses and vulnerability findings without calling a partial scan
  clean.
- Confirm artifacts use only non-executable transparent JSON/NPY/NPZ members,
  object/pickle loading is disabled, and the runtime root is operator
  controlled and read-only.
- Inspect generated manifests for absolute paths, usernames, credentials, or
  environment-specific values.
- Confirm large artifacts, processed data, generated reports, caches, coverage,
  browser traces, screenshots, videos, environments, and secrets remain
  ignored.
- Review any committed small fixture for necessity, provenance, regeneration,
  and size.
- Inspect web output for backend-only model paths or database configuration.

### Operational Smoke Test

On a fresh disposable topology:

1. Validate all Compose definitions.
2. Build the API and web images.
3. Start the isolated PostgreSQL service.
4. Apply Alembic migrations explicitly.
5. Load the deterministic catalog explicitly.
6. Build and validate the model artifact explicitly.
7. Start the API with the artifact mounted read-only.
8. Verify database health and model `ready` status.
9. Start the web service.
10. Execute model status, recommendation POST, landing, onboarding, results,
    catalog, detail, OpenAPI, and documentation smoke checks.
11. Execute the locked browser suite.
12. Tear down only disposable resources.
13. Confirm the persistent development database and development artifacts were
    not reset, deleted, or overwritten.

### Coverage and Performance Policy

Coverage is diagnostic. Meaningful corruption, compatibility, numeric-boundary,
validation, recovery, and integration paths matter more than a single
percentage threshold.

Record build time, artifact size, model load time, and representative request
latency as engineering diagnostics on the 30-game fixture. Do not turn those
numbers into scale or production-performance claims. A bounded request must
not fit a vectorizer, reload the artifact, or densify the complete feature
matrix.

### Exit Criteria

- ML, API, PostgreSQL, frontend, browser, accessibility, OpenAPI, dependency,
  artifact, Docker, and operational gates pass.
- Rankings and explanations are deterministic under the documented policy.
- The real full-stack flow uses a validated disposable artifact.
- Stage 1 and Stage 2 remain reliable.
- No persistent development data or model artifact was destructively changed.
- Results support functional and reproducibility claims only.

## 17. Implementation Phase 10: Documentation and Release Preparation

### Objective

Synchronize documentation with verified Stage 3 behavior and leave a precise
Stage 4 handoff.

### Work

1. Update the root `README.md` with:
   - Completed Stage 3 status only after the acceptance gate passes.
   - Verified model-build and ready-stack setup.
   - Implemented user experience.
   - New backend-only environment configuration.
   - Verified root commands.
   - Acceptance evidence and current limitations.
2. Update `apps/api/README.md` with:
   - Implemented recommendation and model-status contracts.
   - Request/response examples.
   - Artifact configuration and safe failure states.
   - Direct and Docker commands.
   - CORS behavior and quality gates.
3. Update `apps/web/README.md` with:
   - Implemented route and state ownership.
   - Onboarding/result behavior.
   - Client contract and browser gates.
   - The boundary between request-scoped Stage 3 preferences and Stage 4
     persistence.
4. Update `ml/README.md` with:
   - Implemented package ownership.
   - Exact build, inspect, validate, lint, format, and test commands.
   - Artifact contents, trust policy, provenance, and limitations.
5. Update `docs/architecture.md` from planned to implemented boundaries.
6. Update `docs/recommendation-design.md` with the final formula,
   preprocessing, artifact, request, response, score, and explanation
   decisions.
7. Update `docs/roadmap.md` to Complete only after all acceptance criteria pass.
8. Update `data/README.md` only if Stage 3 adds a real processed snapshot or
   changes the documented data boundary.
9. Update `infra/README.md` with the artifact builder and E2E topology only
   after those workflows are verified.
10. Update `scripts/README.md` only for real cross-project scripts.
11. Record every resolved implementation-time decision in Section 21.
12. Replace the provisional Stage 4 handoff in Section 22 with exact
    implemented contracts, fixtures, commands, and limitations.
13. Populate Section 23 with actual dates, versions, commands, counts,
    diagnostics, audit results, and known gaps.
14. Verify all README commands from their documented working directories.
15. Verify every relative Markdown link and Mermaid diagram.
16. Run Markdown lint and `git diff --check`.
17. Inspect the final diff for generated artifacts, reports, local paths,
    secrets, and unrelated scope.

### Suggested Commit Structure

1. `chore(ml): establish reproducible recommendation workspace`
2. `feat(ml): build deterministic catalog artifact and content ranker`
3. `feat(api): expose artifact-backed recommendation contracts`
4. `feat(web): add anonymous recommendation onboarding and results`
5. `test(recommendations): add full-stack model and browser acceptance`
6. `docs(recommendations): record Stage 3 verification and Stage 4 handoff`

Actual commits may combine tightly related work, but each should leave the
repository testable and reviewable.

### Exit Criteria

- Documentation describes verified rather than intended implementation
  behavior.
- Every documented command has been executed successfully.
- Roadmap, architecture, recommendation design, root README, and application
  READMEs agree.
- The Stage 4 handoff names real contracts and remaining limitations.
- The final diff contains only Stage 3 scope and intentional generated
  contract/test-fixture artifacts.
- Completion evidence is reviewable without relying on unstated local
  knowledge.

## 18. Command Interface Target

The exact entrypoint module names will be confirmed in Phase 0. The target
capabilities are:

| Capability                        | Optional Make wrapper       | Direct equivalent required                              |
| --------------------------------- | --------------------------- | ------------------------------------------------------- |
| Validate all Compose definitions  | `make config`               | `docker compose ... config --quiet` for every file      |
| Build API and ML runtime          | `make build`                | `docker compose build api`                              |
| Migrate database                  | `make migrate`              | Existing Alembic container command                      |
| Seed catalog                      | `make seed`                 | Existing seed container command                         |
| Build model artifact              | `make model-build`          | Explicit Python or one-shot Compose builder command     |
| Inspect/validate artifact         | `make model-validate`       | Read-only Python or Compose validation command          |
| Run ML fast tests                 | `make test-ml`              | pytest against `ml/tests`                               |
| Run API fast tests                | `make test`                 | Existing quality-container pytest command               |
| Run PostgreSQL integration tests  | `make test-integration`     | Existing guarded disposable Compose command             |
| Run web quality gate              | `make test-web`             | Existing npm commands                                   |
| Run isolated Stage 3 browser gate | `make test-web-e2e`         | E2E Compose command with model setup                    |
| Lint/format ML and API            | `make lint` / `make format` | Direct Ruff commands over both boundaries               |
| Refresh OpenAPI types             | `make api-types`            | Existing npm generation command                         |
| Start configured stack            | `make up`                   | Explicit Compose startup after migrate/seed/model build |

No wrapper may hide migration, seed, artifact creation, destructive cleanup,
or network installation. `make up` may load an already configured artifact but
must not build one. GNU Make remains optional; direct PowerShell, Python, npm,
and Docker commands are mandatory documentation.

Existing Stage 1 and Stage 2 command meanings should remain stable. If a build
context or quality target changes, its direct equivalent and safety properties
must be updated in the same implementation slice.

## 19. Acceptance Criteria

Stage 3 is complete only when all of the following are true:

- Stage 1 and Stage 2 acceptance gates remain green.
- The ML project installs reproducibly on the supported host workflow and from
  the committed Linux/Python 3.12 lock.
- Exact direct dependencies, transitive container dependencies, licenses, and
  security findings are recorded honestly.
- The canonical catalog snapshot is read-only, stable-slug ordered, validated,
  and fingerprinted deterministically.
- Irrelevant source ordering does not change the semantic fingerprint; a
  meaningful feature change does.
- The popularity baseline formula, prior, normalization, missing-value policy,
  weights, version, and tie behavior are documented and tested independently.
- TF-IDF uses title, genre, tag, developer, publisher, and description through
  a versioned preprocessing configuration.
- Preferred platform remains a separately observable component.
- The feature matrix remains sparse and aligns exactly with stable artifact
  slugs.
- Empty vocabulary, invalid features, non-finite values, zero rows, resource
  limit violations, unsafe dtypes, and shape mismatch fail clearly before
  promotion or numeric allocation where possible.
- The artifact manifest records model/version, schema, creation time, data
  fingerprint, feature/ranking configuration, compatibility metadata, stable
  mapping, member sizes, and checksums.
- Artifact writing is atomic and constrained to an explicit output root.
- Missing, malformed, integrity-failing, out-of-policy, over-limit,
  incompatible, and stale artifacts fail closed.
- The artifact uses transparent non-executable JSON/NPY/NPZ members; object and
  pickle loading are disabled.
- The operator-controlled, read-only configured root is documented as the
  provenance trust boundary; bundle checksums are not misrepresented as
  producer authentication.
- Same snapshot, configuration, dependency graph, seed, and fixed clock produce
  the same semantic artifact and ranking outputs.
- Request selection counts, distinctness, ID/slug validity, primary-signal
  requirement, and `top_k` are bounded and tested.
- The same valid request and artifact produce the same ordered ranks,
  serialized scores, evidence, and explanation text.
- Selected example games are excluded from their own results.
- A non-zero user vector with no positive content support returns the
  documented successful empty state rather than a popularity-only list.
- Feedback-derived dislike/played filtering is not claimed or implemented.
- Final scores are finite, bounded, and represented by canonical fixed-scale
  units; serialized contribution units sum exactly to serialized final-score
  units.
- Adversarial near-ties produce the same quantized keys and complete stable
  order on supported Windows and Linux runtimes.
- Ranking scores are not represented as probabilities or calibrated match
  percentages.
- Model status distinguishes `not_configured`, `unavailable`, and `ready`.
- `ready` appears only after intrinsic artifact validation and a current
  transactionally consistent catalog-fingerprint comparison.
- Status and recommendation paths return the same stale-artifact outcome after
  a post-startup catalog change, and concurrent mutation cannot create a mixed
  snapshot.
- Catalog routes remain available when recommendation capability is
  unavailable.
- No unavailable state silently falls back to fabricated recommendations.
- `POST /api/v1/recommendations` has a complete OpenAPI contract and standard
  error envelopes.
- Allowed and rejected JSON `POST` CORS preflight behavior is verified.
- Recommendation requests perform no database writes.
- Generated frontend recommendation types match the live OpenAPI document.
- The project-owned browser API client is the only recommendation transport.
- An anonymous user can select bounded context, review it, submit it, receive
  real ordered recommendations, understand structured reasons, adjust the
  current flow, and start over.
- The browser neither ranks games nor recalculates component weights.
- Onboarding and result copy does not imply saved preferences, feedback,
  identity, or cross-session personalization.
- Initial, search-loading, insufficient, validation, submitting, populated,
  empty, unconfigured, unavailable, network, malformed, and unexpected states
  behave as documented.
- Critical onboarding and result workflows are keyboard accessible with
  visible focus and useful announcements.
- Automated accessibility checks pass under the documented severity policy.
- Critical flows pass in pinned Chromium, Firefox, and WebKit.
- Recommendation layouts have no page-level overflow at 320, 768, and 1440
  CSS pixels.
- Ordinary API/web startup never trains or writes an artifact.
- A fresh explicit Docker workflow can migrate, seed, build/validate an
  artifact, start a ready API/web stack, and complete the real browser flow.
- The E2E database and artifact are disposable and do not touch persistent
  development state.
- Build time, artifact size, load time, request latency, and diagnostic
  coverage are recorded without unsupported scale or quality claims.
- No generated model bundle, processed dataset, report, cache, trace, local
  environment, secret, or user-specific path is committed unintentionally.
- Root and application documentation contains only verified commands and
  behavior.
- Known limitations and the Stage 4 handoff are documented.

## 20. Risks and Mitigations

**Risk:** The 30-game synthetic catalog produces plausible-looking results
that are mistaken for evidence of recommendation quality.

**Mitigation:** Limit Stage 3 claims to functional integration,
reproducibility, and explainability. Label seed signals as synthetic and defer
comparative ranking metrics to Stage 6.

**Risk:** Offline and online preprocessing drift into different
implementations.

**Mitigation:** Use one shared pure package and contract fixtures for snapshot
schemas, tokens, vectorization, artifact loading, and scoring.

**Risk:** Artifact rows are coupled to environment-specific database IDs.

**Mitigation:** Key and order artifact records by stable slug; resolve request
IDs through the current database before ranking.

**Risk:** A model is reported ready even though the artifact no longer matches
the current catalog.

**Mitigation:** Fingerprint one `REPEATABLE READ, READ ONLY` snapshot on every
configured status and recommendation path, require exact alignment before
reporting `ready` or ranking, and test post-startup plus concurrent mutation.

**Risk:** A missing, corrupt, or incompatible artifact crashes the entire API
or silently returns popularity results.

**Mitigation:** Convert expected model failures into an explicit unavailable
service, preserve catalog availability, and return a typed HTTP 503 for
recommendation calls.

**Risk:** Self-recorded checksums are mistaken for producer authentication, or
a replaced artifact executes code while loading.

**Mitigation:** State explicitly that the operator-controlled read-only root is
the provenance trust boundary, never accept request-selected paths, use only
transparent JSON/NPY/NPZ members with object and pickle loading disabled, and
defer external signing to the Stage 7 production trust design.

**Risk:** A malformed or oversized sparse bundle exhausts memory or CPU before
validation.

**Mitigation:** Bound bundle bytes, members, archive expansion, items,
vocabulary, shapes, non-zero entries, dtypes, and evidence lengths; validate
declared limits before allocation where possible and loaded shapes afterward.

**Risk:** A partially written artifact is activated.

**Mitigation:** Build into a temporary sibling, validate the complete bundle,
and promote atomically only after success.

**Risk:** Title, prose, taxonomy, or popularity weighting overwhelms every
other signal accidentally.

**Mitigation:** Normalize each component, version all field and component
weights, test invariants and reviewed fixtures, and expose component
contributions.

**Risk:** Genre/tag preference is counted once in the user content vector and
again as overlap without an explicit design.

**Mitigation:** Decide the taxonomy component formula in Phase 0, document the
reason for any double representation, and make each contribution independently
observable.

**Risk:** Platform preference is hidden in TF-IDF and cannot be explained.

**Mitigation:** Keep platform out of the text document and score it through a
separate typed component.

**Risk:** Floating-point or library-version differences make rankings flaky.

**Mitigation:** Pin the supported dependency graph, record dtype, quantize raw
components into canonical fixed-scale integer units, rank and serialize from
those units, and test adversarial near-ties across supported runtimes before
stable slug tie-breaking.

**Risk:** Empty or weak input produces a meaningless popularity-only list.

**Mitigation:** Require at least one game, genre, or tag signal and reject a
zero content vector with recoverable insufficient-context guidance. Exclude
zero-content-support candidates and return a documented successful empty state
when no supported candidate remains.

**Risk:** Duplicate or unknown selections are silently discarded and confuse
the user.

**Mitigation:** Enforce bounded distinct collections in both UI and API and
return controlled domain validation for unknown references.

**Risk:** The API reloads a heavy mutable model for every request.

**Mitigation:** Construct one validated immutable service per application
lifecycle and inject it into bounded request orchestration.

**Risk:** Raw score is presented as a probability or personalized certainty.

**Mitigation:** Name it a ranking score, prohibit percentage-match copy, and
pair it with concrete structured evidence.

**Risk:** Explanation prose mentions signals that did not affect ranking.

**Mitigation:** Generate prose exclusively from typed ranked evidence and test
reason/evidence consistency.

**Risk:** Adding JSON `POST` breaks the previously GET-only CORS policy.

**Mitigation:** Add `POST` intentionally, preserve explicit origins, and test
allowed and rejected preflight behavior.

**Risk:** Custom game or taxonomy selectors introduce keyboard and
screen-reader regressions.

**Mitigation:** Prefer native controls, bound the option set, define focus and
announcement behavior, and run keyboard plus automated accessibility gates.

**Risk:** Out-of-order search or recommendation responses overwrite newer
selections or results.

**Mitigation:** Abort superseded requests, associate responses with the
current request state, and test reversed completion order.

**Risk:** Frontend code begins re-sorting results or rebuilding scores.

**Mitigation:** Render API rank order directly and test that the submitted
request and returned order are preserved.

**Risk:** Artifact creation is hidden inside startup and makes failures or
data changes difficult to reason about.

**Mitigation:** Require explicit build and validation commands; ordinary
startup only loads configured immutable output.

**Risk:** The E2E builder modifies the persistent development database or
artifact directory.

**Mitigation:** Use the existing isolated `tmpfs` database plus a
project-scoped disposable artifact location and verify resource identities
before setup.

**Risk:** Numerical dependencies increase image size, build time, licensing,
or vulnerability exposure.

**Mitigation:** Smoke-test and review the exact dependency graph, justify each
direct package, avoid unused notebook/orchestration packages, and record honest
audit findings.

**Risk:** Generated artifacts, manifests, reports, or local paths are committed
accidentally.

**Mitigation:** Retain narrow ignore rules, make test fixtures explicit, scan
the final diff, and inspect manifests for environment-specific metadata.

**Risk:** Activating Stage 3 weakens catalog/detail tests by broadly replacing
the old `not_configured` baseline.

**Mitigation:** Change only assertions that the new capability deliberately
invalidates and retain the rest of the Stage 1 and Stage 2 regression intent.

## 21. Implementation-Time Decisions

1. The ML package targets Python 3.12 and pins NumPy 2.5.1, SciPy 1.18.0,
   scikit-learn 1.9.0, pytest 9.1.1, pytest-cov 7.1.0, Ruff 0.16.0, and
   setuptools 83.0.0. The separate ML and API locks include the complete
   numerical graph. pandas was not justified and was not added. NumPy, SciPy,
   scikit-learn, Joblib, and threadpoolctl use BSD-family licenses; Narwhals
   uses MIT.
2. The API image copies the ML project metadata and source from the root build
   context, installs it without dependency resolution after the API lock, and
   then installs the API package. The Dockerfile-specific allowlist admits only
   the required ML inputs.
3. Canonical records are ordered by stable slug; text uses NFKC and collapsed
   whitespace. Canonical JSON is UTF-8, sorted-key, compact, and rejects NaN.
   Duplicate slugs, non-finite numeric signals, empty catalogs, empty feature
   documents, or an empty TF-IDF vocabulary fail the build.
4. Popularity uses a 50-vote Bayesian prior against the vote-weighted catalog
   rating mean. Missing ratings use that mean. Rating and synthetic popularity
   are independently min-max normalized, with constant ranges mapped to 0.5,
   then combined 70%/30%.
5. Documents repeat normalized title twice; genre and tag field tokens three
   times; and developer, publisher, and description once. Platforms remain a
   separate interpretable signal.
6. TF-IDF is word-based with one- and two-grams, the versioned ASCII field-token
   pattern, Unicode accent stripping, `min_df=1`, `max_df=1.0`, sublinear term
   frequency, L2 normalization, and float64 CSR output.
7. Selected games form a normalized centroid; genres and tags form a vector in
   the fitted vocabulary. Either receives full weight alone. Together they
   receive 65%/35% and are renormalized. A zero or platform-only query returns
   controlled insufficient-context validation.
8. Final model `gamelens-content-tfidf` version `1.0.0` weights content 80%,
   preferred-platform overlap 10%, and popularity 10%. Taxonomy stays inside
   the content query rather than becoming a second final component.
9. Scores use a 1,000,000 fixed scale and round-half-up. Contributions are
   integer-reconstructed, so serialized contributions sum to the serialized
   final score. Ranking ties resolve by final score, content score, popularity
   score, then ascending stable slug. Selected and zero-content candidates are
   excluded.
10. Requests reject unknown fields and duplicates, allow at most 5 games, 5
    genres, 10 tags, 6 platforms, and `top_k` 1–20, and require a game, genre,
    or tag. Unknown references are controlled 422 errors. A valid request with
    no supported candidate returns 200 with `no_content_support` and an empty
    ordered list.
11. Responses include model and data identity, rank, final score, raw component
    scores, weights, contributions, matched taxonomy/platform values, up to
    three similar selected games, popularity evidence, and deterministic prose.
    Explanation priority is similar game, genre, tag, platform, then strong
    popularity support; prose never adds absent evidence.
12. Artifact schema `1` and code compatibility `stage-3-v1` use
    `manifest.json`, `catalog-items.json`, `vectorizer-config.json`,
    `vocabulary.json`, and five NPY members for IDF, CSR data/indices/indptr,
    and popularity. Builds use a temporary sibling and reject an existing final
    target instead of overwriting it.
13. The loader resolves each single-name member beneath the operator-controlled
    root, requires the exact set, validates size and SHA-256, uses
    `allow_pickle=False`, verifies dtype/shape/finiteness/canonical CSR
    structure, non-negative feature weights, L2-normalized rows, and feature
    configuration, and enforces 12-member, 64 MiB/member, 128 MiB total,
    100,000-item, 250,000-term, and 20,000,000-nonzero caps. Checksums detect
    corruption but do not authenticate an operator who can replace the root.
14. A blank path becomes no configuration. Missing, malformed, incompatible,
    integrity-failed, resource-limit, and construction failures become safe
    `unavailable` reason codes. The valid artifact is loaded once and its arrays
    are immutable; activation requires an API restart. Operators adopting the
    hardened loader rotate `MODEL_ARTIFACT_PATH`, rebuild and validate a new
    bundle, and never patch or overwrite the previous artifact directory.
15. PostgreSQL model reads explicitly use `REPEATABLE READ, READ ONLY`, eager
    catalog relationships, and one canonical snapshot. Status and recommendation
    both compare that fingerprint and agree on `catalog_stale` after mutation.
    A current catalog that cannot be canonicalized produces the controlled
    `catalog_invalid` unavailable reason on both paths.
16. The frontend uses one recommendation-flow boundary with local component
    state only; no transient tab storage or global store was justified. Native
    fieldsets and controls provide accessible semantics. Abort signals plus a
    submission key prevent superseded responses from winning.
17. Development uses an explicit `model-builder` profile and read-only API
    mount. E2E uses a tmpfs database and disposable named artifact volume; a
    root init only changes that new volume's owner, while model builder, API,
    web, and Playwright workloads run non-root. Root commands are
    `model-build`, `model-validate`, and `test-ml` in addition to existing gates.
18. No database migration or existing catalog-contract change was required.
    The Stage 1 unconfigured model-status JSON remains unchanged when optional
    Stage 3 fields are unset.

## 22. Stage 4 Handoff

Stage 3 leaves the feedback and persistence stage with:

- A reproducible catalog snapshot and versioned artifact-build workflow.
- A tested popularity baseline and TF-IDF content ranker.
- Stable model, artifact, data-fingerprint, ranking, and explanation
  identities.
- An immutable replaceable online recommendation service.
- Honest unconfigured, unavailable (including a stale-artifact reason), and
  ready model states.
- A typed bounded recommendation request and explained response contract.
- Independently observable component scores and structured evidence.
- A generated TypeScript contract and one project-owned recommendation client.
- An accessible anonymous onboarding and result flow.
- A deterministic ranking and browser fixture on a disposable full stack.
- Proof that Stage 3 recommendations are read-only and request-scoped.
- Complete Stage 1, Stage 2, and Stage 3 regression commands.

Stage 4 may then:

- Establish the anonymous-user identity lifecycle.
- Persist validated preferences.
- Define state-like interaction upsert semantics.
- Add like, dislike, played, wishlist, and rating write contracts.
- Exclude disliked games and apply documented played/feedback adjustments.
- Log bounded model-versioned recommendation events.
- Rehydrate durable context without embedding identity into model artifacts.

Stage 4 must preserve Stage 3 component observability and artifact identity so
feedback adjustments can be tested independently. It must not reinterpret a
Stage 3 request as already persisted history, and it must define consent,
retention, update, and deletion behavior before activating writes.

## 23. Verified Completion Record

**Completed:** 2026-08-07 on
`feat/stage-3-content-recommendation-mvp`.

### Runtime, dependencies, and security

- Python 3.12.13 ran the Linux acceptance containers. The numerical runtime is
  NumPy 2.5.1, SciPy 1.18.0, and scikit-learn 1.9.0. The API lock includes
  FastAPI 0.140.0, Pydantic 2.13.4, SQLAlchemy 2.0.51, Psycopg 3.3.4, and
  Uvicorn 0.51.0. Both Python locks install without a resolver escape and
  `pip check` reports no broken requirements.
- The web gate uses Node.js 24.18.0, npm 11.16.0, Next.js 16.2.12, React
  19.2.8, TypeScript 5.9.3, Vitest 4.1.10, and Playwright 1.62.0. A clean
  `npm ci` passed. Scoped overrides install fixed `brace-expansion` 1.1.18,
  2.1.4, and 5.0.9 plus `js-yaml` 4.3.1; both full and production npm audits
  report zero vulnerabilities.
- Numerical package licenses were reviewed as BSD-family, with Narwhals MIT;
  existing frontend licenses remain MIT, Apache-2.0, or MPL-2.0.
- Docker Scout 1.23.1 scanned the 173 MB pinned development API image and 195
  packages. It reports two critical and two high Debian `perl` advisories, all
  with no fixed version. The finding is not concealed by an unpinned apt
  upgrade: the local image remains non-root and loopback-only, and Stage 7 must
  choose and rescan a production-minimal base before deployment.

### Data, artifact, and deterministic ranking

- The source is the project-authored 30-game, 36-taxonomy deterministic seed.
  Stable-slug ordering plus NFKC/whitespace normalization and canonical JSON
  produce SHA-256 fingerprint
  `1a304ac3686742022ef41828bf48467412e34bd0e882c9b428cc723a5e2685e1`.
  The final hardened rebuild retained this fingerprint.
- Model `gamelens-content-tfidf` version `1.0.0`, artifact schema `1`, and code
  compatibility `stage-3-v1` produced 1,037 vocabulary terms and 1,399 sparse
  nonzeros. The 9-file bundle is 69,743 bytes. A measured database-to-artifact
  build took 0.43 seconds; ten complete validation loads from the Docker
  Desktop bind mount had min/median/max 89.64/95.54/274.79 ms.
- The repeated-build test fixes the UTC build clock and verifies byte-identical
  manifests; corruption changes are rejected. The suite also verifies
  order-independent snapshot identity, sensitivity to model inputs, sparse
  features, popularity prior behavior, deterministic rank order, selected-game
  exclusion, score reconstruction, platform-only rejection, and rejection of
  non-canonical CSR indices and invalid feature-weight invariants.
- The exact popularity, TF-IDF, user-vector, component, fixed-point, tie-break,
  artifact, error, and explanation decisions are recorded in Section 21 and
  `docs/recommendation-design.md`.

### Quality and operational evidence

- ML: 25 tests passed; diagnostic branch-aware package coverage is 81%.
- API: 104 fast tests passed; diagnostic branch-aware application coverage is
  92%. Ruff lint and formatting pass over API, migration, ML, and test code.
- PostgreSQL: 29 integration tests passed on an isolated tmpfs instance. The
  ready recommendation test records users, preferences, interactions,
  recommendation events, games, genres, tags, and platforms before and after a
  request and proves every count unchanged.
- Web: 45 tests in 8 files pass. Strict TypeScript, ESLint, Prettier, generated
  OpenAPI contract, and the Next.js production build pass. Diagnostic V8
  coverage is 53.25% statements overall and 77.51% for the recommendation flow;
  catalog/detail workflow coverage remains primarily browser-owned.
- Browser: 25 project tests pass without retry—15 Chromium plus 5 Firefox and 5
  WebKit smoke cases. The real anonymous flow selects genre/platform context,
  reviews it, sends the bounded POST, renders ordered explained results, and
  has no serious or critical axe findings. Recommendation layouts do not
  overflow at 320, 768, or 1440 CSS pixels.
- CORS tests prove the configured origin may preflight JSON `POST` while an
  unknown origin is rejected without an allow-origin header. Status and POST
  agree on `catalog_stale` and `catalog_invalid`; malformed bounds and unknown
  references use the standard error envelope.
- All three Compose files validate. The disposable E2E chain starts tmpfs
  PostgreSQL, migrates, seeds, initializes artifact ownership, builds and
  validates the model as non-root, mounts it read-only into the API, reaches
  ready status, serves web routes, and passes Playwright. Teardown removes only
  the E2E containers, network, and artifact volume; persistent development
  database, artifact, and web volumes were not reset or deleted.
- Twenty local in-container POST measurements using the loaded seed artifact
  had min/median/p95/max latency 11.57/12.37/13.19/13.55 ms. These figures are
  diagnostics on one machine and are not service-level objectives.

### Representative functional result

For request `preferred_genres=["rpg"]`,
`preferred_platforms=["linux"]`, and `top_k=5`, the ready model returned
`recommendations` in this deterministic order:

1. `moonroot` — 0.354279
2. `emberfall-tactics` — 0.334685
3. `runebreaker` — 0.318262
4. `bramblebound` — 0.219257
5. `tin-star-sheriff` — 0.187989

The result proves functional integration and reproducibility only. The scores
are ranking signals, not probabilities, match percentages, or evidence that
the model performs well on real users.

### Final scope and handoff

Generated model bundles, local environments, caches, coverage output, and E2E
resources remain ignored or disposable. The committed generated file is only
the OpenAPI-derived TypeScript contract. No secret, credential, external
dataset, schema migration, persisted preference, interaction write, or
recommendation-event write was added.

Known limitations are the synthetic 30-game catalog, request-only anonymous
state, no feedback adjustment, no collaborative signal, no formal ranking
evaluation, and the development base-image findings above. Section 22 is the
authoritative Stage 4 persistence and feedback handoff.
