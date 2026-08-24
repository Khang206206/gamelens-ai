# GameLens AI

## Stage 5 Engineering Plan: Collaborative and Hybrid Ranking

- **Document status:** Engineering plan ready on 2026-08-19; Phase 0–1
  external-source preflight slice verified on 2026-08-23; collaborative
  runtime implementation has not started.
- **Stage 4 prerequisite:** Complete and verified on 2026-08-13.
- **Planning and target implementation branch:**
  `feat/stage-5-collaborative-and-hybrid-ranking`
- **Primary outcome:** A reproducible, consent- and retention-aware
  collaborative artifact and a deterministic hybrid-ranking policy whose
  content, feedback, collaborative, platform, and popularity signals remain
  independently observable.

Sections 1–20 remain the forward-looking engineering plan except where the
Phase 0–1 external-source preflight slice is explicitly marked verified.
Section 21 records only measured implementation decisions. Section 22 is a
provisional Stage 6 handoff, and Section 23 remains pending until every
acceptance gate passes. The preflight does not make a Stage 5 collaborative
runtime capability available.

## 1. Context

Stages 1 through 4 established the repository, PostgreSQL catalog, FastAPI and
Next.js applications, deterministic 30-game synthetic seed, reproducible
content artifact, request-scoped recommendation flow, explicit-consent
anonymous persistence, temporal feedback state, feedback-aware ranking, and
bounded recommendation-generation events. The implemented contracts and
verification evidence are recorded in the
[Stage 4 plan](stage-4-feedback-persistence-plan.md).

The current recommender is not collaborative. Model
`gamelens-content-tfidf/1.0.0` learns catalog-level TF-IDF features, and policy
`gamelens-feedback-adjustment/1.0.0` applies a deterministic per-request
content affinity plus dislike and played rules. Neither component learns
cross-user interaction patterns.

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
transaction. It captures `transaction_timestamp()` once and uses that database
time as the inclusive cutoff. Rows are interpreted as active at the cutoff
when:

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

Names are illustrative and must be finalized in Phase 0. `(+ planned)` marks
new files; generated snapshots and artifacts remain ignored.

```text
.
|-- apps/
|   |-- api/
|   |   |-- alembic/versions/
|   |   |   `-- 0006_stage_5_collaborative_contract.py  (+ planned)
|   |   |-- app/
|   |   |   |-- commands/
|   |   |   |   `-- collaborative_artifact.py          (+ planned)
|   |   |   |-- repositories/
|   |   |   |   `-- collaborative_snapshot.py          (+ planned)
|   |   |   |-- services/
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
|   |   `-- collaborative-interactions.json             (+ planned test fixture)
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
|   |   |-- collaborative_artifacts.py                  (+ planned)
|   |   |-- collaborative_training.py                   (+ planned)
|   |   |-- collaborative.py                            (+ planned)
|   |   `-- hybrid.py                                   (+ planned)
|   `-- tests/                                          (* changed)
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
  `4c83b8433a2c048511c7aa38073c4a152686cc70678bdd0990a56d42e9d3b357`.
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
  and all 87 ML tests pass. Focused coverage includes exact verification,
  fail-before-parse and post-parse checks, bounded reads, safe literal and gzip
  errors, aggregate-only output, duplicate/conflict policy, canonical
  fingerprints, fixed-point pruning, ambiguous metadata, insufficiency
  reasons, fail-closed gates, and strict CLI/report semantics.
- A fresh full-source `audit --check-report` run matches the committed JSON by
  canonical JSON type and value.

This slice does not satisfy the complete Phase 0 or Phase 1 exit criteria.
Contribution consent, derived-data invalidation/deletion, the live
repeatable-read extractor, catalog mapping, the project-authored fixture,
revision/lineage migrations, and all collaborative runtime work remain
unimplemented and blocking.

## 9. Implementation Phase 2: Collaborative Artifact and Offline Builder

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

### Objective

Convert bounded source-game context and the validated artifact into
deterministic collaborative candidates and reconstructible evidence.

### Work

1. Define immutable input/output schemas independent of HTTP and SQLAlchemy.
2. Canonicalize and cap positive feedback and saved-game query sources.
3. Add the pure specified-row base/affinity materializer required to represent
   collaborative-only candidates without changing Stage 3 eligibility.
4. Resolve sparse neighbor edges, aggregate available similarities, and retain
   bounded top source evidence per candidate.
5. Exclude all query sources and disliked games before candidate return.
6. Represent unsupported source, unsupported candidate, and no-edge cases
   explicitly rather than assigning fabricated similarity.
7. Apply fixed-point quantization and stable ordering.
8. Add pure golden, property, boundary, and mutation-safety tests.

### Verification

- Repeated and permuted equivalent source inputs return the same scores and
  order.
- Every score is recomputable from returned source edges.
- A source cannot recommend itself, and a dislike cannot re-enter through a
  second source.
- A collaborative-only candidate exposes zero/empty content evidence where
  appropriate plus exact platform, popularity, base, affinity, and origin
  fields; the existing ranker wrappers remain unchanged.
- Empty/unsupported context returns a typed no-support result without mutating
  the artifact or falling back inside the scorer.

### Exit Criteria

- The scorer is deterministic, bounded, identity-free, and independently
  testable.
- Candidate evidence is sufficient for the hybrid policy and response mapper.

## 11. Implementation Phase 4: Versioned Hybrid Ranking Policy

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

The external-source preflight names are now frozen as implemented. Remaining
collaborative command names document intended separation and are still
forward-looking.

| Capability | Optional Make wrapper | Required direct equivalent |
| --- | --- | --- |
| Verify local UCSD source identity | `make ucsd-steam-verify` | `docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam verify --root /workspace --format json` |
| Profile UCSD ingestion preparation | `make ucsd-steam-prepare` | `docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam prepare --root /workspace --format json` |
| Audit UCSD source-level support | `make ucsd-steam-audit` | `docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam audit --root /workspace --format json` |
| Check committed UCSD aggregate report | `make ucsd-steam-audit-check` | `docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam audit --root /workspace --check-report data/external/ucsd-steam/suitability-audit.json --format summary` |
| Audit eligible live interaction data (planned) | `make collaborative-audit` | `python -m app.commands.collaborative_artifact audit` |
| Build a new collaborative bundle | `make collaborative-build` | `python -m app.commands.collaborative_artifact build` |
| Validate configured bundle | `make collaborative-validate` | `python -m app.commands.collaborative_artifact validate` |
| Inspect bundle metadata | none required | `python -m app.commands.collaborative_artifact inspect` |
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

Only the Phase 0–1 external-source preflight decisions are implemented. They
do not silently resolve the separate live-data, fixture, model, artifact, API,
or product decisions.

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
    runtime networking. The general `quality` service receives only the seed,
    manifest, and committed audit paths, not ignored raw sources. Thirty-five
    focused UCSD cases and all 87 ML tests pass; the committed-report check also
    passes against the full local source.

The remaining implementation must resolve and record:

1. Exact contribution-consent resource, version, copy, re-consent, withdrawal,
   and whether saved personalization remains separately available.
2. Exact lineage/revision schema, trigger or service ownership, concurrency,
   expiry safety horizon, invalidation, retirement, and physical deletion rule.
3. Snapshot cutoff, source-kind identifiers, canonical serialization,
   fingerprint, audit schema, aggregate bounds, and privacy review result.
4. Actual eligible cohort and exclusion counts, whether live data crosses
   functional gates, and any decision to remain fixture-only.
5. Final label-policy identity, saved-game preference semantics, reaction
   precedence, rating threshold, duplicate-source behavior, and unknowns.
6. Minimum user/item/pair support, activation minima, neighborhood cap, and
   exact insufficiency codes.
7. Sparse algorithm, block strategy, dtype, quantization, member shapes,
   resource limits, and measured build diagnostics.
8. Collaborative model, artifact schema, code compatibility, manifest members,
   checksums, build ID, and configuration names.
9. Query-source precedence/cap, collaborative aggregation formula, source
   evidence cap, candidate union, and ordering keys.
10. Hybrid policy identity, active-component gates, weights, rounding, played
    order, explanation facts, and exact Stage 4 equivalence evidence.
11. Component readiness states, fallback reasons, database checks, restart,
    activation, rollback, and crash recovery.
12. Personalized response additions, event columns/JSON bounds,
    `stage-5-v1` constraints, OpenAPI compatibility, and frontend copy.
13. Final commands, exit codes, configuration, Compose topology, fixture
    provenance, dependencies, and license changes.
14. Actual test counts, coverage, durations, artifact sizes, aggregate
    diagnostics, platform evidence, security results, and known gaps.

Unresolved items may not become silent defaults. At completion, this checklist
must be replaced by the exact as-built decision record and links to evidence.

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

Pending complete Stage 5 implementation. The verified Phase 0–1
external-source slice is recorded in Section 21 and the committed aggregate
audit; it is not a Stage 5 completion claim.

When every Section 19 gate passes, this section must record the implementation
commit/PR, runtime and lock versions, migration head, consent/lifecycle
decision, data audit, snapshot and artifact identities/sizes, aggregate label
counts, deterministic examples, exact commands, test counts, coverage,
durations, Compose and image checks, browser/accessibility evidence, dependency
and privacy review, limitations, and the finalized Stage 6 handoff. It must not
contain invented values or formal ranking-quality claims.
