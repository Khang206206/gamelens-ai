# GameLens AI

## Stage 5 Engineering Plan: Collaborative and Hybrid Ranking

- **Document status:** Engineering plan ready on 2026-08-19; external-source
  preflight verified on 2026-08-23; Phase 0–1 first-party audit foundation
  verified on 2026-08-24; Phase 2 offline collaborative artifact foundation
  verified on 2026-08-25; Phase 3 pure collaborative scoring and exact-row
  handoff verified on 2026-08-28. Phase 4 hybrid policy and runtime activation
  have not started.
- **Stage 4 prerequisite:** Complete and verified on 2026-08-13.
- **Planning and target implementation branch:**
  `feat/stage-5-collaborative-and-hybrid-ranking`
- **Primary outcome:** A reproducible, consent- and retention-aware
  collaborative artifact and a deterministic hybrid-ranking policy whose
  content, feedback, collaborative, platform, and popularity signals remain
  independently observable.

Sections 1–20 remain the forward-looking engineering plan except where the
Phase 0–3 slices are explicitly marked verified. Section 21 records only
measured implementation decisions. Section 22 is a provisional Stage 6
handoff, and Section 23 remains pending until every acceptance gate passes.
The Phase 3 scorer is an ML-only pure component. It does not make a Stage 5
hybrid API/runtime capability available.

## 1. Context

Stages 1 through 4 established the repository, PostgreSQL catalog, FastAPI and
Next.js applications, deterministic 30-game synthetic seed, reproducible
content artifact, request-scoped recommendation flow, explicit-consent
anonymous persistence, temporal feedback state, feedback-aware ranking, and
bounded recommendation-generation events. The implemented contracts and
verification evidence are recorded in the
[Stage 4 plan](stage-4-feedback-persistence-plan.md).

The currently served recommender is not collaborative. Model
`gamelens-content-tfidf/1.0.0` learns catalog-level TF-IDF features, and policy
`gamelens-feedback-adjustment/1.0.0` applies a deterministic per-request
content affinity plus dislike and played rules. Neither component learns
cross-user interaction patterns. The ML package now also exposes a pure
artifact-backed collaborative candidate scorer, but no API orchestration or
hybrid policy consumes it yet.

Stage 4 also leaves four constraints that control Stage 5:

- A recommendation event means that the server committed one personalized
  generation. It is not an impression, click, conversion, rating, or label.
- The current consent notice covers saved personalization data; it does not
  silently authorize a new offline aggregate model-training purpose.
- The seed catalog and developer-authored interactions prove functionality,
  reproducibility, deletion, and isolation. They are not evidence about real
  users or recommendation quality.
- Expired, revoked, cleared, or deleted state must not re-enter serving through
  snapshots, caches, artifacts, fixtures, or a rebuild.

Stage 5 therefore begins with a data-suitability and governance gate, not an
algorithm. An approved interaction source must have explicit provenance,
label meaning, consent authority, retention behavior, catalog alignment, and
enough support for the baseline. Until those conditions hold, the system must
report collaborative ranking as unavailable and preserve the verified Stage 4
path exactly.

The intended vertical slice is:

```text
separate affirmative contribution consent or project-owned test fixture
    -> one database-time, repeatable-read eligible-interaction snapshot
    -> aggregate audit and canonical fingerprint
    -> sparse binary user-item matrix in bounded build memory
    -> deterministic item-item cosine neighborhoods
    -> checksum-covered identity-free collaborative artifact
    -> pure collaborative candidate scorer
    -> versioned hybrid policy over observable Stage 3/4 components
    -> personalized API evidence and bounded generation event
    -> accessible browser disclosure and exact Stage 4 fallback
```

The production-shaped pipeline may be verified with a clearly labeled
project-authored interaction fixture. Activating an artifact built from local
or real user data remains blocked unless the Phase 0 consent and derived-data
lifecycle are implemented and the suitability audit passes.

## 2. Stage Objectives

Stage 5 will deliver:

1. A written interaction-data contract covering source, authority, purpose,
   cutoff, consent, retention, deletion, label eligibility, catalog identity,
   provenance, and limitations.
2. A read-only suitability command that reports aggregate cohort, label, user,
   item, sparsity, support, and exclusion counts without fitting a model or
   exposing an identity.
3. A separate affirmative data-contribution boundary, or an explicit decision
   to keep non-fixture collaborative training disabled when that boundary is
   absent.
4. A canonical database-time snapshot query using one repeatable-read,
   read-only transaction and an as-of-cutoff interpretation of temporal rows.
5. A frozen positive-label policy that never converts unknown, viewed,
   wishlisted, played, disliked, or recommendation-event rows into implicit
   positives.
6. A project-authored deterministic interaction fixture, isolated from real
   data and labeled only as functional test input.
7. A sparse binary user-item representation with bounded eligibility,
   cardinality, memory, and neighborhood limits.
8. An explainable item-item cosine baseline with overlap support, self-edge
   removal, deterministic pruning, fixed numeric policy, and stable tie-breaks.
9. A collaborative artifact contract with model/schema/code identity, catalog
   and interaction fingerprints, provenance, cutoff, consent policy, data
   revision, validity horizon, aggregate counts, checksums, and resource caps.
10. Immutable build, validate, activate, rollback, invalidate, and retire
    behavior separate from the Stage 3 content artifact lifecycle.
11. A pure collaborative scorer that consumes only stable game slugs and
    bounded source context, never a user ID, credential, database session, or
    mutable model object.
12. Honest cold-start behavior for unsupported users, sources, items, catalogs,
    or datasets, with no fabricated collaborative score.
13. A versioned hybrid policy that combines independently exposed content,
    feedback-affinity, collaborative, platform, popularity, and played
    components before final top-K truncation.
14. Exact Stage 4 score and order preservation whenever the collaborative
    component is absent, invalid, stale, unsupported, or gated off.
15. Candidate union and exclusion rules that can admit supported
    collaborative candidates while retaining selected-source exclusion,
    dislike exclusion, and played adjustment semantics.
16. Fixed-point component contributions and ordering evidence from which every
    returned hybrid score can be reconstructed.
17. Component-level readiness that distinguishes the required content model
    from the optional collaborative capability without taking content serving
    down.
18. A backward-compatible stateless endpoint and an explicitly evolved saved
    personalized response, event schema, and OpenAPI contract.
19. Bounded Stage 5 recommendation-generation events that record exact model,
    data, policy, mode, and fallback identity without becoming training labels.
20. An accessible browser presentation that preserves server order, identifies
    aggregate-interaction evidence only when it was applied, and explains
    fallback without implying quality or social proof.
21. Explicit Docker and direct command workflows; no request, startup,
    migration, seed, or broad test command may train or silently rebuild.
22. ML, API, PostgreSQL, web, browser, accessibility, OpenAPI, Docker,
    dependency, privacy, lifecycle, and complete Stage 1–4 regression gates.
23. A deterministic fixture comparison showing how popularity, content,
    feedback, collaborative, and hybrid candidates/components differ on
    hand-calculated scenarios, explicitly without a quality conclusion.
24. A Stage 6 handoff containing reproducible artifacts, exact component
    semantics, limitations, and evaluation-ready interfaces without reporting
    unearned quality conclusions.

## 3. Non-Goals

The following work is intentionally excluded from Stage 5:

- Claiming that collaborative or hybrid ranking improves relevance,
  satisfaction, engagement, retention, or any user outcome.
- Formal Precision@K, Recall@K, Hit Rate@K, MAP@K, MRR, NDCG@K, catalog
  coverage, novelty, diversity, calibration, fairness, uplift, or statistical
  comparison. Those are Stage 6 deliverables.
- Treating local developer activity, the synthetic fixture, or the 30-game
  catalog as representative real-user behavior.
- Treating a recommendation-generation event as an impression, click,
  conversion, exposure, preference, negative, or positive label.
- Converting missing interaction state into a negative preference.
- Treating `viewed`, `played`, or `wishlisted` alone as positive training
  evidence without a future evaluated policy change.
- User-user nearest-neighbor serving, matrix factorization, SVD, ALS, BPR,
  neural collaborative filtering, graph models, deep learning, embeddings, or
  LLM-based ranking.
- Online or per-request training, incremental mutation of a loaded artifact,
  background fitting, or automatic retraining on startup.
- Exploration, contextual bandits, reinforcement learning, diversity
  reranking, sponsored ranking, business-rule optimization, or A/B testing.
- External game metadata, cover images, remote APIs, or an undocumented public
  interaction dataset.
- Downloading a dataset as part of ordinary setup, tests, startup, or artifact
  loading.
- Browser-side candidate generation, scoring, filtering, reweighting, or
  reordering.
- Replacing or silently changing the Stage 3 stateless endpoint, content model
  identity, artifact schema, or public ranking contract.
- Removing Stage 4 feedback evidence or collapsing it invisibly into a single
  opaque hybrid number.
- Making the optional collaborative artifact a prerequisite for catalog,
  content recommendations, saved feedback, or data deletion.
- Persisting raw credentials, token digests, internal user IDs, stable
  pseudonymous user keys, IP addresses, headers, or device fingerprints in a
  snapshot or artifact.
- Reusing expired, revoked, cleared, or deleted contributions in a new build,
  or continuing to serve an artifact that the lifecycle contract invalidates.
- Production schedulers, queues, caches, managed/external artifact-registry
  services, monitoring, alerting, CI/CD, or deployment automation; those
  remain Stage 7 concerns. The minimal PostgreSQL lineage tables required for
  Stage 5 privacy invalidation are not a production registry service.
- Inventing test counts, coverage, timings, artifact sizes, interaction counts,
  quality metrics, or completion evidence before the commands run.

## 4. Engineering Principles

### 4.1 Data Suitability Before Modeling

The first output is an audit with a machine-readable reason to proceed or stop.
An algorithm must not turn missing authority, ambiguous semantics, catalog
mismatch, or sparse coverage into an apparently valid model.

### 4.2 Separate Permission for a New Purpose

Saved personalization and contributing interactions to an aggregate offline
model are distinct purposes. The safe default is a separate affirmative,
versioned, withdrawable contribution choice. Existing Stage 4 consent does not
become training permission by inference.

### 4.3 Deletion and Retention Survive Derivation

The lifecycle applies after extraction. A change that removes or changes an
eligible label must invalidate affected live-data artifacts before another
personalized response can use them. If automatic invalidation and retirement
cannot be proven, only project-authored fixtures may activate collaborative
serving inside the guarded disposable test/E2E environment.

### 4.4 Explicit Labels and Honest Unknowns

Only a current saved `game` preference with positive server-owned weight,
explicit current like, or current rating meeting the frozen positive threshold
when no dislike overrides it is a positive. These sources collapse to one
binary edge. Dislikes are
exclusions or possible future negative evidence; everything else remains
unknown.

### 4.5 Baseline First

Item-item cosine over a binary implicit matrix is selected for inspectability,
small-data behavior, deterministic implementation, and useful evidence. More
complex models require Stage 6 evidence, not novelty.

### 4.6 Offline Build, Online Inference

Database extraction, fitting, validation, and promotion occur only through
explicit operator commands. The API loads immutable artifacts read-only and
performs bounded scoring only.

### 4.7 Deterministic and Reproducible Computation

The cutoff, canonical row ordering, label policy, filters, sparse operations,
dtype, quantization, pruning, checksums, and tie-breaks are part of the model
contract. Wall-clock time is injected or captured once from PostgreSQL.

### 4.8 Sparse and Bounded Operations

The pipeline must not materialize an unbounded dense user-item or item-item
matrix. Input rows, users, items, nonzeros, pair support, per-item neighbors,
artifact members, response evidence, and event payloads all have explicit caps.

### 4.9 Honest Cold Start and Capability State

Unsupported users, sources, items, and catalogs receive no invented
collaborative value. The response reports exact fallback state, and Stage 4
continues to work.

### 4.10 Independent Component Observability

Content, platform, popularity, feedback affinity, collaborative similarity,
and played adjustment retain separate raw scores, weights, contributions, and
identities. Ranking signals are not probabilities.

### 4.11 No Hidden Double Counting

Hybrid weights are applied once to named components. A Stage 4 pre-played score
must not be blended as an opaque unit and then count the same affinity again.

### 4.12 Identity Minimization

Internal user IDs may exist only transiently inside the guarded extractor to
group rows. The artifact contains item-level aggregates, opaque fingerprints,
and counts—not identity-bearing rows or stable user keys.

### 4.13 Stage 3 and Stage 4 Compatibility Is a Contract

The stateless route remains content-only and read-only. The saved route must be
bit-for-bit equivalent to Stage 4 when the collaborative gate is closed. All
previous migrations, tests, privacy behavior, and artifact loading remain valid.

### 4.14 No Quality Claim Without Stage 6 Evidence

Stage 5 proves contracts, determinism, lifecycle, integration, and fallback.
Only Stage 6 may define leakage-safe splits, metrics, uncertainty, and an
evidence-based comparison.

### 4.15 Incremental Delivery and Regression Safety

Governance precedes extraction; extraction precedes fitting; artifact
validation precedes serving; pure scoring precedes API changes; API contracts
precede UI activation. Every phase has an executable exit criterion.

## 5. Proposed Technical Decisions

These decisions are proposals to freeze in Phase 0. Section 21 must replace
them with exact as-built choices; unresolved values cannot become silent
defaults.

### 5.1 Stage 3 and Stage 4 Compatibility Boundary

- `POST /api/v1/recommendations` stays content-only, cookie-agnostic,
  request-scoped, read-only, and contract-compatible.
- `POST /api/v1/me/recommendations` is the only Stage 5 hybrid activation
  point. It retains one commit-acknowledged generation event per HTTP 200.
- Model `gamelens-content-tfidf/1.0.0`, artifact schema `1`, compatibility
  `stage-3-v1`, and feedback policy
  `gamelens-feedback-adjustment/1.0.0` remain unchanged.
- Stage 5 will add a separate artifact and policy rather than changing content
  files in place.

### 5.2 Interaction-Data Suitability and Provenance Gate

The implemented external-source preflight runs before any build and emits
machine-readable JSON or a human-readable summary. It records source kind,
manifest fingerprint, exact file identity and gzip shape, aggregate schema
quality, source-metadata alignment, candidate-profile fingerprint, matrix
density, support distributions, thresholds, limits, and typed gate states.
It has no database time, cutoff, consent policy, or data revision because it
does not query live GameLens data.

A future consent-qualified live audit must additionally record catalog
fingerprint, PostgreSQL time and cutoff, consent policy, data revision, and
eligible/excluded contributor and label counts by reason. It remains subject
to the transaction, lifecycle, and identity-minimization contracts below.

`ready_for_functional_build` means only that the pipeline has sufficient
approved support to construct a baseline. It does not mean the data is
representative or that recommendations are good. The UCSD report instead
exposes `source_level_support_passes`; its `ready_for_functional_build` and
`approved_training_eligibility` fields remain false. Live-data activation
requires approved consent and derived-data lifecycle gates. Project-authored
fixture activation is reported separately.

UCSD Steam Versions 1 and 2 are selected only for local read-only source
preflight. They are not selected or approved for ingestion, training,
artifact construction, or serving. The manifest records exact source URLs,
attribution to the UCSD McAuley Lab, retrieval date, checksums, and source
shape; it does not assert ownership or rights-holder status. The source page
requests citation, but citation is not a license grant and this repository
records no dataset license or redistribution grant. License/redistribution,
ingestion provenance, Stage 5 label authority, GameLens catalog mapping,
fixture activation, and live-data consent/lifecycle gates remain blocked.

### 5.3 Canonical Interaction Snapshot and Cutoff

The live extractor uses one PostgreSQL `REPEATABLE READ, READ ONLY`
transaction. Immediately after setting its mode, one initialization query
calls `pg_current_snapshot()` to pin MVCC visibility and captures
`clock_timestamp()` once as the inclusive cutoff. The helper completes both
operations before returning to extraction, closing the transaction-start/
first-snapshot race. Rows are interpreted as active at the cutoff when:

```text
occurred_at <= cutoff
and (superseded_at is null or superseded_at > cutoff)
```

An eligible contributor must have the approved contribution-consent version,
consent at or before the cutoff, no revocation at the cutoff, and expiry after
the cutoff. Game identity uses canonical stable slugs and the exact content
catalog fingerprint.

The extractor groups rows by internal user ID only in guarded memory, converts
each eligible contributor to a sorted tuple of positive stable game slugs, and
then sorts that multiset of tuples lexicographically. Identical profiles remain
repeated rows; their identity is irrelevant to the item-item counts. Ephemeral
zero-based cohort rows and the canonical fingerprint are therefore independent
of database user-ID allocation. Neither the grouping map nor internal IDs are
serialized. A live row-level snapshot is streamed through bounded build memory
and is not retained after success or failure; only the aggregate audit and
final item-level artifact may remain. Approved external or project-authored
fixture snapshots, if materialized for reproducible tests, stay ignored and
follow their documented source lifecycle.

### 5.4 Label Eligibility, Precedence, and Unknowns

The proposed version-1 training policy is binary:

| Current state at cutoff | Offline matrix value | Reason |
| --- | ---: | --- |
| Saved `game` preference with weight `> 0` | `1` | Explicit positive game selection |
| Explicit `liked` reaction | `1` | Direct positive feedback |
| No reaction and rating `>= 7` | `1` | Existing Stage 4 positive threshold |
| Explicit `disliked` reaction | absent | Overrides a rating; not a positive |
| Rating below `7` | absent | Not defined as a negative in version 1 |
| `viewed`, `played`, or `wishlisted` alone | absent | Meaning is too ambiguous |
| Recommendation event | absent | Generation audit record only |
| No row | absent | Unknown, not negative |

At most one positive exists for a contributor/game pair after source collapse,
reaction precedence, and deduplication. An active dislike dominates a saved
game preference or rating for the same game. Ratings and duplicate positive
sources are not magnitude-weighted in the first baseline. Superseded history
is used only to reconstruct state at the cutoff, never as repeated confidence.

### 5.5 Consent, Revision, Expiry, and Derived-Data Invalidation

Phase 0 should prefer a separate optional contribution-consent resource and
copy, default off, rather than forcing training permission to use saved
personalization. The database records its version and grant/withdrawal time;
the browser explains aggregate offline use and fallback.

A small PostgreSQL build-lineage registry records the artifact/build identity,
status, aggregate contributor count, and contributor membership. Membership
uses the existing internal user foreign key with `ON DELETE CASCADE`; it stays
inside PostgreSQL and never enters the artifact or response. A monotonic source
revision advances for relevant preference, interaction, consent, and lifecycle
mutations. The builder captures it with the snapshot and verifies it again
before promotion, preventing a mixed or already-obsolete build.

After promotion, a new positive recorded after the cutoff does not invalidate
an otherwise valid point-in-time artifact; the next explicit build may include
it. A transaction that removes or changes an edge contained in a live build,
withdraws contribution consent, revokes/deletes its contributor, or performs
eligible retention must mark every affected registered build invalid before it
commits. Contributor lineage makes that update targetable. Cascade/count and
eligibility checks remain defenses if the artifact file still exists.

A live-data artifact records its build ID, revision, expected contributor
count, and earliest contributor expiry. Runtime use requires:

- artifact revision equal to the matching registered build revision;
- one active matching readiness row with the expected contributor count and
  current invalidation epoch/status;
- current approved contribution-consent version;
- current time before the artifact validity horizon;
- exact catalog fingerprint and artifact compatibility;
- no explicit retirement marker.

A mismatch immediately disables only the collaborative component. Rebuild
from current eligible state is explicit. Obsolete live-data bundles must be
retired and removed according to the Phase 0 deletion decision before another
live artifact is promoted. If this end-to-end behavior cannot be implemented
and tested, live-data build and activation remain blocked while the synthetic
fixture path may still prove functionality.

### 5.6 Support Thresholds and Cold Start

Proposed functional defaults, to be frozen after the audit, are:

- at least two distinct positive items per eligible contributor;
- at least two eligible contributors per retained item;
- at least two co-positive contributors per retained item pair;
- at most 100 stored neighbors per item, capped at catalog size minus one;
- at least 10 retained contributors, 20 positive edges, and 5 retained items
  before a live-data artifact may report functional readiness.

These thresholds suppress one-person edges and degenerate rows; they are not
quality-tuned. The lower structural checks still protect the fitting function,
while the larger activation minima prevent a trivially tiny live cohort from
appearing ready. The build returns a typed `insufficient_data` result and no
promotable live artifact when either gate fails. Unsupported users or source
items fall back at request time without error. A deterministic test fixture may
be purpose-built to cross the functional gates, but remains non-quality data.

### 5.7 Collaborative Baseline

The first baseline is item-item collaborative filtering over a binary implicit
matrix `X` with users as rows and stable-slug games as columns. Item support is
the column sum, co-positive support is `X.T @ X`, and similarity is cosine:

```text
similarity(i, j) = co_positive(i, j) / sqrt(support(i) * support(j))
```

Self-similarity is removed. No mean-centering, confidence weighting, negative
sampling, latent factors, or learned hybrid weights are introduced. The model
describes co-positive interaction structure, not causal similarity or a
probability that a user will like a game.

### 5.8 Sparse Computation and Numeric Policy

`X` is canonical CSR with binary values. Pair computation uses sparse or
bounded-block multiplication and prunes support before materializing retained
neighbors; an unbounded dense catalog-square matrix is prohibited.

Build arithmetic uses a frozen float dtype and rejects NaN, infinity, negative
similarity, invalid indices, duplicates, and non-canonical CSR. Stored
similarities are quantized with the existing scale `1_000_000` and
round-half-up. Neighbor ordering is similarity units descending, overlap
support descending, then neighbor slug ascending.

Resource limits cover users, items, input nonzeros, retained neighbor nonzeros,
member count, member bytes, total bytes, and JSON depth. Exceeding a limit
fails safely before promotion.

### 5.9 Collaborative Artifact Contract

The proposed independent identity is model `gamelens-item-item-cosine`, version
`1.0.0`, artifact schema `1`, and code compatibility `stage-5-v1`. Exact names
remain Phase 0 decisions.

The transparent, non-pickle bundle should contain:

- a canonical `manifest.json`;
- stable item metadata and item support;
- canonical sparse neighbor indices;
- quantized similarity units and pair-overlap support;
- SHA-256 checksum and size metadata for every member.

The manifest includes source kind, model/schema/code identity, build software,
catalog fingerprint, interaction fingerprint, cutoff, consent policy, dataset
revision, validity horizon, label-policy identity, thresholds, matrix shape,
aggregate counts, numeric configuration, and artifact-member checksums. It
contains no user row, user ID, stable pseudonym, credential, preference
payload, or recommendation event.

Build writes a temporary sibling, validates it with the production loader,
then atomically promotes to a new immutable path. Validation never repairs or
overwrites a bundle. Activation and rollback are explicit configuration
changes.

### 5.10 Per-User Collaborative Candidate Scoring

The pure scorer receives a bounded ordered set of stable-slug query sources:
current positive feedback sources and saved positive game selections. Duplicate
slugs collapse with a documented precedence and the existing positive-source
recency cap remains bounded. Offline eligibility and online query-source
selection are separately versioned even when they currently share a signal.

For each candidate, the baseline aggregates available source-to-candidate
neighbor similarities with an equal-weight mean over usable sources, quantizes
once, and exposes the highest contributing source edges. Selected games,
positive feedback sources, and explicit dislikes are excluded from candidates.
An absent edge is missing collaborative support, not a zero-valued dislike.

The scorer returns candidates and evidence only. It does not know top-level
hybrid weights, played state, HTTP schemas, or user identity.

Hybrid orchestration forms the union of ordinary Stage 3/4 candidates and
collaborative neighbor slugs, then asks a new pure base materializer to score
those exact catalog rows. The materializer calculates the existing content,
platform, popularity, and optional feedback-affinity values but deliberately
does not apply the Stage 3 `content_units > 0` eligibility gate. A
collaborative-only candidate therefore has `candidate_origin=collaborative`,
content units of zero when appropriate, exact platform/popularity/base units,
and explicit empty content evidence. The existing `ContentRanker.rank()` and
Stage 4 public wrapper retain their current filter and behavior. The exact new
method name is a Phase 0 implementation decision.

### 5.11 Hybrid Component Gating, Weights, and Fallback

The proposed policy identity is `gamelens-hybrid-ranking/1.0.0`. Its initial
engineering weights are not learned and make no quality claim:

- feedback affinity receives `10%` when a valid Stage 4 positive profile
  exists;
- collaborative similarity receives `10%` when the artifact and user context
  provide support;
- the base Stage 3 score receives the remaining `80%`, `90%`, or `100%`.

Thus affinity-only behavior stays exactly `90/10`, as in Stage 4;
collaborative-only behavior is `90/10`; both active become `80/10/10`; and no
supplemental signal leaves the Stage 3 base at `100%`. Played adjustment is
applied once after these pre-played contributions. Dislikes remain hard
exclusions before ordering and top-K.

Supplemental gates and weights are chosen once per request, not independently
per candidate. When the request has usable collaborative support, a content
candidate with no retained source edge receives
`collaborative_supported=false`, raw/contribution units of zero, and the same
request-wide collaborative weight; its missing 10% is not reassigned to base.
This is an explicit absence of positive collaborative support, not a dislike
or a predicted negative probability. Stage 6 must measure the consequence
before changing this versioned policy.

The candidate pool is the union of Stage 3/4 content-supported candidates and
collaborative neighbors. A collaborative-only candidate may enter only when it
has a valid retained edge and passes all exclusions. If the collaborative
component is unavailable or supplies no supported candidates, the implementation
must invoke the existing Stage 4 behavior and preserve its scores, ordering,
reason, and evidence exactly.

### 5.12 Feedback Relationship and Double-Count Prevention

The hybrid policy consumes the Stage 3 base score and the Stage 4 affinity as
separate components, not the opaque Stage 4 pre-played score plus affinity a
second time. Positive feedback may legitimately serve as context for both
content affinity and collaborative edges, but each resulting signal has one
named contribution and one weight.

Stage 4 dislike precedence, positive-rating threshold, most-recent-source cap,
selected/source exclusion, played factor, and wishlist neutrality remain
unchanged unless Section 21 records an explicitly tested contract change.

### 5.13 Fixed-Point Ranking Evidence

Every item exposes base score and subcomponents, feedback-affinity score,
collaborative score, effective weights, fixed-point contributions, pre-played
score, played factor/delta, final score, policy identities, source edges, and
fallback mode. Contributions must sum exactly in integer units.

Proposed ordering is final score, pre-played score, base contribution,
collaborative contribution, affinity contribution, content score, popularity
score, then stable slug. Exact keys are frozen by golden tests in Phase 0.
Explanations are deterministic prose derived only from structured evidence and
must not say “users like you,” “popular with players,” or another unsupported
social or quality claim.

### 5.14 Readiness and Failure Semantics

The content component remains required for recommendation readiness. The
optional collaborative component reports one of:

- `not_configured`;
- `fixture_only`;
- `insufficient_data`;
- `unavailable` with a bounded reason;
- `stale` with catalog, revision, consent, expiry, or compatibility reason;
- `ready`.

`GET /api/v1/models/status` keeps existing fields and may add an optional
component block. A collaborative failure never changes a content-ready status
into total outage. The personalized response reports `stage_4_fallback` or
`hybrid` truthfully; it never returns an invented zero collaborative model.

### 5.15 Personalized Response and Event Contract

The saved response retains existing fields for compatibility and adds optional
hybrid-policy, collaborative-model, ranking-mode, fallback-reason, and
per-item collaborative evidence. The stateless response does not change.

A data-preserving migration may add all-or-none collaborative identity and
feedback/hybrid policy fields to `recommendation_events`, with a new
`stage-5-v1` constraint. Existing `legacy-v1` and `stage-4-v1` rows remain
valid. For Stage 5 rows:

- existing model columns continue to identify the content model;
- explicit fields identify feedback policy, hybrid policy, collaborative
  model, and interaction fingerprint when applied;
- request context records bounded mode and fallback reason;
- result summaries store compact fixed-point component units and support;
- no prose, raw state dump, identity, credential, or unbounded edge list is
  stored.

Events remain generation audit records and are excluded from every interaction
snapshot query by construction.

### 5.16 Browser and Product Behavior

The browser remains a renderer of server order and evidence. It may show an
“aggregate interaction signal” row only when the API applied it, with a short
description of what was and was not used. Fallback remains useful and should
not be presented as an error when content serving is ready.

If separate contribution consent is implemented, it is unchecked by default,
independent from saved personalization, keyboard operable, versioned, and
withdrawable. Copy must explain that withdrawal stops future eligible builds
and triggers the documented artifact invalidation path. Loading, stale,
unsupported, failure, consent, withdrawal, and clear-data states require
visible text and accessible announcements.

### 5.17 Docker, Commands, and Branch Topology

The existing content model profile and commands keep their meaning. Stage 5
adds separate collaborative audit/build/validate operations, a separate
artifact path, and a disposable fixture path. The API mounts both configured
artifacts read-only. No request or service startup fits either model.

Development and E2E builds use new immutable disposable paths. Lifecycle tests
may delete only guarded disposable artifacts and databases. Production
scheduling and managed/external artifact registry services remain Stage 7
work; the minimal Stage 5 PostgreSQL build-lineage rows are part of the privacy
contract.

An artifact with `source_kind=fixture` is loadable only when
`ENVIRONMENT=test` and an explicit test-only fixture flag are both present.
Development and production reject it with `fixture_not_allowed`; no ordinary
user-facing response may present synthetic co-occurrence as an aggregate
interaction signal.

## 6. Target Repository Structure

Phase 0–3 names marked `(+ implemented)` are as built. Later-phase illustrative
entries remain `(+ planned)`; generated snapshots and artifacts remain ignored.

```text
.
|-- apps/
|   |-- api/
|   |   |-- alembic/versions/
|   |   |   `-- 0006_stage_5_collaborative_contract.py  (+ implemented)
|   |   |-- app/
|   |   |   |-- commands/
|   |   |   |   |-- collaborative_snapshot.py          (+ implemented)
|   |   |   |   `-- collaborative_artifact.py          (+ implemented)
|   |   |   |-- repositories/
|   |   |   |   `-- collaborative_snapshot.py          (+ implemented)
|   |   |   |-- services/
|   |   |   |   |-- collaborative_snapshot.py          (+ implemented)
|   |   |   |   `-- hybrid_recommendation.py            (+ planned)
|   |   |   `-- schemas/
|   |   |       `-- collaborative.py                    (+ planned)
|   |   `-- tests/                                      (* changed)
|   `-- web/
|       |-- src/features/recommendations/               (* changed)
|       `-- e2e/                                        (* changed)
|-- data/
|   |-- catalog/games.json                              (existing)
|   |-- external/ucsd-steam/                            (metadata/audit only)
|   |-- fixtures/interactions/
|   |   `-- collaborative-interactions.json             (+ implemented test fixture)
|   `-- generated/                                      (ignored generated)
|-- docs/
|   `-- stage-5-collaborative-hybrid-ranking-plan.md
|-- infra/
|   |-- docker-compose.test.yml                         (* changed)
|   `-- docker-compose.e2e.yml                          (* changed)
|-- ml/
|   |-- artifacts/
|   |   `-- collaborative/                              (ignored generated)
|   |-- src/gamelens_recommender/
|   |   |-- interaction_snapshot.py                     (+ implemented)
|   |   |-- collaborative_artifacts.py                  (+ implemented)
|   |   |-- collaborative_training.py                   (+ implemented)
|   |   |-- collaborative.py                            (+ implemented)
|   |   `-- hybrid.py                                   (+ planned)
|   `-- tests/
|       `-- test_phase3_handoff.py                      (+ implemented)
|-- .env.example                                        (* changed)
|-- docker-compose.yml                                  (* changed)
`-- Makefile                                            (* changed)
```

The SQLAlchemy repository owns consent-aware PostgreSQL extraction. The ML
package owns canonical interaction schemas after extraction, sparse fitting,
artifact validation, pure scoring, and hybrid math. API services own
transaction boundaries and HTTP mapping. The browser owns presentation only.

## 7. Implementation Phase 0: Preflight, Data Suitability, and Contract Baseline

### Objective

Freeze the legal/product/data boundary and demonstrate whether any non-fixture
interaction cohort is eligible before schema or model work begins.

### Work

1. Re-run every Stage 1–4 gate and record the clean baseline.
2. Inventory consent copy, temporal interaction semantics, retention, clear
   data, event meanings, catalog identity, current artifact, and configuration.
3. Review whether offline aggregate training is an authorized purpose. Default
   to a separate optional contribution consent if authority is not explicit.
4. Define the live-data invalidation, expiry, withdrawal, rebuild, retirement,
   and physical deletion contract.
5. Freeze proposed label precedence, thresholds, matrix limits, numeric policy,
   model/artifact/policy identities, response fields, event fields, and errors.
6. Design a read-only audit query and machine-readable report before fitting.
7. Specify the project-authored fixture separately from live data, including
   expected edges, cold-start cases, and explicit non-quality disclaimer.
8. Record whether any new dependency is necessary; prefer current NumPy, SciPy,
   scikit-learn, SQLAlchemy, and standard-library capabilities.

### Verification

- A reviewed contract answers who may contribute, which rows are labels, when
  they expire, what invalidates an artifact, and what happens after withdrawal.
- The audit design cannot read recommendation events as labels or emit an
  identity.
- Every proposed default has a named test and owner.
- A decision to postpone live-data activation is represented as a supported
  state, not treated as a failure to complete the functional pipeline.

### Exit Criteria

- Stage 1–4 regression evidence is green.
- Data authority and derived-data deletion have an implementable decision.
- Exact contracts and limits are frozen or explicitly block the next phase.

## 8. Implementation Phase 1: Canonical Interaction Snapshot and Provenance

### Objective

Extract one deterministic, privacy-minimized, as-of-cutoff interaction view and
produce an honest suitability result.

### Work

1. Add any approved consent, build-lineage, contributor-lineage, and monotonic
   dataset-revision migration with a populated upgrade, downgrade, constraint,
   cascade, and concurrency plan.
2. Implement the repository query in one database-time repeatable-read,
   read-only transaction.
3. Apply contributor eligibility, temporal-as-of state, reaction precedence,
   positive-rating threshold, deduplication, and stable game identity.
4. Stream canonical triples to the ML boundary while keeping internal IDs and
   cohort-row mapping transient.
5. Compute aggregate audit distributions and canonical interaction fingerprint
   with fixed serialization.
6. Return typed reasons for no contributors, no multi-positive users,
   unsupported items, no supported pairs, catalog mismatch, revision race, or
   unapproved live source.
7. Add and validate the separate deterministic synthetic interaction fixture.
8. Remove every temporary live row-level input on both success and failure;
   retain only aggregate audit output, lineage, and the validated item artifact.

### Verification

- Reordered database rows or different internal ID allocation for the same
  multiset of positive profiles produce the same fingerprint and matrix.
- Superseded, disliked, expired, revoked, non-contributing, post-cutoff, and
  deleted state is excluded by tests.
- Recommendation events, views, played-only, wishlist-only, taxonomy
  preferences, and non-game preferences never appear as offline positives;
  saved positive `game` preferences follow the explicit versioned label rule.
- Audit output contains bounded aggregates and no user ID, token material, raw
  per-user row, or credential; identity-bearing lineage remains only in the
  protected relational database.
- Success, refusal, and injected build failure leave no live row-level snapshot
  or cohort mapping on disk.
- Concurrent feedback mutation either precedes or follows the captured
  snapshot; it cannot produce a mixed revision.

### Exit Criteria

- The extractor and audit report are deterministic and privacy-reviewed.
- The fixture has exact expected labels and exclusion reasons.
- Live-data build remains gated unless authority, revision, and lifecycle are
  all valid.

### Verified Phase 0–1 External-Source Slice (2026-08-23)

The following bounded slice is implemented and verified:

- `gamelens_recommender.ucsd_steam` provides read-only `verify`, `prepare`,
  and `audit` commands plus JSON and summary output. Expected blocked
  integration is a successful command state; malformed, missing, mismatched,
  unsafe, or over-limit input exits with a typed error.
- The implementation uses only the Python 3.12 standard library. It verifies
  all three compressed members before parsing, rejects symlinks/path escape,
  bounds each exact compressed read, caps a line at 2 MiB and each expanded
  member at 2 GB, uses bounded `ast.literal_eval` rather than `eval`, and
  rechecks all compressed identities after scanning or parsing.
- Manifest schema 1 freezes exact compressed/expanded sizes, SHA-256 values,
  line counts, maximum line sizes, fail-closed gate states, and source status
  `local-raw-sources-verified-not-integrated`. Its canonical SHA-256 is
  `a55b2b2cc5b96a04bb58f29e789cc80467997128da6f73e806a56000585095ca`.
- Preparation policy `ucsd-steam-review-recommend-preparation-v1` treats only
  source-native `recommend=true` as a candidate, collapses duplicate
  user/item pairs, excludes conflicts, ownership, playtime, and false reviews,
  and performs only unambiguous v1-to-v2 source metadata alignment. This is
  not an approved Stage 5 label or a GameLens catalog mapping.
- The canonical candidate fingerprint hashes the sorted multiset of sorted
  source-item profiles without serializing a source user key. The verified
  fingerprint is
  `eafce3dcdd6cde57ec5eacf1746b83f0a3e269c0fc9069b2da2bf5d78ecd9f66`.
- The verified audit contains 59,305 review rows, 58,431 deduplicated
  user/item pairs, 51,692 unambiguous true candidate pairs, and 47,492 pairs
  aligned to one unambiguous v2 metadata ID. Three deterministic queue-based
  bipartite fixed-point passes leave 9,792 profiles, 33,049 edges, 1,516
  items, and 6,481 item pairs with support of at least two. These are
  structural diagnostics only.
- The aggregate report emits no source user identifier or row-level snapshot,
  writes no processed data, and fits no model. Thirty-five focused UCSD cases
  and all 105 ML tests pass. Focused coverage includes exact verification,
  fail-before-parse and post-parse checks, bounded reads, safe literal and gzip
  errors, aggregate-only output, duplicate/conflict policy, canonical
  fingerprints, fixed-point pruning, ambiguous metadata, insufficiency
  reasons, fail-closed gates, and strict CLI/report semantics.
- A fresh full-source `audit --check-report` run matches the committed JSON by
  canonical JSON type and value.

The external-source slice alone does not authorize ingestion and remains
independent from the first-party interaction path below.

### Verified Phase 0–1 First-Party Interaction Foundation (2026-08-24)

- Migration file `0006_stage_5_collaborative_contract.py` advances the schema
  head to `0006_stage_5_collab_contract`. It adds one optional, versioned
  contribution-consent row per user and one monotonic singleton data revision.
  The populated upgrade grants no consent to existing users.
- Statement triggers advance the revision after mutations to users,
  contribution consent, preferences, interactions, catalog rows, taxonomies,
  and catalog associations. Recommendation events are deliberately not a
  revision source and are never queried as labels.
- User deletion cascades the contribution-consent row and existing user-owned
  source state; the source mutation advances the revision. Phase 0–1 writes no
  live row snapshot or artifact, so there is no derived file to delete.
  Any Phase 2 promotion must compare the captured revision and add protected
  build/contributor lineage before a bundle can become serveable.
- The live extractor requires PostgreSQL, establishes one `REPEATABLE READ,
  READ ONLY` transaction, pins `pg_current_snapshot()`, and captures one
  `clock_timestamp()` cutoff before returning to extraction. It applies
  consent/expiry/revocation/withdrawal and as-of temporal filters, uses the
  exact current content-catalog fingerprint, groups only transient internal
  IDs, and returns sorted stable-slug profiles with aggregate exclusions.
  Preference/interaction queries join one reusable eligible-user subquery and
  stream 1,000 rows per batch without per-user bind expansion.
- Label policy `gamelens-collaborative-labels/1.0.0` freezes dislike dominance,
  active likes, ratings of at least 7, and saved positive game preferences.
  Low ratings, viewed/played/wishlist-only state, superseded and post-cutoff
  rows, non-game preferences, ineligible contributors, and recommendation
  events are absent from positives.
- Canonical profile serialization retains the sorted profile multiset and
  hashes it with the label-policy identity. The bounded audit emits only
  aggregates, typed insufficiency/refusal errors, the exact catalog and
  interaction fingerprints, cutoff, and revision; no ID or cohort mapping is
  written.
- The strict project-authored fixture contains 12 synthetic profiles,
  36 expected positives, 6 supported items, explicit exclusions, and cold-start
  cases. It is accepted only with `ENVIRONMENT=test` plus
  `COLLABORATIVE_ALLOW_TEST_FIXTURE=true`. Its read is capped at 1,000,000 bytes,
  and duplicate/unrecognized keys, non-finite constants, and JSON type aliases
  fail closed. It passes functional thresholds but
  explicitly remains non-representative and non-quality evidence.
- `COLLABORATIVE_LIVE_DATA_ENABLED=false` and an unset contribution-consent
  version are the defaults. `make collaborative-audit` returns
  `integration_blocked` without creating a database engine. No Phase 0–1
  command builds, promotes, loads, or serves a collaborative artifact.
- Verification passes 193 fast API tests, 105 ML tests, 54 disposable-
  PostgreSQL tests, 76 web tests, the 38-case exact-host browser matrix, all
  three Compose configurations, Ruff over 124 Python files, OpenAPI drift, and
  the exact full-source UCSD report comparison.

The Phase 0–1 exit criteria are satisfied for the bounded audit and
ingestion-preparation foundation. Live training and serving remain intentionally
blocked: product consent copy/routes and Phase 2 build/contributor lineage,
artifact invalidation horizon, validation, promotion, retirement, and serving
gates do not yet exist.

## 9. Implementation Phase 2: Collaborative Artifact and Offline Builder

**Implementation status:** Complete for the guarded fixture/offline artifact
scope and verified 2026-08-25. Protected live lineage and serving remain later
phases.

### Objective

Fit, serialize, validate, and inspect the bounded item-item cosine artifact
without introducing identity or opaque executable serialization.

### Work

1. Build canonical binary CSR from eligible triples and validate shape,
   indices, duplicates, values, and resource limits.
2. Apply user, item, and pair support thresholds in a documented order.
3. Compute cosine similarity with sparse/bounded operations, remove self-edges,
   quantize, sort, and prune neighborhoods deterministically.
4. Serialize manifest, item/support metadata, sparse neighbors, similarity
   units, and pair support without pickle.
5. Add complete member checksums, exact member set, schema/code identity,
   aggregate diagnostics, build/lineage identity, data revision, consent
   policy, and validity horizon.
6. Validate a temporary sibling with the production loader before atomic
   promotion to an unused immutable path.
7. Add inspection output that reports artifact identity and aggregates without
   exposing interaction rows.

### Verification

- A hand-calculated tiny fixture matches every support, cosine, quantized unit,
  retained edge, and tie-break.
- Reordered equivalent input produces identical semantic members and
  fingerprint.
- Corruption, extra/missing member, traversal, wrong dtype/shape, non-finite
  value, invalid CSR, resource excess, stale revision, expired validity, and
  catalog mismatch fail with bounded reason codes.
- Artifact scans find no internal ID, credential, user row, or stable user key.

### Exit Criteria

- Build, validate, inspect, and failure paths are deterministic.
- The loader returns immutable validated arrays.
- No unvalidated or lifecycle-invalid bundle can be promoted or served.

## 10. Implementation Phase 3: Pure Collaborative Candidate Scoring

**Implementation status:** Complete for the ML-only scorer/materialization
boundary and verified 2026-08-28. Hybrid policy, API orchestration, lifecycle
readiness, response/event fields, and UI activation remain later phases.

### Objective

Convert bounded source-game context and the validated artifact into
deterministic collaborative candidates and reconstructible evidence. Deliver
the work as independently testable slices so source selection, CSR lookup,
aggregation, exclusions, and Stage 3/4 materialization regressions can be
isolated without involving HTTP, PostgreSQL, lifecycle readiness, or hybrid
weights.

### Phase Boundary and Dependency Order

Phase 3 is an ML-package boundary only. It receives an already validated
`LoadedCollaborativeArtifact`, stable game slugs, and immutable source/exclusion
state. It does not load a path, inspect consent, query a database, know a user
identity, choose a serving fallback, apply hybrid or played weights, truncate to
request top-K, map an API response, or write an event.

The implementation is split along the following dependency graph:

```text
3A contracts and characterization goldens
 |-- 3B query-source canonicalization -> 3C CSR edge lookup -> 3D pure scorer
 `-- 3E exact-row base materializer -> 3F exact-row affinity materializer
                                      \
                         3D + 3F -> 3G ML-only handoff and hardening
```

After 3A, the scoring branch (3B–3D) and materialization branch (3E–3F) may be
implemented in parallel. Work within each branch remains sequential. Phase 4
may not start until 3G passes, and no slice may hide a failing earlier-slice
test behind orchestration fallback.

### Completed Slice Record

| Slice | Implemented boundary | Commit |
| --- | --- | --- |
| 3A | Frozen scoring contracts and Stage 3/4 characterization goldens | `73b4528` |
| 3B | Canonical immutable query-source selection | `7a57dcd` |
| 3C | Bounded sparse CSR neighborhood lookup | `5e25a64` |
| 3D | Pure aggregation, exclusions, evidence, diagnostics, and typed outcomes | `844c695` |
| 3E | Exact-row base/content/platform/popularity materialization | `a5b755c` |
| 3F | Exact-row feedback-affinity materialization | `d0b6676` |
| 3G | Public handoff boundary, end-to-end fixture trace, and hardening | `fa0ebd0` |

The final focused Phase 3 regression set passes 154 tests. The complete ML
suite passes 256 tests with one symbolic-link capability skip on the current
Windows host. Ruff lint, Ruff format check, privacy-string review, mutation and
permutation cases, resource bounds, and `git diff --check` pass. No dependency,
artifact format, API, database, event, response, fallback, or UI contract
changed in Phase 3.

### As-Built Contract Freeze from Slice 3A

Slice 3A adopted the following contract. These values are explicit production
defaults protected by the Phase 3 tests rather than incidental behavior:

1. Query-source kinds are `liked`, `rating`, and `saved_game`. Active dislikes
   remove a slug from every source kind and remain candidate exclusions.
2. Duplicate-source precedence is dislike, then liked, then qualifying rating,
   then saved game. Positive feedback is ordered by occurrence time descending
   and slug ascending, preserving the existing most-recent-five limit. Saved
   games have no runtime recency contract, are ordered by slug, and retain the
   existing five-game limit. After cross-kind collapse, the total scorer input
   is therefore bounded by ten sources.
3. A source absent from the artifact item axis is unsupported. A retained
   source row with no neighbor edges is supported but has no edge. Neither case
   fabricates a zero-similarity edge.
4. A candidate score is the round-half-up integer mean of all available stored
   `similarity_units` from supported query sources. The calculation uses integer
   or `Decimal` arithmetic only; it never converts stored units back through a
   binary float. Missing edges are absent from both numerator and denominator.
5. Every contributing edge is returned because the source count is already
   bounded. Edge evidence is ordered by similarity units descending, pair
   support descending, then source slug ascending. This preserves exact score
   reconstruction and avoids a separate lossy evidence cap; Phase 6 may present
   a smaller display-only subset without changing scorer evidence.
6. Query-source candidates are excluded first, then explicit dislikes. The
   scorer does not apply content eligibility, played state, wishlist state,
   hybrid weights, or top-K.
7. Candidate ordering is collaborative score units descending, then stable slug
   ascending. Artifact row/index order is never an ordering contract. With at
   most ten sources and one hundred retained neighbors per source, visited
   edges and returned candidates are each bounded by 1,000 before deduplication
   and exclusions.
8. Expected support outcomes are typed result reasons:
   `recommendations`, `no_query_sources`, `no_supported_sources`,
   `no_candidate_edges`, and `no_eligible_candidates`. Invalid input or an
   incompatible supposedly validated artifact is a typed contract error and
   returns no partial candidates. The scorer never performs fallback itself.
9. Frozen output records include canonical query sources, supported and
   unsupported source slugs, each candidate's score and item support, every
   contributing source edge with pair support, and bounded aggregate counters
   for sources, visited edges, candidates before exclusions, exclusions, and
   returned candidates. They contain no timestamp beyond what source selection
   needs, user/cohort identity, mutable array/view, prose, or HTTP field.

The implemented production records are `CollaborativeQuerySource`,
`CollaborativeSourceEdge`, `CollaborativeCandidateScore`,
`CollaborativeScoringDiagnostics`, and `CollaborativeScoringResult`, colocated
with the scorer in `ml/src/gamelens_recommender/collaborative.py`. Slice 3A
froze these names together with their field meaning, bounds, reason taxonomy,
numeric policy, and ordering before 3B.

### Slice 3A: Contracts, Characterization, and Test Harness

#### Work

1. Add frozen input/output/config types and one typed scorer-contract error.
   Validate tuple ownership, canonical slugs, source kinds, timezone-aware
   feedback timestamps, integer bounds, and configuration identity before any
   sparse traversal.
2. Add a tiny hand-authored immutable neighborhood fixture whose row pointers,
   neighbor indices, similarities, and pair supports are independent of the
   trainer. Keep a second test path that uses the real Phase 2 fixture bundle.
3. Record characterization goldens for the unchanged
   `ContentRanker.score_candidates()`, `ContentRanker.rank()`, and
   `FeedbackRanker.rank()` paths before refactoring them.
4. Map each contract field and reason to a focused test name so later failures
   identify the owning slice.

#### Checkpoint

- Schema/config tests and Stage 3/4 characterization tests pass with no scorer
  algorithm, API change, artifact-format change, or new dependency.
- The hand-authored fixture catches CSR off-by-one and ordering bugs without
  relying on the fitting code to reproduce the same mistake.

### Slice 3B: Query-Source Canonicalization

#### Work

1. Implement one pure source-selection function over immutable positive
   feedback sources, saved-game slugs, and disliked slugs.
2. Apply precedence, recency, per-kind caps, cross-kind deduplication, and the
   final stable order exactly once. The scorer consumes this canonical result
   rather than reimplementing source policy.
3. Preserve the existing Stage 4 liked/rating semantics; extracting a reusable
   helper may not change `FeedbackRanker.rank()` output.

#### Focused Verification

- Permutations and duplicate representations produce the same canonical tuple.
- Equal timestamps use slug ordering; timezone offsets representing the same
  instant compare consistently.
- Dislike precedence, liked-over-rating, feedback-over-saved, five-plus-five
  caps, empty input, invalid slugs/types/timestamps, and input immutability are
  covered without loading an artifact.

#### Checkpoint

- Given only input source state, a failure can be diagnosed without CSR or
  ranking code, and every downstream test uses the same canonicalizer.

### Slice 3C: Sparse Neighborhood Lookup

#### Work

1. Resolve each supported source through `slug_to_index`, slice exactly one CSR
   row through `neighbor_indptr`, and copy the matching candidate slug,
   similarity units, pair support, and support metadata into frozen edge
   records.
2. Treat unsupported source and supported zero-degree row as different states.
3. Count visited edges before aggregation and assert the bound derived from the
   validated artifact's per-row neighbor limit. Do not build a dense item-item
   vector or depend on physical neighbor-index order.

#### Focused Verification

- First, middle, last, and empty CSR rows return the exact expected edges.
- Unsupported slugs perform no row read; index zero and final `indptr` boundary
  are covered explicitly.
- Edge similarity and pair-support values remain aligned after evidence sort.
- Repeated/interleaved calls cannot mutate artifact arrays, mappings, or
  returned results.

#### Checkpoint

- Raw edge lists and counters match the hand-authored fixture before any mean,
  exclusion, candidate ordering, or content materialization exists.

### Slice 3D: Aggregation, Exclusions, Evidence, and Typed Outcomes

#### Work

1. Add `CollaborativeScorer` over the 3B canonical sources and 3C edge stream.
   Aggregate candidate buckets in one bounded pass and finalize them only after
   all supported source rows have been visited.
2. Compute the fixed-point mean once from the full contributing-edge sum and
   count. Return all contributing edges in their explicit evidence order.
3. Exclude every canonical query source and dislike before return, apply the
   frozen candidate sort, and populate disjoint diagnostic counters using the
   documented source-before-dislike exclusion precedence.
4. Return the most specific no-support reason reached. Invalid contracts raise
   the typed error before traversal; expected sparsity returns a normal result.

#### Focused Verification

- Hand-calculated one-source, multi-source, missing-edge, half-unit rounding,
  equal-score, and pair-support-tie cases match exact integer units and order.
- Each score is reconstructed from every returned edge; no returned edge is
  non-contributing and no contributing edge is omitted.
- Permuted equivalent inputs, source-row order, and candidate discovery order
  produce equal results.
- A source cannot recommend itself, a dislike cannot re-enter through another
  source, and filtering happens before the result is handed to top-K logic.
- Empty sources, all-unsupported sources, zero-degree sources, all-excluded
  candidates, the 1,000-edge boundary, and one-over-limit input each reach the
  exact result reason or contract error.

#### Checkpoint

- The pure collaborative scorer is complete and testable using only the
  collaborative artifact. It has no import from API code, SQLAlchemy, content
  ranking, feedback blending, or hybrid policy.

### Slice 3E: Exact-Row Base Materialization

#### Work

1. Add a narrowly named `ContentRanker` entry point for a canonical bounded set
   of exact candidate slugs. Factor shared base-component calculation so the
   existing full-catalog path and the new exact-row path cannot drift.
2. Compute content similarity only for requested rows, plus the existing
   platform, popularity, and base units. Return a `BaseCandidateScore` even when
   content units are zero.
3. Keep the zero-content eligibility filter solely in the existing
   `score_candidates()`/`rank()` path. The exact-row method does not exclude,
   sort for final ranking, blend signals, or materialize prose.
4. Reject duplicate, noncanonical, oversized, or missing slugs with a typed
   incompatibility/contract error rather than returning fabricated components.

#### Focused Verification

- Materializing the ordinary content-supported slug set reproduces every
  existing base component exactly.
- A known zero-content row receives zero content evidence plus exact platform,
  popularity, and base units.
- Empty, one-row, last-row, mixed-support, unknown, duplicate, cap, and input-
  permutation cases are deterministic and bounded.
- Existing Stage 3 candidate membership, scores, order, evidence, reason, and
  public wrapper remain byte-for-byte/value-for-value equivalent to the 3A
  characterization goldens.

#### Checkpoint

- Collaborative-only catalog rows can be scored without weakening Stage 3
  eligibility and any regression is local to `ranking.py` tests.

### Slice 3F: Exact-Row Affinity Materialization

#### Work

1. Extract the existing positive-profile and affinity calculation behind one
   pure exact-slug helper owned by the feedback-ranking module. Reuse the 3B
   positive-source selection semantics rather than adding another precedence
   path.
2. Return raw affinity units and whether an affinity profile is active for each
   requested slug. Do not apply base/affinity weights, played adjustment,
   exclusions, final ordering, top-K, explanation prose, or hybrid logic.
3. Make the existing `FeedbackRanker.rank()` delegate to the shared calculation
   while preserving its public result and policy identity.

#### Focused Verification

- No positive profile returns inactive/zero affinity without inventing support.
- Liked, qualifying-rating, recency-cap, source exclusion, zero-affinity, and
  exact-row subset cases match the pre-refactor Stage 4 units.
- Existing Stage 4 items, scores, order, evidence, adjustment reasons, played
  behavior, wishlist neutrality, and result reasons remain exactly equal to the
  3A characterization goldens.

#### Checkpoint

- Base and affinity materialization can be debugged independently, and Phase 4
  will not need to reach into `FeedbackRanker.rank()` internals.

### Slice 3G: ML-Only Handoff and Hardening

#### Work

1. Add one integration test that builds and production-loads the Phase 2
   fixture artifact, selects sources, scores collaborative candidates, checks
   catalog-fingerprint compatibility with the content artifact, and
   materializes the resulting exact slugs through 3E and 3F.
2. Prove a collaborative-only candidate can reach the Phase 4 handoff with
   exact collaborative, content, platform, popularity, base, and affinity units
   plus explicit empty content evidence where appropriate. Phase 4, not the
   scorer, owns candidate-union origin, weights, played adjustment, final rank,
   and fallback.
3. Export only the stable public Phase 3 types/functions, document their
   complexity and purity boundary, and keep internal CSR helpers private.
4. Run mutation, permutation, privacy-string, resource-bound, full ML, Ruff,
   format, and Stage 1–4 regression gates. Record measured test evidence only
   after all gates pass.

#### Checkpoint

- One deterministic fixture trace can be followed from canonical query sources
  through exact CSR offsets, candidate sums/counts, exclusions, final
  collaborative order, and specified-row components without HTTP or fallback.
- `ml/src/gamelens_recommender/collaborative.py` has no dependency on content or
  feedback rankers; the integration test joins their outputs by stable slug.

### Debugging Ownership

| Symptom | Owning slice and first evidence to inspect |
| --- | --- |
| Wrong source present, missing, or capped | 3B canonical source tuple and precedence tests |
| Wrong neighbor, similarity, or pair support | 3C source index, `indptr` slice, and raw edge list |
| Wrong collaborative units, order, or exclusion | 3D edge sum/count, exclusion counters, and candidate golden |
| Existing content result changed | 3E Stage 3 characterization diff |
| Existing personalized result changed | 3F Stage 4 characterization diff |
| Collaborative-only slug cannot be joined | 3G catalog fingerprint and exact-row handoff test |

Pure code returns typed reasons and bounded counters but emits no log itself.
Later API orchestration may log only those aggregate fields. It must not dump
source lists, artifact arrays, interaction state, or user identity while
diagnosing a failure.

### Work

1. Complete slices 3A through 3G in dependency order and keep each checkpoint
   green before the next dependent slice starts.
2. Use parametrized/permutation property tests with the existing dependencies;
   do not add Hypothesis or another package solely for this phase.
3. Keep commits aligned to slice boundaries. Do not combine CSR aggregation,
   Stage 3/4 refactors, and Phase 4 hybrid math in one change.
4. Run the focused new scorer suite after 3B–3D, the existing recommender suite
   after 3E, the existing feedback suite after 3F, then the complete ML and
   lint/format gates at 3G.

### Verification

- Repeated and permuted equivalent source inputs return the same scores and
  order.
- Every score is recomputable from returned source edges.
- A source cannot recommend itself, and a dislike cannot re-enter through a
  second source.
- A collaborative-only candidate reaches the Phase 4 handoff with zero/empty
  content evidence where appropriate plus exact platform, popularity, base,
  affinity, and origin-ready membership; Phase 4 alone assigns union origin.
  The existing ranker wrappers remain unchanged.
- Empty/unsupported context returns a typed no-support result without mutating
  the artifact or falling back inside the scorer.
- Stored similarity units are never round-tripped through float, every sparse
  traversal and output is bounded, and a deterministic trace identifies which
  slice owns any mismatch.

### Exit Criteria

- The scorer is deterministic, bounded, identity-free, and independently
  testable.
- Candidate evidence is sufficient for the hybrid policy and response mapper.
- Exact-row base and affinity seams preserve all Stage 3/4 public behavior and
  permit zero-content collaborative candidates without changing eligibility.
- Focused Phase 3 tests, the complete ML suite, Ruff, format, privacy review,
  and all applicable Stage 1–4 regression gates pass with no new dependency.
- Phase 3 contains no API activation, lifecycle readiness, fallback, response,
  event, UI, or ranking-quality claim; those remain later phases.

## 11. Implementation Phase 4: Versioned Hybrid Ranking Policy

**Implementation status:** Not started. Phase 3 now supplies the stable scorer,
exact-row base, and exact-row affinity inputs required by this phase.

### Objective

Combine base, feedback, collaborative, and played signals once, transparently,
and with exact Stage 4 fallback.

### Work

1. Refactor the Stage 4 ranker only as needed to expose base and affinity
   candidates without changing its public `rank()` behavior.
2. Form the candidate union before final filtering and top-K truncation.
3. Apply active-component weights, fixed-point contributions, played factor,
   final score, and frozen tie-breaks.
4. Preserve selected/positive-source/dislike exclusions and wishlist neutrality.
5. Return explicit ranking mode, fallback reason, policy identities, raw
   components, contributions, and structured explanation facts.
6. Generate deterministic, cautious prose only from structured evidence.
7. Add golden equivalence tests against the unmodified Stage 4 wrapper when
   collaborative support is absent.
8. Produce a deterministic fixture comparison of baseline candidate sets,
   component units, ranks, and fallback mode; label it a functional diagnostic,
   not an offline quality evaluation.

### Verification

- No collaborative artifact, invalid artifact, stale artifact, unsupported
  user, and no-edge user each match Stage 4 items, scores, order, and evidence.
- Hybrid contributions sum exactly to pre-played units, and played delta sums
  exactly to final units.
- Collaborative-only candidates enter only through valid retained edges and
  cannot bypass exclusions.
- Tie cases resolve identically across runs and supported platforms.

### Exit Criteria

- The policy has a frozen identity and complete reconstructibility.
- Stage 3 and Stage 4 ranker golden tests remain unchanged and green.

## 12. Implementation Phase 5: Artifact Lifecycle, Readiness, and API Orchestration

### Objective

Load both artifacts safely, enforce collaborative privacy lineage at request
time, and keep content serving available through every optional-component
failure.

### Work

1. Add an optional collaborative artifact setting without changing
   `MODEL_ARTIFACT_PATH` or the existing content loader.
2. Load and validate the collaborative bundle once at service construction;
   do not hot-reload or mutate it.
3. Add content and collaborative component services behind explicit
   interfaces, then inject them into personalized orchestration.
4. Verify build identity, registry status, contributor count, consent policy,
   registered revision, invalidation epoch/status, catalog fingerprint, and
   validity horizon from one bounded readiness row in the same consistent
   database snapshot used for the personalized request. Do not scan all
   contributor rows on the request hot path.
5. Map missing, fixture-only, insufficient, corrupt, incompatible,
   privacy-invalid, expired, catalog-stale, and ready states to bounded codes.
6. Preserve the required content readiness contract and extend model status
   additively with optional component state.
7. Ensure an optional-component exception cannot produce a partial event,
   incorrect hybrid label, or total content outage.
8. Reject `source_kind=fixture` outside the guarded disposable test/E2E
   environment even when its files and checksums are otherwise valid.

### Verification

- Missing configuration and every bounded collaborative failure return exact
  Stage 4 personalized results with the documented mode and reason.
- Deleting a registered contributor, withdrawing contribution consent,
  removing/changing an included positive edge, advancing beyond validity, or
  changing the catalog invalidates collaborative use before the next committed
  response. A new post-cutoff positive remains future snapshot input rather
  than silently changing the loaded artifact.
- Repointing configuration to a retired artifact cannot bypass database
  lineage or revision checks.
- The stateless route never queries collaborative lineage or changes behavior.

### Exit Criteria

- Component readiness is truthful and independently observable.
- Privacy or artifact invalidation takes effect immediately at the serving
  boundary while Stage 4 remains available.

## 13. Implementation Phase 6: Response, Event, OpenAPI, and Product Integration

### Objective

Expose the hybrid contract through the saved endpoint, preserve generated
client ownership, and present evidence without overstating meaning.

### Work

1. Finalize additive personalized response schemas for mode, fallback,
   collaborative identity, support, source edges, weights, and contributions.
2. Add the data-preserving `stage-5-v1` recommendation-event migration and
   all-or-none identity constraints while retaining legacy row validity.
3. Map one ranking result to one bounded response and one compact event summary
   from the same fixed-point values.
4. Keep generation, insertion, commit, acknowledgement, and ambiguous-commit
   semantics identical to Stage 4.
5. Regenerate the OpenAPI document and project-owned browser types; prohibit
   handwritten parallel response interfaces.
6. Render ranking mode and conditional aggregate-interaction evidence while
   preserving API order.
7. If approved, add separate contribution-consent, re-consent, withdrawal,
   invalidation, and fallback copy with accessible controls and announcements.
8. Keep model fingerprints and database lineage details out of ordinary UI
   prose even when they remain available in technical API identity.

### Verification

- OpenAPI drift fails when server and generated browser contracts diverge.
- A hybrid HTTP 200 commits exactly one matching `stage-5-v1` event; every
  known pre-commit failure commits none; ambiguous acknowledgement is not
  reported as success.
- Fallback events record content/feedback identity, mode, and bounded reason
  without pretending that a collaborative model contributed.
- Response and event units reconstruct the same score and rank.
- Browser component tests prove no client-side sorting or score recomputation.
- Keyboard, focus, live-region, contrast, responsive, consent, withdrawal,
  fallback, loading, empty, and error states are usable.

### Exit Criteria

- API, event, OpenAPI, generated client, and UI describe the same versioned
  ranking decision.
- Collaborative language appears only when a real component contribution was
  applied.

## 14. Implementation Phase 7: Derived-Data Lifecycle and Safe Commands

### Objective

Make audit, build, activation, invalidation, retirement, and cleanup explicit,
reviewable operations with no hidden destructive side effect.

### Work

1. Implement separate `audit`, `build`, `validate`, and `inspect` subcommands
   with machine-readable output and stable exit codes.
2. Register a validated live-data build and its contributor lineage only
   through a deliberate promotion transaction.
3. Define crash recovery for the filesystem/registry boundary so neither an
   orphan registry row nor orphan bundle becomes serveable.
4. Mark affected builds invalid in the same transaction as label removal,
   consent withdrawal, revocation, or user deletion when application control
   exists; retain the cascade-maintained readiness state and source/build
   revision checks as defense in depth.
5. Add an artifact-retirement preview listing exact non-active paths and
   reasons without reading or displaying contributor identities.
6. Require a database/artifact-set fingerprint and explicit confirmation to
   remove obsolete bundles; protect the current configured content artifact,
   active collaborative artifact, repository root, and development database.
7. Prohibit lifecycle mutation from startup, migration, seed, broad tests, or
   ordinary Compose teardown.
8. Document manual rollback: only a still-valid, registered artifact may be
   selected; privacy-invalid history is never a rollback target.

### Verification

- Audit, validate, inspect, and preview are read-only and idempotent.
- Build refuses an existing target; validation never repairs a bundle.
- Promotion failure leaves no ready half-state, and retry has deterministic
  behavior.
- Preview/confirmation mismatch, path escape, active path, unregistered path,
  or non-disposable test target fails closed.
- Disposable tests prove withdrawal/deletion invalidation and confirmed
  cleanup without touching content artifacts or persistent development data.

### Exit Criteria

- Operators can explain and reproduce every artifact state transition.
- No invalidated live-data artifact can be served or silently resurrected.

## 15. Implementation Phase 8: Docker, Configuration, and Full-Stack Fixtures

### Objective

Exercise the complete collaborative/hybrid lifecycle in isolated containers
without making the normal development stack self-modifying.

### Work

1. Add documented optional configuration for the collaborative artifact path,
   limits, and frozen policy identities; keep secrets server-only.
2. Extend the model profile with explicit collaborative audit/build/validate
   commands rather than a continuously running trainer.
3. Mount the configured collaborative artifact read-only in the API and give
   only the one-shot builder a writable target.
4. Extend disposable PostgreSQL fixtures with a deterministic multi-user,
   current-consent interaction cohort that crosses functional thresholds.
5. Keep the project-authored fixture out of persistent development seeding and
   identify every generated user/interaction as test-only.
6. Build both artifacts in E2E setup, start the API after validation, and run
   hybrid, fallback, invalidation, re-consent, and clear-data browser paths.
7. Tear down only the isolated tmpfs database, network, containers, and
   disposable artifact volumes.
8. Validate development, PostgreSQL-test, and E2E Compose definitions and
   non-root ownership on supported Docker hosts.

### Verification

- Ordinary `docker compose up`, API startup, web startup, migration, and seed
  never fit or mutate an artifact.
- The E2E builder has no credential/token output and the API has no artifact
  write permission.
- Fixture and live-source modes cannot be confused through configuration.
- A fixture bundle loads only with `ENVIRONMENT=test` plus the explicit
  test-only flag and is rejected in development/production.
- E2E teardown leaves persistent development data and configured artifacts
  untouched.

### Exit Criteria

- A fresh disposable stack can build, validate, serve, invalidate, fall back,
  and tear down without manual database editing.
- All Compose files and non-root filesystem boundaries pass.

## 16. Implementation Phase 9: Test Matrix and Quality Gate

### Objective

Prove Stage 5 functional correctness, determinism, privacy, failure semantics,
and regression safety without performing Stage 6 quality evaluation.

### Work

1. Build focused suites for every contract below and keep fixtures small enough
   for exact expected values.
2. Run diagnostic coverage only to find untested branches; do not optimize for
   a number at the expense of behavior.
3. Run the complete Stage 1–4 matrix after the Stage 5 suites.
4. Record commands, versions, counts, coverage, durations, artifact diagnostics,
   platform, and limitations only from actual results.
5. Perform a final secret, identity, generated-file, fixture-provenance,
   dependency-license, vulnerability, and release-diff review.

### Snapshot and provenance suite

- Database-time cutoff, temporal state, reaction precedence, saved-game
  preference, rating threshold, source collapse, and stable canonical ordering.
- Current contribution consent, withdrawal, revocation, expiry, safety horizon,
  deletion, post-cutoff mutation, and dataset revision.
- Explicit proof that recommendation events, views, played-only,
  wishlist-only, and unknown rows are never positives.
- Aggregate-only audit, insufficiency reasons, catalog alignment, and no
  identity in output.

### Collaborative ML suite

- Hand-calculated binary CSR, item support, pair support, cosine,
  quantization, diagonal removal, threshold order, top-neighbor pruning, and
  stable ties.
- Empty, single-user, single-item, unsupported, duplicate, invalid, oversized,
  and non-finite inputs.
- Reproducible semantic artifact from equivalent canonical input.

### Hybrid-ranking suite

- Exact Stage 4 equivalence for every fallback reason.
- Positive/source/dislike exclusion before top-K, collaborative-only candidate
  union, active-component weights, played factor, wishlist neutrality, and
  fixed-point reconstruction.
- Cold user, cold source, cold item, mixed support, empty result, tie, and top-K
  boundaries.
- Request-wide missing-edge behavior and collaborative-only materialization
  with zero/empty content evidence and exact remaining base components.

### Artifact and lifecycle suite

- Exact members, checksums, dtypes, shapes, canonical CSR, limits, compatibility,
  catalog fingerprint, interaction fingerprint, build ID, revision, lineage,
  validity horizon, immutable arrays, and path safety.
- Missing, corrupt, extra, stale, retired, contributor-deleted, consent-invalid,
  and expired artifact rejection.
- Crash-safe promotion, read-only validation/preview, guarded cleanup, and
  valid-only rollback.

### API and PostgreSQL suite

- Populated upgrade/downgrade/re-upgrade, constraints, foreign-key cascades,
  revision concurrency, lineage count, transaction isolation, and catalog
  preservation.
- Additive model status, unchanged stateless response, personalized hybrid and
  fallback responses, typed errors, and one-event-per-committed-200 semantics.
- Component identity and fixed-point equality across response/event, plus
  bounded JSON shapes and retention compatibility.

### Frontend and browser suite

- Generated type ownership, server-order preservation, conditional evidence,
  neutral fallback, no unsupported social claim, stale-response cancellation,
  and safe errors.
- Separate consent/withdrawal when implemented, request-only opt-out,
  rehydration, expiry, invalidation, clear data, keyboard, focus, live regions,
  serious/critical axe checks, and responsive layouts.
- Chromium primary matrix and critical Firefox/WebKit paths through the real
  disposable stack.

### Cross-project suite

- Ruff lint/format, Python package integrity, strict TypeScript, ESLint,
  Prettier, production build, OpenAPI drift, npm and Python dependency checks,
  Compose validation, container runtime imports, non-root permissions, and
  complete Stage 1–4 regressions.
- Privacy scans for credentials, internal IDs, raw interactions, generated
  snapshots, artifact members, reports, browser traces, screenshots, coverage,
  caches, and environment files.

### Verification

- Every Section 19 acceptance item maps to at least one automated test or a
  named manual review with retained evidence.
- No test uses recommendation events as labels or reports ranking-quality
  metrics.
- The fixture comparison identifies behavioral/component differences without
  Precision/Recall/NDCG, tuning, or a superiority conclusion.
- Repeated deterministic runs produce the same semantic artifact and ordered
  results.
- Failure-path tests prove Stage 4 availability and event truth.

### Exit Criteria

- Stage 5 and all Stage 1–4 gates pass from documented clean commands.
- Remaining failures, platform gaps, or lifecycle uncertainty block completion
  rather than becoming undocumented exceptions.

## 17. Implementation Phase 10: Documentation and Release Preparation

### Objective

Make the implemented behavior reproducible, distinguish evidence from
limitations, and leave a precise Stage 6 input contract.

### Work

1. Update root, API, web, ML, infrastructure, data, architecture, data-model,
   recommendation-design, roadmap, environment, command, and plan documents.
2. Replace Section 21 proposals with exact as-built identities, thresholds,
   schemas, weights, commands, migrations, counts, and deviations.
3. Convert Section 22 from provisional to verified handoff and populate
   Section 23 only from passing evidence.
4. Document data source/provenance, consent authority, label limitations,
   lifecycle, artifact members, readiness states, fallback, rollback, and
   cleanup.
5. Record why fixture behavior and local diagnostics are not quality evidence.
6. Review dependency and data licenses and update attribution only for sources
   actually introduced.
7. Review the final diff for accidental implementation claims, generated
   outputs, credentials, user-derived rows, stale versions, and unsupported
   metrics.

### Verification

- A new contributor can audit/build/validate the fixture, start the stack,
  observe hybrid and fallback, and tear it down from documented commands.
- Every documented command and field exists; every planned-only item is still
  labeled planned.
- Completion evidence matches logs and does not extrapolate from synthetic
  data.

### Suggested Commit Structure

1. `docs: freeze stage 5 data and ranking contracts`
2. `feat(api): add contribution and collaborative lineage schema`
3. `feat(api): add canonical interaction snapshot audit`
4. `feat(ml): add collaborative artifact builder and loader`
5. `feat(ml): add collaborative scorer and hybrid policy`
6. `feat(api): orchestrate hybrid ranking and stage 5 events`
7. `feat(web): present consent and collaborative evidence`
8. `test: add disposable hybrid and lifecycle acceptance`
9. `docs: record stage 5 verification and stage 6 handoff`

### Exit Criteria

- Documentation is synchronized and the release diff is privacy-clean.
- Sections 21–23 contain only measured, verified facts.
- Stage 6 receives stable artifacts and interfaces, not a quality conclusion.

## 18. Command Interface Target

The external-source, Phase 0–1 audit, and guarded Phase 2 fixture-artifact
command names are frozen as implemented. Live build and artifact retirement
remain forward-looking until their lifecycle phases are implemented.

| Capability | Optional Make wrapper | Required direct equivalent |
| --- | --- | --- |
| Verify local UCSD source identity | `make ucsd-steam-verify` | `docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam verify --root /workspace --format json` |
| Profile UCSD ingestion preparation | `make ucsd-steam-prepare` | `docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam prepare --root /workspace --format json` |
| Audit UCSD source-level support | `make ucsd-steam-audit` | `docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam audit --root /workspace --format json` |
| Check committed UCSD aggregate report | `make ucsd-steam-audit-check` | `docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam audit --root /workspace --check-report data/external/ucsd-steam/suitability-audit.json --format summary` |
| Report the default-off live interaction gate or audit explicitly enabled eligible live data | `make collaborative-audit` | `python -m app.commands.collaborative_snapshot audit --source live --format json` |
| Audit the project-authored test fixture | `make collaborative-fixture-audit` | `ENVIRONMENT=test COLLABORATIVE_ALLOW_TEST_FIXTURE=true python -m app.commands.collaborative_snapshot audit --source fixture --format json` |
| Build a new guarded fixture bundle | `make collaborative-build` | `docker compose --profile quality run --build --rm --no-deps -e COLLABORATIVE_ALLOW_TEST_FIXTURE=true quality python -m app.commands.collaborative_artifact build --source fixture` |
| Validate the configured guarded fixture bundle | `make collaborative-validate` | `docker compose --profile quality run --rm --no-deps -e COLLABORATIVE_ALLOW_TEST_FIXTURE=true quality python -m app.commands.collaborative_artifact validate` |
| Inspect guarded fixture-bundle metadata | none required | `docker compose --profile quality run --rm --no-deps -e COLLABORATIVE_ALLOW_TEST_FIXTURE=true quality python -m app.commands.collaborative_artifact inspect` |
| Preview obsolete-bundle retirement | `make collaborative-retirement-preview` | `python -m app.commands.collaborative_artifact retire` without confirmation |
| Confirm disposable/obsolete cleanup | no broad wrapper | Same retire command with exact emitted confirmation |
| Build existing content artifact | `make model-build` | Existing `recommendation_artifact build` command |
| Validate existing content artifact | `make model-validate` | Existing `recommendation_artifact validate` command |
| Inspect component status | none required | `GET /api/v1/models/status` |
| Run focused ML tests | `make test-ml` | Existing documented pytest command |
| Run API and PostgreSQL gates | `make test`, `make test-integration` | Existing documented direct commands |
| Run web and browser gates | `make test-web`, `make test-web-e2e` | Existing documented npm/Compose commands |
| Validate all Compose files | `make config` | Existing direct `docker compose ... config --quiet` commands |

Existing command meanings must not change. No startup, request, migration,
seed, broad test, or teardown command may fit a model, install an unpinned
dependency, purge user data, retire an artifact, or silently rebuild a bundle.
Mutable commands require exact targets and fail safely on ambiguity.

## 19. Acceptance Criteria

Stage 5 is complete only when all applicable criteria below pass:

- All Stage 1–4 migrations, contracts, privacy behavior, commands, artifacts,
  fast tests, integration tests, web tests, browser tests, and Docker workflows
  remain green.
- `POST /api/v1/recommendations` remains cookie-agnostic, content-only,
  request-scoped, read-only, and contract-compatible.
- Data source, purpose, authority, cutoff, catalog mapping, consent,
  retention, deletion, provenance, and limitations are documented.
- Existing Stage 4 consent is not silently reused for aggregate training.
- Declining contribution does not create training eligibility; the documented
  request-only or saved-personalization fallback remains usable.
- The audit is read-only, aggregate-only, deterministic, bounded, and returns
  typed suitability reasons without fitting.
- Snapshot cutoff comes from PostgreSQL and one repeatable-read, read-only
  transaction.
- Temporal state, reaction precedence, rating threshold, saved positive game
  preference, and duplicate-source collapse match the frozen label policy.
- Unknown, viewed, played-only, wishlist-only, low-rating, disliked, and
  recommendation-event rows never become positive cosine edges.
- Recommendation events remain committed-generation audit records and are
  excluded from training by code, query, test, and documentation.
- Internal IDs and credentials remain outside snapshots, artifacts, logs,
  events, responses, browser state, reports, and committed fixtures.
- Live user label rows and ephemeral cohort mappings are not retained as a
  reusable snapshot file after build success or failure.
- Any identity-bearing contributor lineage stays protected in PostgreSQL and
  exists only to enforce lifecycle invalidation.
- Cleared, withdrawn, revoked, expired, or deleted contributions cannot enter
  a new build or continue through a serveable old artifact.
- Artifact/registry revision identity, bounded readiness/invalidation state,
  expected contributor count, consent version, validity horizon, and catalog
  fingerprint are checked before use without a per-request contributor scan;
  promotion also proves the source revision did not change during
  extraction/build.
- The deterministic fixture is explicitly project-authored, isolated from
  development data, and never presented as a real-user or quality dataset.
- A fixture artifact is serveable only in guarded disposable test/E2E mode and
  is rejected by ordinary development and production configuration.
- Structural and activation thresholds fail with `insufficient_data` rather
  than promoting a trivial live artifact.
- Fitting and serving use bounded sparse operations and never persist an
  unbounded dense user-item or item-item matrix.
- Hand-calculated item support, pair support, raw cosine, quantization,
  self-edge removal, pruning, and tie-breaks match implementation exactly.
- The artifact has exact model/schema/code identity, source kind, cutoff,
  catalog and interaction fingerprints, label policy, thresholds, build ID,
  revision, validity, aggregates, resource limits, and member checksums.
- Artifact files contain no executable pickle, user matrix, user row, user ID,
  stable pseudonym, credential, or raw interaction payload.
- Missing, corrupt, incompatible, oversized, stale, expired, privacy-invalid,
  retired, or catalog-mismatched bundles never become collaborative-ready.
- Build targets are immutable; validation is read-only; promotion is
  crash-safe; rollback accepts only a still-valid registered artifact.
- The collaborative scorer is pure, bounded, identity-free, deterministic,
  and excludes all source and disliked games.
- Unsupported users, sources, items, or pairs receive no fabricated
  collaborative score.
- Candidate union allows a valid collaborative-only candidate before
  exclusions and top-K.
- A collaborative-only candidate receives explicitly materialized
  content/platform/popularity/base/affinity evidence without weakening the
  existing Stage 3 zero-content eligibility contract.
- Hybrid weights are request-wide, versioned engineering defaults rather than
  learned or quality-optimized values.
- Under an active collaborative request, a candidate with no retained edge has
  unsupported/zero collaborative evidence and no candidate-level weight
  reallocation; this behavior is golden-tested and deferred to Stage 6 for
  evaluation.
- A reproducible fixture comparison records baseline candidates, components,
  and ranks while making no recommendation-quality claim.
- Base, platform, popularity, feedback affinity, collaborative, played, and
  final values remain independently observable and reconstructible.
- Each named signal is weighted once; component contributions sum exactly in
  fixed-point units.
- Played adjustment occurs once after the pre-played hybrid score, dislikes
  remain hard exclusions, and wishlist remains neutral.
- Every collaborative-unavailable or unsupported path matches Stage 4 scores,
  order, response reason, and evidence exactly.
- Content readiness survives optional collaborative failure, while model
  status and personalized output expose truthful mode and bounded reason.
- The saved response, `stage-5-v1` event, and generated browser type share the
  same model/data/policy identity and component units.
- Every commit-acknowledged personalized HTTP 200 has exactly one matching
  bounded event; known pre-commit failures have none; ambiguous commit
  acknowledgement is not returned as success.
- Event payloads contain no prose, credentials, identities, unbounded source
  lists, or state dump, and never become training labels.
- Browser code preserves server order and performs no ranking math.
- Collaborative explanation appears only for a positive applied contribution
  and makes no “users like you” or quality claim.
- Consent, withdrawal, fallback, loading, empty, failure, keyboard, focus,
  announcement, accessibility, and responsive states pass their gates.
- Commands have direct equivalents, immutable paths, stable exit behavior,
  read-only defaults where appropriate, and guarded destructive confirmation.
- Ordinary startup, request handling, migration, seed, tests, and teardown do
  not train, promote, retire, or delete artifacts or user data.
- Dependency locks, licenses, security checks, Compose validation, non-root
  execution, OpenAPI drift, privacy scan, and final release review pass.
- Documentation distinguishes current Stage 4 behavior, implemented Stage 5
  evidence, provisional policy defaults, and deferred Stage 6 evaluation.
- No Precision/Recall/NDCG or other formal quality result, superiority claim,
  real-user claim, invented count, timing, or artifact size appears without
  the appropriate later evidence.

## 20. Risks and Mitigations

**Risk:** The available cohort is too small, sparse, or unrepresentative.

**Mitigation:** Audit first, enforce structural and activation gates, support
`insufficient_data`, use the synthetic fixture only for function, and defer
quality conclusions to Stage 6.

**Risk:** The Stage 4 storage consent is misread as permission for aggregate
model training.

**Mitigation:** Require a reviewed separate affirmative contribution purpose,
version, copy, withdrawal path, and eligibility query; otherwise block live
training.

**Risk:** A deleted or withdrawn contributor continues to influence a loaded
artifact.

**Mitigation:** Combine source-revision validation at promotion, transactional
build invalidation, protected contributor lineage, validity horizon, bounded
runtime readiness checks, immediate fallback, explicit rebuild, and guarded
retirement.

**Risk:** Persisted lineage becomes a new identity leak.

**Mitigation:** Keep it inside access-controlled PostgreSQL with existing
internal IDs and cascade rules; exclude it from artifacts, logs, reports,
events, responses, and browser state.

**Risk:** Recommendation events are mistaken for impressions or positives.

**Mitigation:** Exclude the table at the repository boundary, assert that
exclusion in tests, and repeat its generation-only meaning in schemas and docs.

**Risk:** Rating, dislike, saved-selection, or superseded-state conflicts create
duplicate or contradictory edges.

**Mitigation:** Freeze as-of temporal semantics, dislike precedence, source
collapse, binary values, and one edge per contributor/game pair.

**Risk:** Pairwise similarity becomes quadratic and exhausts memory.

**Mitigation:** Use sparse/bounded-block computation, support pruning, hard
resource caps, deterministic top-neighbor retention, and fail before promotion.

**Risk:** A few co-occurrences are presented as strong social evidence.

**Mitigation:** Require pair support, expose aggregate support, use neutral
language, and never describe scores as probabilities or quality.

**Risk:** Collaborative candidates are limited to the content shortlist and
the implementation is hybrid in name only.

**Mitigation:** Form the content/collaborative candidate union before
exclusions, ordering, and top-K; test a valid collaborative-only candidate.

**Risk:** The same feedback signal is hidden in multiple weighted totals.

**Mitigation:** Consume base and affinity separately, name every component,
apply one contribution per signal, and verify integer reconstruction.

**Risk:** Floating-point differences or unordered sparse operations change
artifacts and rankings across runs.

**Mitigation:** Freeze canonical order, dtype, quantization, round-half-up,
support pruning, and complete tie-breaks; use semantic reproducibility tests.

**Risk:** Silent fallback makes operators or users believe hybrid ranking ran.

**Mitigation:** Return explicit mode/reason, expose component readiness, record
the same truth in events, and use neutral non-blocking UI disclosure.

**Risk:** Artifact and database registration fail between two durability
boundaries.

**Mitigation:** Use staged status transitions, immutable paths, production
loader validation, idempotent recovery, and readiness only after both sides
match.

**Risk:** The project overfits policy constants to the authored fixture.

**Mitigation:** Treat weights and thresholds as versioned operational defaults,
do not tune on the fixture, and reserve comparative selection for Stage 6.

**Risk:** Stage 5 changes break the verified Stage 3/4 experience.

**Mitigation:** Keep the stateless route and content artifact unchanged, make
collaborative optional, require exact fallback goldens, and run all regressions.

**Risk:** Planning language is mistaken for implemented capability.

**Mitigation:** Keep plan status, roadmap, README, API, ML, web, and
infrastructure docs explicit until Section 23 is populated from passing gates.

## 21. Implementation-Time Decisions

Phase 0–3 source preflight, first-party snapshot, consent/revision, fixture,
aggregate audit, sparse trainer, offline artifact, and pure scoring decisions
are implemented. They do not activate a hybrid policy, API readiness,
response/event changes, live build, or a product contribution flow.

### As-Built Phase 0–1 First-Party Decisions

1. Contribution authority is separate from personalization consent in
   `collaborative_contribution_consents`. One current row records the user,
   non-blank version, grant time, and optional withdrawal time. Existing users
   receive no row during migration, and no public route grants one.
2. `collaborative_data_revision` is a singleton monotonic counter. PostgreSQL
   statement triggers own changes for every source table that can alter cohort
   eligibility, labels, or exact catalog identity; recommendation events are
   excluded. A missing singleton produces a typed fail-closed audit error; the
   next source mutation after a test-only truncate recreates it atomically.
3. Source deletion is immediate relational state removal. User deletion
   cascades consent/preferences/interactions and advances the revision.
   Withdrawal, revocation, expiry changes, feedback changes, and catalog
   changes likewise invalidate the captured revision. No Phase 0–1 live
   row-level derived file exists.
4. Live extraction initializes a verified PostgreSQL `REPEATABLE READ,
   READ ONLY` transaction by pinning `pg_current_snapshot()` and capturing one
   `clock_timestamp()` cutoff before returning to extraction. A fresh
   transaction verifies the captured revision before an aggregate report is
   emitted. Eligible users require current base consent, unexpired/unrevoked state, and the configured
   contribution version granted and not withdrawn by the cutoff.
5. Temporal state includes `occurred_at <= cutoff` and
   `superseded_at IS NULL OR superseded_at > cutoff`. Stable GameLens slugs and
   the exact content-catalog fingerprint cross the ML boundary; internal IDs
   and per-user mapping do not.
6. Label policy `gamelens-collaborative-labels/1.0.0` is binary. Dislike
   dominates; like, rating >= 7, then saved positive game preference are
   positive. Ratings below 7 and viewed/played/wishlist-only rows are absent.
   Recommendation events and taxonomy preferences are never queried as labels.
7. Audit schema 1 freezes profile canonicalization, SHA-256 serialization,
   aggregate distributions, deterministic two-core support, pair support,
   activation thresholds, privacy flags, and bounded resource limits. Typed
   states cover insufficiency, catalog mismatch, revision race, and unapproved
   live input.
8. The authored fixture is `stage-5-collaborative-interactions-v1` and is
   guarded by test environment plus explicit fixture permission. Its 12
   profiles/36 positives/6 items pass functional thresholds; its provenance
   flags prohibit quality or real-user claims.
9. The default live command exits successfully with `integration_blocked` and
   `unapproved_live_source` before database access. An explicitly enabled audit
   may read eligible live state, but every report keeps
   `approved_live_training_eligibility=false`.
10. Phase 0–1 itself adds no dependency and no build/serve command. Its lack of
    an artifact was an explicit activation blocker subsequently addressed only
    for the guarded fixture/offline scope in Phase 2.

### As-Built Phase 2 Collaborative Artifact Decisions

1. The existing deterministic support fixed point is now a reusable public
   boundary. Only profiles with at least two items and items with at least two
   profiles survive; canonical profile ordering and the Phase 1 interaction
   fingerprint remain unchanged. The resulting binary CSR is canonical and
   uses `int64` arithmetic so the allowed 256-contributor case cannot overflow.
2. Sparse `X.T @ X` produces bounded pair support without materializing a dense
   item-item matrix. Self-edges and pairs supported by fewer than two profiles
   are removed. Cosine uses `float64`; round-half-up at scale 1,000,000 produces
   `int32` units. Per-item top 100 selection orders by units descending, pair
   support descending, and stable slug ascending, then stores retained neighbor
   indices in canonical ascending order.
3. The frozen model contract is `gamelens-item-item-cosine/1.0.0`, artifact
   schema `1`, and code compatibility `stage-5-v1`. The exact bundle is
   `manifest.json`, `item-slugs.json`, `item-support.npy`,
   `neighbors-indices.npy`, `neighbors-indptr.npy`, `similarity-units.npy`, and
   `pair-support.npy`. Arrays use explicit `int64` support and `int32`
   index/indptr/similarity dtypes; serialization never enables pickle.
4. The manifest freezes label, threshold, numeric, limit, matrix, neighborhood,
   source, build, catalog, interaction, and lifecycle identity plus the exact
   member set, byte sizes, and SHA-256 checksums. Every source kind requires a
   timezone-aware `valid_until > built_at`. Fixture metadata must omit live
   cutoff, consent version, and data revision; live metadata requires them.
5. The loader reads every member once under per-member and total byte caps,
   rejects symlinks and path traversal, parses strict duplicate-free/non-finite-
   free canonical JSON, validates bounded NPY headers/dtype/shape/trailing bytes,
   and recomputes graph support/cosine coherence. Catalog mismatch, expected
   revision or consent mismatch, and `now >= valid_until` fail closed with typed
   reason codes. Returned arrays have immutable byte backing.
6. The builder creates an exclusive promotion lock and temporary sibling,
   fsyncs members, writes the manifest last, loads the temporary bundle through
   the production validator, optionally performs the mandatory last-moment live
   revision callback, and atomically renames only to an unused immutable target.
   Failure cleans the temporary directory and never overwrites a target.
7. The operator CLI exposes `build`, `validate`, and `inspect`. Fixture builds
   require `ENVIRONMENT=test` plus `COLLABORATIVE_ALLOW_TEST_FIXTURE=true`,
   re-audit before fit, detect an audit-to-fit fixture change, and receive a
   deterministic build ID and 30-day validity horizon. The default live build
   returns `unapproved_live_source` before database access.
8. Inspection returns artifact identity and aggregate matrix/neighborhood facts
   without item slugs or profile rows. Scans of deterministic fixture bundles
   find no internal ID, profile key, credential, stable user key, contributor
   matrix, raw interaction, or recommendation event.
9. The project-authored fixture deterministically produces 12 contributors,
   6 retained items, 36 positive edges, and 20 directed neighbors. Equivalent
   reordered input produces byte-identical semantic members and immutable
   loaded arrays. Hand-calculated cosine quantization includes the `707107`
   golden case and pair-support-one exclusion.
10. Verification covers support cascades, duplicate profiles, overflow, top-K
    ties, caps, corruption, missing/extra members, traversal, JSON/NPY safety,
    dtype/shape/CSR/cosine coherence, catalog/revision/consent mismatch, expiry,
    promotion races, cleanup, privacy, determinism, and the real fixture
    pipeline. The full ML suite has 155 passes; one symlink case is skipped on
    the current Windows host because it cannot create symlinks and remains
    runnable on capable systems. All 200 API unit tests, Ruff, and
    `git diff --check` pass.

### As-Built Phase 3 Pure Scoring Decisions

1. Query sources are immutable stable-slug records with kinds `liked`,
   `rating`, and `saved_game`. Dislikes dominate all positive forms;
   liked-over-rating and feedback-over-saved precedence, recency/slug ordering,
   and five-positive plus five-saved caps are applied once by
   `canonicalize_collaborative_query_sources()`.
2. Sparse lookup resolves only canonical source rows through `slug_to_index`
   and exact `neighbor_indptr` slices. Unsupported sources and supported
   zero-degree rows remain distinct. At most 10 source rows, 100 neighbors per
   row, 1,000 visited edges, and 1,000 returned candidates are permitted.
3. `CollaborativeScorer` computes each candidate as the round-half-up integer
   mean of all present stored `similarity_units`. Missing edges do not enter the
   numerator or denominator. Source and dislike exclusions precede return;
   candidates order by collaborative units descending then slug ascending.
4. Results carry policy identity, canonical source partitions, exact candidate
   units/item support, every contributing edge with pair support, bounded
   diagnostics, and typed reasons for recommendations, empty input,
   unsupported sources, no edges, and all-excluded candidates. Contract errors
   return no partial result and the scorer performs no fallback.
5. `ContentRanker.materialize_base_candidates()` scores at most 1,000 exact
   catalog rows and preserves zero-content candidates with exact platform,
   popularity, and base units. Existing `score_candidates()` eligibility,
   ranking, evidence, and Stage 3 wrapper behavior remain unchanged.
6. `FeedbackRanker.materialize_affinity_candidates()` returns exact affinity
   units and profile-active state for the same bounded slug seam. The existing
   Stage 4 `rank()` path delegates to the shared calculation without changing
   items, ordering, played adjustment, explanations, policy identity, or
   result reasons.
7. The production-loaded fixture trace uses source `emberfall-tactics`, exact
   CSR offset range `[4, 8)`, and four deterministic candidates. The
   collaborative-only `starbound-couriers` handoff has collaborative/content/
   platform/popularity/base/affinity units
   `428571/0/1000000/599117/159912/0` plus empty genre, tag, and selected-game
   content evidence. Catalog fingerprints match before outputs are joined by
   stable slug.
8. Stable Phase 3 contracts are exported from the package root. Internal CSR
   lookup helpers are not root exports. Complexity and purity boundaries are
   recorded in code; `collaborative.py` imports neither content nor feedback
   rankers and performs no I/O, identity lookup, weights, played adjustment,
   top-K, fallback, prose, or HTTP mapping.
9. Slice commits are `73b4528`, `7a57dcd`, `5e25a64`, `844c695`, `a5b755c`,
   `d0b6676`, and `fa0ebd0`. The focused Phase 3 set passes 154 tests; the full
   ML suite passes 256 with one Windows symbolic-link capability skip. Ruff
   lint/format, mutation, permutation, privacy-string, resource-bound, and
   Stage 3/4 characterization gates pass with no new dependency.
10. Candidate union origin, hybrid weights, played application after hybrid
    blending, final rank, serving fallback, readiness, lifecycle validation,
    API/event schemas, UI evidence, and ranking-quality claims remain outside
    Phase 3 and are not implied by these fixture results.

### As-Built External-Source Decisions

1. Source kind is `external_snapshot`; report schema is 1; manifest schema is
   1; the source remains `local-raw-sources-verified-not-integrated`.
2. `verify`, `prepare`, and `audit` are read-only standard-library commands.
   JSON is the machine format and `--format summary` is the human format.
   Expected blocked integration exits zero; source/manifest safety errors exit
   two. No audit module command downloads source data, writes, fits, promotes,
   or mutates PostgreSQL. A requested container image build may obtain image
   dependencies.
3. All manifest members must pass exact path, HTTPS host, compressed size,
   bounded SHA-256, gzip CRC/shape, expanded size, line-count, maximum-line,
   and no-blank-line checks. Every compressed identity is verified before any
   source literal is parsed and rechecked after scanning or parsing.
4. Parser caps are 2 MiB per line, 2 GB expanded per member, 5,000,000
   top-level records, 20,000,000 nested rows, 500,000 transient users,
   100,000 transient items, 2,000,000 review pairs, 10,000,000 pair
   contributions, and 1,000,000 distinct item pairs. Source user IDs are capped
   at 256 characters and item IDs at 32. The parser is `ast.literal_eval`;
   executable and structurally invalid literals fail with typed errors.
5. Preparation policy `ucsd-steam-review-recommend-preparation-v1` uses
   source-native `recommend=true` only, collapses same-flag user/item
   duplicates, excludes conflicts, and never promotes ownership, playtime, or
   false reviews. The policy is explicitly not an approved Stage 5 label.
6. Source-level thresholds are two items per profile, two profiles per item,
   and two profiles per pair; diagnostic activation minima are 10 profiles,
   20 edges, and 5 items. A deterministic queue-based bipartite two-core reaches
   the same user/item fixed point without repeated full rescans. The JSON report
   records the algorithm and pass count; this does not freeze the future
   model-builder pruning policy.
7. Candidate profiles are sorted item tuples; the multiset retains duplicate
   profiles and is sorted before canonical JSON/SHA-256 hashing. Source user
   keys are used only for transient grouping and are never emitted.
8. The exact verified file/profile/support counts, manifest fingerprint,
   candidate fingerprint, distributions, limits, and privacy flags are in
   [`data/external/ucsd-steam/suitability-audit.json`](../data/external/ucsd-steam/suitability-audit.json).
   Source-level structural support passes, but approved training eligibility
   and functional-build readiness remain false.
9. Source identity is verified. Source provenance is recorded but not
   ingestion-approved. License/redistribution, GameLens catalog mapping,
   Stage 5 label authority, fixture activation, and live consent/lifecycle
   gates remain blocked. The catalog schema has nullable `external_id`; all 30
   seed payloads omit it and use the null default, and no reviewed Steam mapping
   artifact exists. No title matching is attempted.
10. No dependency changed. The dedicated `ucsd-source-audit` service mounts
    `data/` and `ml/` read-only, uses a read-only root filesystem, and disables
    runtime networking. The general `quality` service mounts `data/catalog/`,
    `data/fixtures/`, and the committed UCSD manifest and aggregate-audit files
    read-only; it never mounts ignored `data/external/ucsd-steam/payload/`
    bytes. Thirty-five focused UCSD cases and all 105 ML tests pass; the
    committed-report check also passes against the full local source.

The remaining implementation must resolve and record:

1. Product contribution-consent copy, public grant/re-consent/withdrawal
   routes, and approval to audit an actual live cohort. Saved personalization
   must remain a separate purpose.
2. Protected live build/contributor lineage, invalidation, retirement,
   rollback, and physical bundle deletion. The Phase 2 bundle already freezes a
   validity horizon, requires a live revision callback, and promotes immutably.
3. Actual approved live cohort/exclusion aggregates and the explicit decision
   to activate live build or remain fixture-only.
4. Candidate-union origin, hybrid ordering, and exclusion ownership across the
   combined base/affinity/collaborative set. Query-source selection, raw
   collaborative ordering, and exact-row materialization are frozen in Phase 3.
5. Hybrid policy identity, active-component gates, weights, rounding, played
   order, explanation facts, and exact Stage 4 equivalence evidence.
6. Component readiness states, fallback reasons, database checks, restart,
   activation, rollback, and crash recovery.
7. Personalized response additions, event columns/JSON bounds, `stage-5-v1`
   constraints, OpenAPI compatibility, and frontend copy.
8. Live lifecycle commands, guarded fixture-artifact E2E topology,
   dependency/license changes, security results, artifact sizes, and measured
   runtime diagnostics.

Unresolved items may not become silent defaults. At Stage 5 completion, this
checklist must be replaced by exact as-built decisions and passing evidence.

## 22. Stage 6 Handoff

When complete, Stage 5 should leave Stage 6 with:

- A source- and consent-qualified canonical interaction snapshot contract with
  exact cutoff, fingerprint, label policy, filters, and aggregate diagnostics.
- A documented distinction between project-authored fixture data and any
  approved real/local cohort.
- Reproducible popularity, content, feedback, collaborative, and hybrid
  baselines with stable model/data/policy identity.
- An immutable sparse collaborative artifact, loader, build/validate commands,
  lifecycle registry, and cold-start/fallback behavior.
- Independently reconstructible component scores, weights, contributions,
  support, evidence, and final ordering.
- Versioned personalized response and generation-event fields sufficient to
  audit which component ran, without treating an event as exposure or label.
- Exact candidate, exclusion, source, top-K, tie, and played semantics.
- Complete functional, deterministic, privacy, integration, browser, and
  regression evidence plus honest known limitations.

Stage 6 may then define leakage-safe temporal or user-level splits; compare
popularity, content, feedback, collaborative, and hybrid variants; choose
Precision/Recall/NDCG and supporting coverage/novelty/diversity measures; save
machine-readable configurations and results; and write an evidence-based
experiment report.

The Stage 5 fixture, tiny local cohorts, build diagnostics, deterministic
examples, and successful UI flows are not recommendation-quality evidence.
Before Stage 5 is marked complete, this section must change from “should leave”
to verified facts only.

## 23. Verified Completion Record

Pending complete Stage 5 implementation. The verified Phase 0–3 source/audit,
offline-artifact, and pure-scoring slices are recorded in Section 21; they are
not a Stage 5 completion claim.

When every Section 19 gate passes, this section must record the implementation
commit/PR, runtime and lock versions, migration head, consent/lifecycle
decision, data audit, snapshot and artifact identities/sizes, aggregate label
counts, deterministic examples, exact commands, test counts, coverage,
durations, Compose and image checks, browser/accessibility evidence, dependency
and privacy review, limitations, and the finalized Stage 6 handoff. It must not
contain invented values or formal ranking-quality claims.
