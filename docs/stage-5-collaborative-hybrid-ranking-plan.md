# GameLens AI

## Stage 5 Engineering Plan: Collaborative and Hybrid Ranking

- **Document status:** Engineering plan ready on 2026-08-19; external-source
  preflight verified on 2026-08-23; Phase 0–1 first-party audit foundation
  verified on 2026-08-24; Phase 2 offline collaborative artifact foundation
  verified on 2026-08-25; Phase 3 pure collaborative scoring and exact-row
  handoff verified on 2026-08-28; Phase 4 versioned hybrid policy and exact
  Stage 4 fallback verified on 2026-08-29; Phase 5 artifact lifecycle,
  readiness, and internal API orchestration verified on 2026-08-30; Phase 6
  response, event, OpenAPI, and product integration verified on 2026-09-01;
  Phase 7 derived-data lifecycle and safe commands verified on 2026-09-03.
  Phase 8 Docker, configuration, full-stack fixtures and docs reconciliation
  verified on 2026-09-09; Phases 9–10 remain pending.
- **Stage 4 prerequisite:** Complete and verified on 2026-08-13.
- **Planning and target implementation branch:**
  `feat/stage-5-collaborative-and-hybrid-ranking`
- **Primary outcome:** A reproducible, consent- and retention-aware
  collaborative artifact and a deterministic hybrid-ranking policy whose
  content, feedback, collaborative, platform, and popularity signals remain
  independently observable.

Sections 1–20 remain the forward-looking engineering plan except where the Phase
0–7 slices are explicitly marked verified. Section 21 records only measured
implementation decisions. Section 22 is a provisional roadmap Stage 6 handoff,
and Section 23 remains pending until every Stage 5 acceptance gate passes. Phase
6 exposes one synchronized saved response and `stage-5-v1` event from the Phase
5 decision and presents cautious browser evidence. Phase 7 adds guarded live
build and lifecycle operations without granting product contribution consent,
approving a production cohort, or completing Stage 5.

## 1. Context

Stages 1 through 4 established the repository, PostgreSQL catalog, FastAPI and
Next.js applications, deterministic 30-game synthetic seed, reproducible content
artifact, request-scoped recommendation flow, explicit-consent anonymous
persistence, temporal feedback state, feedback-aware ranking, and bounded
recommendation-generation events. The implemented contracts and verification
evidence are recorded in the
[Stage 4 plan](stage-4-feedback-persistence-plan.md).

The stateless recommender is not collaborative. Model
`gamelens-content-tfidf/1.0.0` learns catalog-level TF-IDF features, and policy
`gamelens-feedback-adjustment/1.0.0` applies a deterministic per-request content
affinity plus dislike and played rules. Neither component learns cross-user
interaction patterns. The ML package also exposes a pure artifact-backed
collaborative candidate scorer and versioned hybrid ranker, and Phase 5 consumes
them from saved-request orchestration. Phase 6 now exposes the resulting hybrid
decision when the optional component is ready or an explicit exact Stage 4
fallback when it is not; the stateless endpoint remains unchanged.

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
algorithm. An approved interaction source must have explicit provenance, label
meaning, consent authority, retention behavior, catalog alignment, and enough
support for the baseline. Until those conditions hold, the system must report
collaborative ranking as unavailable and preserve the verified Stage 4 path
exactly.

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
project-authored interaction fixture. Activating an artifact built from local or
real user data remains blocked unless the Phase 0 consent and derived-data
lifecycle are implemented and the suitability audit passes.

## 2. Stage Objectives

Stage 5 will deliver:

1. A written interaction-data contract covering source, authority, purpose,
   cutoff, consent, retention, deletion, label eligibility, catalog identity,
   provenance, and limitations.
2. A read-only suitability command that reports aggregate cohort, label, user,
   item, sparsity, support, and exclusion counts without fitting a model or
   exposing an identity.
3. A separate affirmative data-contribution boundary, or an explicit decision to
   keep non-fixture collaborative training disabled when that boundary is
   absent.
4. A canonical database-time snapshot query using one repeatable-read, read-only
   transaction and an as-of-cutoff interpretation of temporal rows.
5. A frozen positive-label policy that never converts unknown, viewed,
   wishlisted, played, disliked, or recommendation-event rows into implicit
   positives.
6. A project-authored deterministic interaction fixture, isolated from real data
   and labeled only as functional test input.
7. A sparse binary user-item representation with bounded eligibility,
   cardinality, memory, and neighborhood limits.
8. An explainable item-item cosine baseline with overlap support, self-edge
   removal, deterministic pruning, fixed numeric policy, and stable tie-breaks.
9. A collaborative artifact contract with model/schema/code identity, catalog
   and interaction fingerprints, provenance, cutoff, consent policy, data
   revision, validity horizon, aggregate counts, checksums, and resource caps.
10. Immutable build, validate, activate, rollback, invalidate, and retire
    behavior separate from the Stage 3 content artifact lifecycle.
11. A pure collaborative scorer that consumes only stable game slugs and bounded
    source context, never a user ID, credential, database session, or mutable
    model object.
12. Honest cold-start behavior for unsupported users, sources, items, catalogs,
    or datasets, with no fabricated collaborative score.
13. A versioned hybrid policy that combines independently exposed content,
    feedback-affinity, collaborative, platform, popularity, and played
    components before final top-K truncation.
14. Exact Stage 4 score and order preservation whenever the collaborative
    component is absent, invalid, stale, unsupported, or gated off.
15. Candidate union and exclusion rules that can admit supported collaborative
    candidates while retaining selected-source exclusion, dislike exclusion, and
    played adjustment semantics.
16. Fixed-point component contributions and ordering evidence from which every
    returned hybrid score can be reconstructed.
17. Component-level readiness that distinguishes the required content model from
    the optional collaborative capability without taking content serving down.
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
- Exploration, contextual bandits, reinforcement learning, diversity reranking,
  sponsored ranking, business-rule optimization, or A/B testing.
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
- Making the optional collaborative artifact a prerequisite for catalog, content
  recommendations, saved feedback, or data deletion.
- Persisting raw credentials, token digests, internal user IDs, stable
  pseudonymous user keys, IP addresses, headers, or device fingerprints in a
  snapshot or artifact.
- Reusing expired, revoked, cleared, or deleted contributions in a new build, or
  continuing to serve an artifact that the lifecycle contract invalidates.
- Production schedulers, queues, caches, managed/external artifact-registry
  services, monitoring, alerting, CI/CD, or deployment automation; those remain
  Stage 7 concerns. The minimal PostgreSQL lineage tables required for Stage 5
  privacy invalidation are not a production registry service.
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
when no dislike overrides it is a positive. These sources collapse to one binary
edge. Dislikes are exclusions or possible future negative evidence; everything
else remains unknown.

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

Content, platform, popularity, feedback affinity, collaborative similarity, and
played adjustment retain separate raw scores, weights, contributions, and
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

Governance precedes extraction; extraction precedes fitting; artifact validation
precedes serving; pure scoring precedes API changes; API contracts precede UI
activation. Every phase has an executable exit criterion.

## 5. Proposed Technical Decisions

These decisions are proposals to freeze in Phase 0. Section 21 must replace them
with exact as-built choices; unresolved values cannot become silent defaults.

### 5.1 Stage 3 and Stage 4 Compatibility Boundary

- `POST /api/v1/recommendations` stays content-only, cookie-agnostic,
  request-scoped, read-only, and contract-compatible.
- `POST /api/v1/me/recommendations` is the only Stage 5 hybrid activation point.
  It retains one commit-acknowledged generation event per HTTP 200.
- Model `gamelens-content-tfidf/1.0.0`, artifact schema `1`, compatibility
  `stage-3-v1`, and feedback policy `gamelens-feedback-adjustment/1.0.0` remain
  unchanged.
- Stage 5 will add a separate artifact and policy rather than changing content
  files in place.

### 5.2 Interaction-Data Suitability and Provenance Gate

The implemented external-source preflight runs before any build and emits
machine-readable JSON or a human-readable summary. It records source kind,
manifest fingerprint, exact file identity and gzip shape, aggregate schema
quality, source-metadata alignment, candidate-profile fingerprint, matrix
density, support distributions, thresholds, limits, and typed gate states. It
has no database time, cutoff, consent policy, or data revision because it does
not query live GameLens data.

A future consent-qualified live audit must additionally record catalog
fingerprint, PostgreSQL time and cutoff, consent policy, data revision, and
eligible/excluded contributor and label counts by reason. It remains subject to
the transaction, lifecycle, and identity-minimization contracts below.

`ready_for_functional_build` means only that the pipeline has sufficient
approved support to construct a baseline. It does not mean the data is
representative or that recommendations are good. The UCSD report instead exposes
`source_level_support_passes`; its `ready_for_functional_build` and
`approved_training_eligibility` fields remain false. Live-data activation
requires approved consent and derived-data lifecycle gates. Project-authored
fixture activation is reported separately.

UCSD Steam Versions 1 and 2 are selected only for local read-only source
preflight. They are not selected or approved for ingestion, training, artifact
construction, or serving. The manifest records exact source URLs, attribution to
the UCSD McAuley Lab, retrieval date, checksums, and source shape; it does not
assert ownership or rights-holder status. The source page requests citation, but
citation is not a license grant and this repository records no dataset license
or redistribution grant. License/redistribution, ingestion provenance, Stage 5
label authority, GameLens catalog mapping, fixture activation, and live-data
consent/lifecycle gates remain blocked.

### 5.3 Canonical Interaction Snapshot and Cutoff

The live extractor uses one PostgreSQL `REPEATABLE READ, READ ONLY` transaction.
Immediately after setting its mode, one initialization query calls
`pg_current_snapshot()` to pin MVCC visibility and captures `clock_timestamp()`
once as the inclusive cutoff. The helper completes both operations before
returning to extraction, closing the transaction-start/ first-snapshot race.
Rows are interpreted as active at the cutoff when:

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
and is not retained after success or failure; only the aggregate audit and final
item-level artifact may remain. Approved external or project-authored fixture
snapshots, if materialized for reproducible tests, stay ignored and follow their
documented source lifecycle.

### 5.4 Label Eligibility, Precedence, and Unknowns

The proposed version-1 training policy is binary:

| Current state at cutoff                   | Offline matrix value | Reason                                 |
| ----------------------------------------- | -------------------: | -------------------------------------- |
| Saved `game` preference with weight `> 0` |                  `1` | Explicit positive game selection       |
| Explicit `liked` reaction                 |                  `1` | Direct positive feedback               |
| No reaction and rating `>= 7`             |                  `1` | Existing Stage 4 positive threshold    |
| Explicit `disliked` reaction              |               absent | Overrides a rating; not a positive     |
| Rating below `7`                          |               absent | Not defined as a negative in version 1 |
| `viewed`, `played`, or `wishlisted` alone |               absent | Meaning is too ambiguous               |
| Recommendation event                      |               absent | Generation audit record only           |
| No row                                    |               absent | Unknown, not negative                  |

At most one positive exists for a contributor/game pair after source collapse,
reaction precedence, and deduplication. An active dislike dominates a saved game
preference or rating for the same game. Ratings and duplicate positive sources
are not magnitude-weighted in the first baseline. Superseded history is used
only to reconstruct state at the cutoff, never as repeated confidence.

### 5.5 Consent, Revision, Expiry, and Derived-Data Invalidation

Phase 0 should prefer a separate optional contribution-consent resource and
copy, default off, rather than forcing training permission to use saved
personalization. The database records its version and grant/withdrawal time; the
browser explains aggregate offline use and fallback.

A small PostgreSQL build-lineage registry records the artifact/build identity,
status, aggregate contributor count, and contributor membership. Membership uses
the existing internal user foreign key with `ON DELETE CASCADE`; it stays inside
PostgreSQL and never enters the artifact or response. A monotonic source
revision advances for relevant preference, interaction, consent, and lifecycle
mutations. The builder captures it with the snapshot and verifies it again
before promotion, preventing a mixed or already-obsolete build.

After promotion, a new positive recorded after the cutoff does not invalidate an
otherwise valid point-in-time artifact; the next explicit build may include it.
A transaction that removes or changes an edge contained in a live build,
withdraws contribution consent, revokes/deletes its contributor, or performs
eligible retention must mark every affected registered build invalid before it
commits. Contributor lineage makes that update targetable. Cascade/count and
eligibility checks remain defenses if the artifact file still exists.

A live-data artifact records its build ID, revision, expected contributor count,
and earliest contributor expiry. Runtime use requires:

- artifact revision equal to the matching registered build revision;
- one active matching readiness row with the expected contributor count and
  current invalidation epoch/status;
- current approved contribution-consent version;
- current time before the artifact validity horizon;
- exact catalog fingerprint and artifact compatibility;
- no explicit retirement marker.

A mismatch immediately disables only the collaborative component. Rebuild from
current eligible state is explicit. Obsolete live-data bundles must be retired
and removed according to the Phase 0 deletion decision before another live
artifact is promoted. If this end-to-end behavior cannot be implemented and
tested, live-data build and activation remain blocked while the synthetic
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
round-half-up. Neighbor ordering is similarity units descending, overlap support
descending, then neighbor slug ascending.

Resource limits cover users, items, input nonzeros, retained neighbor nonzeros,
member count, member bytes, total bytes, and JSON depth. Exceeding a limit fails
safely before promotion.

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
contains no user row, user ID, stable pseudonym, credential, preference payload,
or recommendation event.

Build writes a temporary sibling, validates it with the production loader, then
atomically promotes to a new immutable path. Validation never repairs or
overwrites a bundle. Activation and rollback are explicit configuration changes.

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

- feedback affinity receives `10%` when a valid Stage 4 positive profile exists;
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
candidate with no retained source edge receives `collaborative_supported=false`,
raw/contribution units of zero, and the same request-wide collaborative weight;
its missing 10% is not reassigned to base. This is an explicit absence of
positive collaborative support, not a dislike or a predicted negative
probability. Stage 6 must measure the consequence before changing this versioned
policy.

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

Phase 5 implements the additive status block and readiness states. Phase 6
implements the truthful public mode: hybrid decisions expose hybrid evidence,
while every unavailable/no-support outcome exposes explicit `stage_4_fallback`
with exact Stage 4 ranking.

### 5.15 Personalized Response and Event Contract

The saved response retains existing fields for compatibility and adds optional
hybrid-policy, collaborative-model, ranking-mode, fallback-reason, and per-item
collaborative evidence. The stateless response does not change.

A data-preserving migration adds all-or-none collaborative identity and
feedback/hybrid policy fields to `recommendation_events`, with a new
`stage-5-v1` constraint. Existing `legacy-v1` and `stage-4-v1` rows remain
valid. For Stage 5 rows:

- existing model columns continue to identify the content model;
- explicit fields identify feedback policy, hybrid policy, collaborative model,
  and interaction fingerprint when applied;
- request context records bounded mode and fallback reason;
- result summaries store compact fixed-point component units and support;
- no prose, raw state dump, identity, credential, or unbounded edge list is
  stored.

Events remain generation audit records and are excluded from every interaction
snapshot query by construction.

### 5.16 Browser and Product Behavior

The browser remains a renderer of server order and evidence. It may show an
“aggregate interaction signal” row only when the API applied it, with a short
description of what was and was not used. Fallback remains useful and should not
be presented as an error when content serving is ready.

If separate contribution consent is implemented, it is unchecked by default,
independent from saved personalization, keyboard operable, versioned, and
withdrawable. Copy must explain that withdrawal stops future eligible builds and
triggers the documented artifact invalidation path. Loading, stale, unsupported,
failure, consent, withdrawal, and clear-data states require visible text and
accessible announcements.

### 5.17 Docker, Commands, and Branch Topology

The existing content model profile and commands keep their meaning. Stage 5 adds
separate collaborative audit/build/validate operations, a separate artifact
path, and a disposable fixture path. The API mounts both configured artifacts
read-only. No request or service startup fits either model.

Development and E2E builds use new immutable disposable paths. Lifecycle tests
may delete only guarded disposable artifacts and databases. Production
scheduling and managed/external artifact registry services remain Stage 7 work;
the minimal Stage 5 PostgreSQL build-lineage rows are part of the privacy
contract.

An artifact with `source_kind=fixture` is loadable only when `ENVIRONMENT=test`
and an explicit test-only fixture flag are both present. Development and
production reject it with `fixture_not_allowed`; no ordinary user-facing
response may present synthetic co-occurrence as an aggregate interaction signal.

## 6. Target Repository Structure

Phase 0–7 names marked `(+ implemented)` are as built. Later-phase illustrative
entries remain `(+ planned)`; generated snapshots and artifacts remain ignored.

```text
.
|-- apps/
|   |-- api/
|   |   |-- alembic/versions/
|   |   |   |-- 0006_stage_5_collaborative_contract.py  (+ implemented)
|   |   |   |-- 0007_stage_5_artifact_registry.py       (+ implemented)
|   |   |   |-- 0008_stage_5_authority_loss.py          (+ implemented)
|   |   |   |-- 0009_stage_5_label_changes.py           (+ implemented)
|   |   |   |-- 0010_stage_5_recommendation_event_contract.py (+ implemented)
|   |   |   `-- 0011_stage_5_lifecycle_guard.py         (+ implemented)
|   |   |-- app/
|   |   |   |-- commands/
|   |   |   |   |-- collaborative_snapshot.py          (+ implemented)
|   |   |   |   `-- collaborative_artifact.py          (+ implemented)
|   |   |   |-- repositories/
|   |   |   |   |-- collaborative_snapshot.py          (+ implemented)
|   |   |   |   |-- collaborative_registry.py          (+ implemented)
|   |   |   |   `-- collaborative_registry_types.py    (+ implemented)
|   |   |   |-- services/
|   |   |   |   |-- collaborative_snapshot.py          (+ implemented)
|   |   |   |   |-- collaborative_build.py             (+ implemented)
|   |   |   |   |-- collaborative_lifecycle.py         (+ implemented)
|   |   |   |   |-- collaborative_retirement.py        (+ implemented)
|   |   |   |   |-- collaborative_recovery.py          (+ implemented)
|   |   |   |   |-- collaborative_rollback.py          (+ implemented)
|   |   |   |   `-- recommendation/
|   |   |   |       |-- collaborative.py               (+ implemented)
|   |   |   |       |-- readiness.py                   (+ implemented)
|   |   |   |       |-- readiness_resolution.py        (+ implemented)
|   |   |   |       |-- hybrid.py                      (+ implemented)
|   |   |   |       |-- decision.py                    (+ implemented)
|   |   |   |       `-- status.py                      (+ implemented)
|   |   |   `-- schemas/
|   |   |       |-- model_status.py                    (+ implemented)
|   |   |       `-- personalized_recommendations.py    (+ implemented)
|   |   `-- tests/                                      (* changed)
|   `-- web/
|       |-- src/lib/api/generated.ts                    (+ Phase 6 contract)
|       |-- src/features/recommendations/               (+ Phase 6 results)
|       `-- e2e/                                        (+ Phase 8 implemented)
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
|   `-- docker-compose.e2e.yml                          (* later phase planned)
|-- ml/
|   |-- artifacts/
|   |   `-- collaborative/                              (ignored generated)
|   |-- src/gamelens_recommender/
|   |   |-- interaction_snapshot.py                     (+ implemented)
|   |   |-- collaborative_artifacts.py                  (+ implemented)
|   |   |-- collaborative_training.py                   (+ implemented)
|   |   |-- collaborative.py                            (+ implemented)
|   |   `-- hybrid.py                                   (+ implemented)
|   `-- tests/
|       |-- test_phase3_handoff.py                      (+ implemented)
|       |-- test_hybrid_*.py                            (+ implemented)
|       `-- test_phase4_handoff.py                      (+ implemented)
|-- .env.example                                        (* changed)
|-- docker-compose.yml                                  (* changed)
`-- Makefile                                            (* changed)
```

The SQLAlchemy repository owns consent-aware PostgreSQL extraction. The ML
package owns canonical interaction schemas after extraction, sparse fitting,
artifact validation, pure scoring, and hybrid math. API services own transaction
boundaries and HTTP mapping. The browser owns presentation only.

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
  preferences, and non-game preferences never appear as offline positives; saved
  positive `game` preferences follow the explicit versioned label rule.
- Audit output contains bounded aggregates and no user ID, token material, raw
  per-user row, or credential; identity-bearing lineage remains only in the
  protected relational database.
- Success, refusal, and injected build failure leave no live row-level snapshot
  or cohort mapping on disk.
- Concurrent feedback mutation either precedes or follows the captured snapshot;
  it cannot produce a mixed revision.

### Exit Criteria

- The extractor and audit report are deterministic and privacy-reviewed.
- The fixture has exact expected labels and exclusion reasons.
- Live-data build remains gated unless authority, revision, and lifecycle are
  all valid.

### Verified Phase 0–1 External-Source Slice (2026-08-23)

The following bounded slice is implemented and verified:

- `gamelens_recommender.ucsd_steam` provides read-only `verify`, `prepare`, and
  `audit` commands plus JSON and summary output. Expected blocked integration is
  a successful command state; malformed, missing, mismatched, unsafe, or
  over-limit input exits with a typed error.
- The implementation uses only the Python 3.12 standard library. It verifies all
  three compressed members before parsing, rejects symlinks/path escape, bounds
  each exact compressed read, caps a line at 2 MiB and each expanded member at 2
  GB, uses bounded `ast.literal_eval` rather than `eval`, and rechecks all
  compressed identities after scanning or parsing.
- Manifest schema 1 freezes exact compressed/expanded sizes, SHA-256 values,
  line counts, maximum line sizes, fail-closed gate states, and source status
  `local-raw-sources-verified-not-integrated`. Its canonical SHA-256 is
  `a55b2b2cc5b96a04bb58f29e789cc80467997128da6f73e806a56000585095ca`.
- Preparation policy `ucsd-steam-review-recommend-preparation-v1` treats only
  source-native `recommend=true` as a candidate, collapses duplicate user/item
  pairs, excludes conflicts, ownership, playtime, and false reviews, and
  performs only unambiguous v1-to-v2 source metadata alignment. This is not an
  approved Stage 5 label or a GameLens catalog mapping.
- The canonical candidate fingerprint hashes the sorted multiset of sorted
  source-item profiles without serializing a source user key. The verified
  fingerprint is
  `eafce3dcdd6cde57ec5eacf1746b83f0a3e269c0fc9069b2da2bf5d78ecd9f66`.
- The verified audit contains 59,305 review rows, 58,431 deduplicated user/item
  pairs, 51,692 unambiguous true candidate pairs, and 47,492 pairs aligned to
  one unambiguous v2 metadata ID. Three deterministic queue-based bipartite
  fixed-point passes leave 9,792 profiles, 33,049 edges, 1,516 items, and 6,481
  item pairs with support of at least two. These are structural diagnostics
  only.
- The aggregate report emits no source user identifier or row-level snapshot,
  writes no processed data, and fits no model. Thirty-five focused UCSD cases
  and all 105 ML tests pass. Focused coverage includes exact verification,
  fail-before-parse and post-parse checks, bounded reads, safe literal and gzip
  errors, aggregate-only output, duplicate/conflict policy, canonical
  fingerprints, fixed-point pruning, ambiguous metadata, insufficiency reasons,
  fail-closed gates, and strict CLI/report semantics.
- A fresh full-source `audit --check-report` run matches the committed JSON by
  canonical JSON type and value.

The external-source slice alone does not authorize ingestion and remains
independent from the first-party interaction path below.

### Verified Phase 0–1 First-Party Interaction Foundation (2026-08-24)

- Migration file `0006_stage_5_collaborative_contract.py` advances the schema
  head to `0006_stage_5_collab_contract`. It adds one optional, versioned
  contribution-consent row per user and one monotonic singleton data revision.
  The populated upgrade grants no consent to existing users.
- Statement triggers advance the revision after mutations to users, contribution
  consent, preferences, interactions, catalog rows, taxonomies, and catalog
  associations. Recommendation events are deliberately not a revision source and
  are never queried as labels.
- User deletion cascades the contribution-consent row and existing user-owned
  source state; the source mutation advances the revision. Phase 0–1 writes no
  live row snapshot or artifact, so there is no derived file to delete. Any live
  promotion must compare the captured revision and use protected
  build/contributor lineage before a bundle can become serveable; Phase 5 now
  supplies that lineage/readiness boundary, while the promotion command remains
  later work.
- The live extractor requires PostgreSQL, establishes one
  `REPEATABLE READ, READ ONLY` transaction, pins `pg_current_snapshot()`, and
  captures one `clock_timestamp()` cutoff before returning to extraction. It
  applies consent/expiry/revocation/withdrawal and as-of temporal filters, uses
  the exact current content-catalog fingerprint, groups only transient internal
  IDs, and returns sorted stable-slug profiles with aggregate exclusions.
  Preference/interaction queries join one reusable eligible-user subquery and
  stream 1,000 rows per batch without per-user bind expansion.
- Label policy `gamelens-collaborative-labels/1.0.0` freezes dislike dominance,
  active likes, ratings of at least 7, and saved positive game preferences. Low
  ratings, viewed/played/wishlist-only state, superseded and post-cutoff rows,
  non-game preferences, ineligible contributors, and recommendation events are
  absent from positives.
- Canonical profile serialization retains the sorted profile multiset and hashes
  it with the label-policy identity. The bounded audit emits only aggregates,
  typed insufficiency/refusal errors, the exact catalog and interaction
  fingerprints, cutoff, and revision; no ID or cohort mapping is written.
- The strict project-authored fixture contains 12 synthetic profiles, 36
  expected positives, 6 supported items, explicit exclusions, and cold-start
  cases. It is accepted only with `ENVIRONMENT=test` plus
  `COLLABORATIVE_ALLOW_TEST_FIXTURE=true`. Its read is capped at 1,000,000
  bytes, and duplicate/unrecognized keys, non-finite constants, and JSON type
  aliases fail closed. It passes functional thresholds but explicitly remains
  non-representative and non-quality evidence.
- `COLLABORATIVE_LIVE_DATA_ENABLED=false` and an unset contribution-consent
  version are the defaults. `make collaborative-audit` returns
  `integration_blocked` without creating a database engine. No Phase 0–1 command
  builds, promotes, loads, or serves a collaborative artifact.
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

1. Build canonical binary CSR from eligible triples and validate shape, indices,
   duplicates, values, and resource limits.
2. Apply user, item, and pair support thresholds in a documented order.
3. Compute cosine similarity with sparse/bounded operations, remove self-edges,
   quantize, sort, and prune neighborhoods deterministically.
4. Serialize manifest, item/support metadata, sparse neighbors, similarity
   units, and pair support without pickle.
5. Add complete member checksums, exact member set, schema/code identity,
   aggregate diagnostics, build/lineage identity, data revision, consent policy,
   and validity horizon.
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
boundary and verified 2026-08-28. Phase 4 now consumes this boundary; API
orchestration, lifecycle readiness, response/event fields, and UI activation
remain later phases.

### Objective

Convert bounded source-game context and the validated artifact into
deterministic collaborative candidates and reconstructible evidence. Deliver the
work as independently testable slices so source selection, CSR lookup,
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

After 3A, the scoring branch (3B–3D) and materialization branch (3E–3F) could be
implemented in parallel while work within each branch remained sequential. Phase
4 started only after 3G passed, and no slice hid a failing earlier-slice test
behind orchestration fallback.

### Completed Slice Record

| Slice | Implemented boundary                                                    | Commit    |
| ----- | ----------------------------------------------------------------------- | --------- |
| 3A    | Frozen scoring contracts and Stage 3/4 characterization goldens         | `73b4528` |
| 3B    | Canonical immutable query-source selection                              | `7a57dcd` |
| 3C    | Bounded sparse CSR neighborhood lookup                                  | `5e25a64` |
| 3D    | Pure aggregation, exclusions, evidence, diagnostics, and typed outcomes | `844c695` |
| 3E    | Exact-row base/content/platform/popularity materialization              | `a5b755c` |
| 3F    | Exact-row feedback-affinity materialization                             | `d0b6676` |
| 3G    | Public handoff boundary, end-to-end fixture trace, and hardening        | `fa0ebd0` |

The final focused Phase 3 regression set passes 154 tests. The complete ML suite
passes 256 tests with one symbolic-link capability skip on the current Windows
host. Ruff lint, Ruff format check, privacy-string review, mutation and
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
3. A source absent from the artifact item axis is unsupported. A retained source
   row with no neighbor edges is supported but has no edge. Neither case
   fabricates a zero-similarity edge.
4. A candidate score is the round-half-up integer mean of all available stored
   `similarity_units` from supported query sources. The calculation uses integer
   or `Decimal` arithmetic only; it never converts stored units back through a
   binary float. Missing edges are absent from both numerator and denominator.
5. Every contributing edge is returned because the source count is already
   bounded. Edge evidence is ordered by similarity units descending, pair
   support descending, then source slug ascending. This preserves exact score
   reconstruction and avoids a separate lossy evidence cap; Phase 6 preserves
   the bounded returned edge set in the conditional UI evidence.
6. Query-source candidates are excluded first, then explicit dislikes. The
   scorer does not apply content eligibility, played state, wishlist state,
   hybrid weights, or top-K.
7. Candidate ordering is collaborative score units descending, then stable slug
   ascending. Artifact row/index order is never an ordering contract. With at
   most ten sources and one hundred retained neighbors per source, visited edges
   and returned candidates are each bounded by 1,000 before deduplication and
   exclusions.
8. Expected support outcomes are typed result reasons: `recommendations`,
   `no_query_sources`, `no_supported_sources`, `no_candidate_edges`, and
   `no_eligible_candidates`. Invalid input or an incompatible supposedly
   validated artifact is a typed contract error and returns no partial
   candidates. The scorer never performs fallback itself.
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

1. Implement one pure source-selection function over immutable positive feedback
   sources, saved-game slugs, and disliked slugs.
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

1. Add one integration test that builds and production-loads the Phase 2 fixture
   artifact, selects sources, scores collaborative candidates, checks
   catalog-fingerprint compatibility with the content artifact, and materializes
   the resulting exact slugs through 3E and 3F.
2. Prove a collaborative-only candidate can reach the Phase 4 handoff with exact
   collaborative, content, platform, popularity, base, and affinity units plus
   explicit empty content evidence where appropriate. Phase 4, not the scorer,
   owns candidate-union origin, weights, played adjustment, final rank, and
   fallback.
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

| Symptom                                        | Owning slice and first evidence to inspect                  |
| ---------------------------------------------- | ----------------------------------------------------------- |
| Wrong source present, missing, or capped       | 3B canonical source tuple and precedence tests              |
| Wrong neighbor, similarity, or pair support    | 3C source index, `indptr` slice, and raw edge list          |
| Wrong collaborative units, order, or exclusion | 3D edge sum/count, exclusion counters, and candidate golden |
| Existing content result changed                | 3E Stage 3 characterization diff                            |
| Existing personalized result changed           | 3F Stage 4 characterization diff                            |
| Collaborative-only slug cannot be joined       | 3G catalog fingerprint and exact-row handoff test           |

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
  affinity, and origin-ready membership; Phase 4 alone assigns union origin. The
  existing ranker wrappers remain unchanged.
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

**Implementation status:** Complete and verified on 2026-08-29 through slices
4A–4G. The implementation remains pure inside the ML package. Phase 5 now
provides lifecycle-backed readiness and internal API orchestration; Phase 6 now
provides the synchronized public response/event contract required to expose
hybrid output safely.

### Completed Slice Record

| Slice | Commit    | Verified outcome                                                                                              |
| ----- | --------- | ------------------------------------------------------------------------------------------------------------- |
| 4A    | `23132a0` | Frozen hybrid identities, modes, origins, weights, tie-breaks, fallback taxonomy, and typed contracts         |
| 4B    | `2447e26` | Reusable immutable Stage 4 ranking context with unchanged public Stage 4 behavior                             |
| 4C    | `d547e3f` | Stable-slug content/collaborative candidate union before final top-K                                          |
| 4D    | `6e3e181` | Fixed-point hybrid contributions, played adjustment, exclusions, and deterministic ordering                   |
| 4E    | `18e6ad4` | Reconstructible recommendation evidence and deterministic cautious prose                                      |
| 4F    | `8556744` | Public `HybridRanker` orchestration and exact Stage 4 fallback matrix                                         |
| 4G    | `10a5c79` | Production-loaded fixture handoff, frozen functional golden, determinism, immutability, and privacy hardening |

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

- No collaborative artifact, invalid artifact, stale artifact, unsupported user,
  and no-edge user each match Stage 4 items, scores, order, and evidence.
- Hybrid contributions sum exactly to pre-played units, and played delta sums
  exactly to final units.
- Collaborative-only candidates enter only through valid retained edges and
  cannot bypass exclusions.
- Tie cases resolve identically across runs and supported platforms.

### Exit Criteria

- The policy has a frozen identity and complete reconstructibility.
- Stage 3 and Stage 4 ranker golden tests remain unchanged and green.

## 12. Implementation Phase 5: Artifact Lifecycle, Readiness, and API Orchestration

**Status:** Complete and verified 2026-08-30 through slices 5A–5H.

### Objective

Load both artifacts safely, enforce collaborative privacy lineage at request
time, and keep content serving available through every optional-component
failure.

### Work

1. Add an optional collaborative artifact setting without changing
   `MODEL_ARTIFACT_PATH` or the existing content loader.
2. Load and validate the collaborative bundle once at service construction; do
   not hot-reload or mutate it.
3. Add content and collaborative component services behind explicit interfaces,
   then inject them into personalized orchestration.
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
  response. A new post-cutoff positive remains future snapshot input rather than
  silently changing the loaded artifact.
- Repointing configuration to a retired artifact cannot bypass database lineage
  or revision checks.
- The stateless route never queries collaborative lineage or changes behavior.

### Exit Criteria

- Component readiness is truthful and independently observable.
- Privacy or artifact invalidation takes effect immediately at the serving
  boundary while Stage 4 remains available.

### As-Built Phase 5 Slice Record

| Slice | Commit    | Independently completed boundary                                                                                                                   |
| ----- | --------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| 5A    | `0eab24f` | Load and freeze the optional collaborative artifact once; reject fixture use outside the explicit test gate.                                       |
| 5B    | `189ce4c` | Map immutable artifact and supplied lifecycle facts to one pure bounded readiness decision.                                                        |
| 5C    | `a6d7a34` | Add live build/contributor registry, aggregate count maintenance, and one-row readiness query.                                                     |
| 5D    | `fb7251f` | Enforce contributor authority and invalidate affected active builds transactionally on authority loss.                                             |
| 5E    | `4f52547` | Invalidate affected builds when an included positive label is removed or changes, while leaving post-cutoff additions for a future build.          |
| 5F    | `7e10882` | Extend model status additively with content/collaborative component state and regenerate the owned browser type.                                   |
| 5G    | `aefb425` | Orchestrate readiness, collaborative scoring, hybrid ranking, and every exact Stage 4 fallback reason.                                             |
| 5H    | `66af706` | Resolve one internal saved-ranking decision in the existing repeatable-read transaction while retaining the Stage 4 public response/event handoff. |

The implemented readiness states are `not_configured`, `fixture_only`,
`insufficient_data`, `unavailable`, `stale`, and `ready`. Lifecycle reasons are
`not_configured`, `fixture_not_allowed`, `insufficient_data`,
`artifact_missing`, `artifact_corrupt`, `artifact_incompatible`,
`artifact_stale`, `privacy_invalid`, `artifact_expired`, `catalog_stale`, and
`artifact_retired`. Scorer no-support reasons remain `no_query_sources`,
`no_supported_sources`, `no_candidate_edges`, and `no_eligible_candidates`.

The handoff gate passes 311 API unit tests, 98 disposable-PostgreSQL integration
tests, and 331 ML tests with one Windows symbolic-link capability skip. Ruff
lint and format pass across 165 Python files, generated OpenAPI types have no
drift, and Docker test resources are removed. Same-snapshot integration proves
that an in-flight request sees its original ready lineage, the next request
observes `privacy_invalid` or `artifact_retired`, and a readiness SQL failure
falls back as `artifact_incompatible` without aborting the exact Stage 4 event
commit.

At the Phase 5 exit boundary, the public saved response and recommendation event
intentionally remained Stage 4; exposing hybrid fields before their synchronized
contract would have created an incorrect event/API claim. Phase 6 now supersedes
that temporary public boundary.

## 13. Implementation Phase 6: Response, Event, OpenAPI, and Product Integration

**Status:** Complete and verified 2026-09-01 through slices 6A–6G.

### Objective

Expose the hybrid contract through the saved endpoint, preserve generated client
ownership, and present evidence without overstating meaning.

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
8. Keep model fingerprints and database lineage details out of ordinary UI prose
   even when they remain available in technical API identity.

### Phase 6 Implementation Handoff and Slice Order

Phase 6 starts from the immutable `PersonalizedRankingDecision` produced by
Phase 5. It must not recompute readiness or ranking after that decision, and it
must not derive the response and event through separate numeric paths. Public
contribution-consent routes are not an implicit prerequisite; they require a
separate approved product/privacy decision and may remain deferred while the
guarded fixture proves the response/event contract.

Each slice below should be independently reviewable, testable, and complete in
one commit:

| Slice | Complete implementation boundary                                                                                                                                                                                                                                      | Independent verification                                                                                                                                                                            |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 6A    | Freeze additive personalized response schemas for mode, fallback, hybrid policy/component identity, candidate origin, support, source edges, weights, contributions, and explanation evidence. Add pure schema/mapping characterization without activating the route. | Pydantic bounds, exact fixed-point serialization, hybrid/fallback goldens, no identity/prose leakage, and unchanged Stage 4/stateless schemas.                                                      |
| 6B    | Add the data-preserving event migration/model/repository contract for `stage-5-v1`, including all-or-none mode/component identity and bounded compact result fields while retaining `legacy-v1` and `stage-4-v1` rows.                                                | Empty/populated upgrade, downgrade/re-upgrade, constraints, retention/cascade compatibility, old-row readability, and no event-as-label/revision behavior.                                          |
| 6C    | Implement one pure decision projector that derives both response data and compact event data from the same `PersonalizedRankingDecision` and fixed-point records.                                                                                                     | Response/event equality and reconstruction for real hybrid plus all 15 fallback reasons; top-K/JSON bounds; deterministic ordering; no duplicate ranking call.                                      |
| 6D    | Activate the projector in `POST /api/v1/me/recommendations`, insert `stage-5-v1`, and preserve Stage 4 commit/ambiguous-outcome semantics.                                                                                                                            | One event per committed 200, zero event on every pre-commit failure, exact generation correlation, savepoint/fallback behavior, concurrent invalidation snapshot, and unchanged stateless endpoint. |
| 6E    | Regenerate OpenAPI and the project-owned TypeScript contract, then update client runtime parsing without adding handwritten parallel interfaces.                                                                                                                      | OpenAPI drift, strict TypeScript, malformed/unknown-field client cases, backward-compatible model status, and unchanged public request-only client behavior.                                        |
| 6F    | Render server-provided mode, neutral fallback, and conditional aggregate collaborative evidence in saved results without client sorting or score recomputation.                                                                                                       | Component tests for hybrid/fallback/loading/empty/error states, cautious copy, keyboard/focus/live-region behavior, and responsive/axe checks.                                                      |
| 6G    | Run the complete Phase 6 API/PostgreSQL/web contract matrix and record the handoff into lifecycle-command and full-stack phases.                                                                                                                                      | Full unit/integration/static/build/OpenAPI checks, focused privacy scan, deterministic replay, and only measured counts; browser E2E remains Phase 8 unless explicitly brought forward.             |

Implemented slice commits are `8c1c4f9`, `fe784e2`, `c2ddd2d`, `0bbdc58`,
`9ab9f68`, and `51664b5` for 6A–6F. Slice 6G is this verification and
documentation handoff. Public contribution-consent routes remain deferred
because no separate product/privacy approval was introduced.

Suggested commit subjects are
`feat(api): add stage 5 personalized response contract`,
`feat(api): persist stage 5 recommendation events`,
`feat(api): map stage 5 ranking decisions`,
`feat(api): activate stage 5 saved responses`,
`feat(web): consume stage 5 recommendation contract`,
`feat(web): present hybrid recommendation evidence`, and
`test: verify phase 6 contract handoff`.

### Verification

- OpenAPI drift fails when server and generated browser contracts diverge.
- A hybrid HTTP 200 commits exactly one matching `stage-5-v1` event; every known
  pre-commit failure commits none; ambiguous acknowledgement is not reported as
  success.
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

**Status:** Complete and verified on 2026-09-03 through slice 7H.

### Phase 7 Completion Handoff

Phase 7 advances the Alembic head from `0010_stage_5_event_contract` to
`0011_stage_5_lifecycle_guard` while preserving the immutable Phase 2 artifact
format, Phase 5 registry/readiness contracts, and Phase 6 response/event/browser
contract. It does not reopen ranking math, event meaning, or browser-side order.

The completed state remains fail-closed:

1. No public route grants collaborative contribution consent and no existing
   personalization consent may be reused for that purpose.
2. Guarded live build/registration requires separately enabled live-data,
   contribution-consent-version, promotion, build-ID, and exact-confirmation
   gates; default settings refuse before build work.
3. Explicit recovery, invalidation, retirement, rollback check, retirement
   preview, confirmed cleanup, and interrupted-filesystem recovery commands are
   implemented with bounded machine-readable output.
4. Phase 7 command tests use exact disposable database/artifact targets;
   ordinary startup, migration, seed, broad tests, and Compose teardown remain
   non-mutating with respect to derived artifacts.
5. Full guarded two-artifact browser lifecycle remains Phase 8. Phase 7 exposes
   deterministic command outcomes for that orchestration without hidden fitting,
   activation, or deletion.

| Slice | Completed boundary                                                                  | Commit    |
| ----- | ----------------------------------------------------------------------------------- | --------- |
| 7A    | Stable operator command contracts, explicit targets, confirmations, and safe errors | `03985e3` |
| 7B    | Eligible ephemeral lineage plus guarded immutable live build registration           | `23c2c62` |
| 7C    | Exact orphan-bundle registration recovery                                           | `b48aa41` |
| 7D    | Explicit idempotent invalidation and ordered terminal retirement                    | `f997b23` |
| 7E    | Identity-free retirement inventory and fingerprinted preview                        | `7b2bf74` |
| 7F    | Fresh-confirmation cleanup with protected paths and quarantine                      | `7740223` |
| 7G    | Previewed recovery for interrupted cleanup and stopped-builder remnants             | `0dc057d` |
| 7H    | Valid-only rollback, one-way DB guard, non-mutation, privacy, and lifecycle handoff | `3fabc72` |

### Objective

Make audit, build, activation, invalidation, retirement, and cleanup explicit,
reviewable operations with no hidden destructive side effect.

### Work

1. Implement separate `audit`, `build`, `validate`, and `inspect` subcommands
   with machine-readable output and stable exit codes.
2. Register a validated live-data build and its contributor lineage only through
   a deliberate promotion transaction.
3. Define crash recovery for the filesystem/registry boundary so neither an
   orphan registry row nor orphan bundle becomes serveable.
4. Mark affected builds invalid in the same transaction as label removal,
   consent withdrawal, revocation, or user deletion when application control
   exists; retain the cascade-maintained readiness state and source/build
   revision checks as defense in depth.
5. Add an artifact-retirement preview listing exact non-active paths and reasons
   without reading or displaying contributor identities.
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
- Preview/confirmation mismatch, path escape, active path, unregistered path, or
  non-disposable test target fails closed.
- Disposable tests prove withdrawal/deletion invalidation and confirmed cleanup
  without touching content artifacts or persistent development data.

The 7H handoff verifies the complete command sequence on disposable PostgreSQL
and temporary artifact sets: audit, two immutable live builds, validate/inspect,
valid rollback check, source revision advance, withdrawal or deletion
invalidation, failed resurrection, retirement preview, confirmation mismatch,
and confirmed cleanup. It also characterizes startup, migration, seed, and broad
test non-mutation. The final gate passes 782 combined API-unit/ML tests, 143
PostgreSQL integration tests, Ruff across 194 Python files, OpenAPI drift, privacy
output checks, and `git diff --check`.

### Exit Criteria

- Operators can explain and reproduce every artifact state transition.
- No invalidated live-data artifact can be served or silently resurrected.

## 15. Implementation Phase 8: Docker, Configuration, and Full-Stack Fixtures

**Status: IMPLEMENTED — VERIFIED (2026-09-09).** This section owns the
Phase 8 boundaries, completed slice ledger and acceptance contracts. Section 21
retains exact Docker/PostgreSQL/live-source/browser results, deviations and the
final documentation comparison. The combined gate is owned by `35082f2`; retained [8H evidence](evidence/stage-5-phase-8h.json) includes
502 API unit, 333 ML, 151 PostgreSQL, 86 web unit and 38 inherited browser passes,
18 fixture/fallback browser passes and 26 lifecycle phases per replay. Both
live/lifecycle replays passed on fresh projects. Host interruptions required a
resumed suffix, so this is not one uninterrupted combined process. Docker
Desktop Linux x86_64 was verified; native Windows/macOS artifact filesystems
and other architectures remain untested. Phases 9–10 remain separate gates.

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

### Phase 8 Boundary and Test Modes

The initial survey was performed on 2026-09-05 at `a1aab44`. The completed
implementation reuses Phases 5–7 loading, ranking, registry and operator guards;
it adds no migration, public contribution-consent feature, external dataset,
production approval, scheduler or deployment automation. Schema head remains
`0011_stage_5_lifecycle_guard`. The historical survey is retained in Git; the
as-built sources and reconciliation are recorded in Section 21.

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
by the original planning commit; completed-slice execution is recorded in Section 21.

### Phase 8 Completed Slice Record

| Slice | Depends on | Status | Implementation commit | Verification |
| --- | --- | --- | --- | --- |
| 8A | Verified Phase 7 | IMPLEMENTED — VERIFIED | `e19ea9f` | Configuration/command and Compose gates passed; see [Section 21](#as-built-phase-8-docker-and-fixture-decisions). |
| 8B | 8A | IMPLEMENTED — VERIFIED | `53c112b` | Guarded disposable PostgreSQL cohort gate passed; see [Section 21](#as-built-phase-8-docker-and-fixture-decisions). |
| 8C | 8A | IMPLEMENTED — VERIFIED | `44d070d` | Two-artifact fixture topology passed two fresh deterministic runs; see [Section 21](#as-built-phase-8-docker-and-fixture-decisions). |
| 8D | 8C | IMPLEMENTED — VERIFIED | `7f8cf1b` | Real hybrid Chromium and cross-browser smoke passed; see [Section 21](#as-built-phase-8-docker-and-fixture-decisions). |
| 8E | 8C | IMPLEMENTED — VERIFIED | `4711979` | Full optional-component fallback matrix and browsers passed; see [Section 21](#as-built-phase-8-docker-and-fixture-decisions). |
| 8F | 8B, 8C | IMPLEMENTED — VERIFIED | `4769d5d` | Disposable PostgreSQL/live-source gate passed; see [Section 21](#as-built-phase-8-docker-and-fixture-decisions). |
| 8G | 8D, 8E, 8F | IMPLEMENTED — VERIFIED | `693808f` | Six isolated live lifecycle scenarios passed; see [Section 21](#as-built-phase-8-docker-and-fixture-decisions). |
| 8H | 8A–8G | IMPLEMENTED — VERIFIED | `35082f2` | Combined gate, isolation, fault teardown and two clean replays passed; see [Section 21](#as-built-phase-8-docker-and-fixture-decisions). |
| 8I | Passing 8H | IMPLEMENTED — VERIFIED | `d0e86f9` | Documentation comparison and focused docs gates passed; see [Section 21](#as-built-phase-8-docker-and-fixture-decisions). |

Implementation followed the dependencies above. Fixture builders and live
registry checks passed before their browser gates. The content-only route
remains independently runnable. Section 18 lists the exact Make and direct
runner commands. Each slice's acceptance contract is preserved below; measured
execution and historical limitations are recorded in Section 21.

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

**Status: IMPLEMENTED — VERIFIED (2026-09-09).** Depends on 8A–8G.

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

**Status: IMPLEMENTED — VERIFIED (2026-09-09).** Depends on passing 8H.

- Scope: documentation only; one separate final docs commit (completed as `d0e86f9`). Reconcile against
  the committed implementation and retained run evidence, not this plan's intended
  filenames, commands, or anticipated outcomes.
- Required comparison inventory:

  | Documents | Compare with |
  | --- | --- |
  | Root/API/ML/web/infra READMEs and `scripts/README.md` | Actual wrappers and direct CLI parsers; working directory/shell syntax; topology, mounts, explicit setup/build/validation, scenario selection, failure/teardown behavior |
  | `data/README.md`, `data/fixtures/README.md` | Exact synthetic cohort provenance, JSON-vs-database source distinction, eligibility/authority, output privacy and fixture isolation |
  | `docs/architecture.md`, `docs/data-model.md`, `docs/recommendation-design.md` | Actual component loading, registry/invalidation, one-time artifact selection, unchanged schema head and scoring/response/event contracts |
  | `docs/roadmap.md`, parent plan Sections 15, 18, 21–23, and the Phase 8 slice ledger below | Measured Phase 8 completion, exact commits/commands/deviations, remaining Phase 9/10 gates, provisional Stage 6 handoff |
  | Configuration descriptions throughout docs | Actual `.env.example`, Settings, Compose values, frozen ML constants; no stale “serving does not load it yet”, fictional limits, or missing gate descriptions |

- For each item, record corrected or reviewed/no-change with a source reference.
  Configuration fixes belong in the owning implementation slice before 8H; do not
  silently change configuration in this docs-only commit. Keep Stage 5 completion
  and parent Section 23 pending; Phase 8 does not finalize Stage 6 evidence.
- Gate: check local links, formatting, `git diff --check`, commands against parser
  and runner definitions, and every numerical claim against logs. Replay changed
  command instructions only when the recorded 8H invocation does not establish
  their correctness. No new live-source build solely to edit prose.

## 16. Implementation Phase 9: Test Matrix and Quality Gate

**Status: IN PROGRESS (2026-09-09).** Slices 9A (inventory) and 9B (synthetic snapshot/provenance checks) are complete;
9C–9L and Phase 10 remain planned and unstarted. The original survey below is
historical planning evidence. 9A changes only documentation and inventory data;
no runtime test, migration, configuration, dependency or live-build change is
included. Phase 8 is complete; the Phase 9 runtime/release gates remain pending.

### Objective

Prove Stage 5 functional correctness, determinism, privacy, failure semantics,
and regression safety without performing Stage 6 quality evaluation.

### Work

1. Build focused suites for every contract below and keep fixtures small enough
   for exact expected values.
2. Run diagnostic coverage only to find untested branches; do not optimize for a
   number at the expense of behavior.
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
- Explicit proof that recommendation events, views, played-only, wishlist-only,
  and unknown rows are never positives.
- Aggregate-only audit, insufficiency reasons, catalog alignment, and no
  identity in output.

### Collaborative ML suite

- Hand-calculated binary CSR, item support, pair support, cosine, quantization,
  diagonal removal, threshold order, top-neighbor pruning, and stable ties.
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
- Request-wide missing-edge behavior and collaborative-only materialization with
  zero/empty content evidence and exact remaining base components.

### Artifact and lifecycle suite

- Exact members, checksums, dtypes, shapes, canonical CSR, limits,
  compatibility, catalog fingerprint, interaction fingerprint, build ID,
  revision, lineage, validity horizon, immutable arrays, and path safety.
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

### Phase 9 Survey Baseline and Boundaries

Surveyed clean commit `47d132b` on
`feat/stage-5-collaborative-and-hybrid-ranking`. Phase 8 implementation evidence
belongs to `35082f2`, documentation reconciliation to `d0e86f9`, and the subsequent
plan consolidation to `47d132b`. The [8H record](evidence/stage-5-phase-8h.json)
is historical evidence, not a new Phase 9 run or a coverage/security certificate.
No `AGENTS.md` was found in the repository during this survey.

| Existing implementation and tests inspected | Consequence for Phase 9 |
| --- | --- |
| [Snapshot repository](../apps/api/app/repositories/collaborative_snapshot.py), `test_stage_5_collaborative_snapshot.py`, `test_interaction_snapshot.py` | PostgreSQL cutoff, repeatable-read extraction, authority, label precedence and revision-race tests already exist. Map exact assertions before adding missing boundaries; SQLite or mocks cannot prove database isolation. |
| [Collaborative training](../ml/src/gamelens_recommender/collaborative_training.py), `test_collaborative_training.py`, `test_collaborative_artifacts.py` | Hand-calculated cosine, sparse caps, stable pruning, reordered-input determinism, malformed bundle and promotion-race coverage already exist. Extend gaps instead of rebuilding the pipeline. |
| [Hybrid policy](../ml/src/gamelens_recommender/hybrid.py), `test_hybrid_ranker.py`, `test_phase4_handoff.py` | The contract has 11 unavailable plus 4 no-support reasons. Exact Stage 4 fallback and functional golden traces exist; the seven fixture-browser fallback reasons are a different, narrower matrix. Reconcile all 15 reasons across layers. |
| [Build service](../apps/api/app/services/collaborative_build.py), registry/lifecycle services and `test_stage_5_live_build_promotion.py`, `test_stage_5_lifecycle_handoff.py` | Real PostgreSQL-derived build, retained lineage, revision races, orphan recovery, concurrent promotions and ordinary-operation nonmutation already have integration tests. Live fixtures are needed to prove this boundary. |
| [Decision projection](../apps/api/app/services/recommendation/projection.py), response/event unit suites and `test_stage_5_recommendation_events.py` | Shared response/event projection and populated migration checks exist. Prove commit acknowledgement, exact units, bounded payloads and inherited event retention without changing contracts. |
| [Web test scripts](../apps/web/package.json), [Playwright projects](../apps/web/playwright.config.ts), hybrid/fallback/lifecycle specs | Unit/V8 coverage, Chromium and Firefox/WebKit smoke routing, keyboard/focus/axe/responsive checks already exist. Audit mode-specific skips and actual scenario selection, not just a green process exit. |
| [Makefile](../Makefile), [Phase 8 runner](../infra/run-phase8.py), E2E wrappers and ownership helper | Reuse the current explicit build/isolation/replay workflows. `test-phase8` exists; no Phase 9 runner or `test-phase9` target exists at this baseline. The runner does not collect Phase 9 diagnostic coverage or current dependency/license/vulnerability evidence. |
| [API coverage settings](../apps/api/pyproject.toml), [ML coverage settings](../ml/pyproject.toml), [V8 settings](../apps/web/vitest.config.ts), Dockerfiles and locks | Diagnostic tooling and package checks exist. Old percentages, audits and image findings must not be reused as current results. Measure scope explicitly; generated web types are excluded from V8 instrumentation and checked separately. |

This is a static survey, not a claim that an unexecuted test passes or that a
named suite exhausts a contract. The first slice creates the assertion-level
inventory; later slices add only demonstrated gaps or a regression for a
reproduced defect. Preserve the current schema head
`0011_stage_5_lifecycle_guard`, model/policy identities and default-off gates.
Any necessary implementation correction belongs to its owning future slice,
with a failing reproducer and focused verification, never this planning commit.
A schema, consent-product, ranking-policy or broad dependency redesign requires
an explicit plan revision before implementation; it is not incidental gate work.

Public contribution grant/re-consent/withdrawal routes and approval of an actual
user cohort remain unresolved in Section 21. Private synthetic lifecycle helpers
do not implement those product routes. The matrix must distinguish verification
of default-off/decline behavior, a documented fixture-only scope decision, and
blocked production authority. No applicable acceptance item may disappear under
an unexplained `N/A`; Phase 9 cannot silently authorize real-user training or
finalize Stage 5 while required release decisions remain unresolved.

### Phase 9 Slice Ledger and Dependency Order

Slices **9A and 9B are COMPLETE** within their inventory and synthetic extraction
scopes; **9C–9L remain PLANNED — NOT IMPLEMENTED**. Production authority and
final release evidence remain blocked/pending. Each slice ends with
**one commit** containing its bounded work, focused checks and truthful ledger
update. The original planning commit `f4d9be7` is separate from 9A completion.
The remaining suggested subjects are future commit messages, not existing commits.

| Slice | Depends on | Deliverable / suggested commit subject |
| --- | --- | --- |
| 9A (COMPLETE) | Completed 8I and this plan | Acceptance-to-test inventory — `docs(test): map stage 5 acceptance gates` |
| 9B (COMPLETE) | 9A | Snapshot/provenance boundary gaps — `test(api): close snapshot and provenance gaps` |
| 9C | 9A | Sparse math and pure scorer gaps — `test(ml): close collaborative numeric gaps` |
| 9D | 9C | Hybrid/fallback matrix and five-baseline diagnostic — `test(ml): verify hybrid and baseline diagnostics` |
| 9E | 9A | Bundle rejection and operator safety gaps — `test: harden collaborative artifact safety gates` |
| 9F | 9B, 9E | PostgreSQL lineage, promotion and lifecycle gates — `test(api): verify registered lifecycle boundaries` |
| 9G | 9D, 9F | API/OpenAPI/event transaction agreement — `test(api): verify stage 5 response and event truth` |
| 9H | 9G | Web and browser acceptance matrix — `test(web): complete stage 5 browser matrix` |
| 9I | 9B–9H | Diagnostic coverage and gap disposition — `test: record stage 5 diagnostic coverage` |
| 9J | 9A; final lock/image/diff after 9I | Dependency, security, privacy and license review — `chore(quality): verify stage 5 release inputs` |
| 9K | 9I, 9J and all earlier gates passing | Combined clean regression and repeatability evidence — `test: record stage 5 phase 9 quality gate` |
| 9L | Passing 9K | Final phase docs comparison — `docs: reconcile phase 9 verification and handoff` |

Recommended commit order is 9A through 9L. Dependency independence means 9B,
9C and 9E can each be implemented and debugged with their own fixture and focused
command after 9A; it does not require parallel execution. 9J inventory can start
after 9A, but its final scan must use the resulting locks, images and code.
9K is the first mandatory combined rerun, rather than a prerequisite for every
small slice. On failure, reproduce the smallest test/scenario, fix the owning
boundary, rerun that gate and impacted dependents before continuing. Do not
bundle unrelated failures into a slice or relax an assertion to obtain green.
If a completed slice needs a later repair commit, add and name that repair slice
in the ledger instead of hiding it or rewriting the meaning of its old evidence.

### 9A — Acceptance Inventory and Evidence Contract

**Status: COMPLETE — INVENTORY VERIFIED (2026-09-09).** Based on completed 8I
`d0e86f9`, consolidation `47d132b` and clean planning parent `f4d9be7`.

The [acceptance inventory](stage-5-acceptance-inventory.md),
[canonical route data](evidence/stage-5-acceptance-inventory.json) and
[static verification record](evidence/stage-5-phase-9a.json) map all 47 Section 19
bullets, all 22 Section 16 suite bullets, 171 inherited Stage 1–4 acceptance
bullets through ten gate families, and all 15 fallback reasons. Existing
assertions are not marked as freshly passed;
public contribution routes/actual cohort authority and later-slice evidence
remain explicitly absent or blocked. No test implementation, PostgreSQL, Docker
or live build was needed. The single owning commit hash is reported after
creation, not invented here; 9B and subsequent slices are unstarted.

- Scope: docs/test inventory only. Give every Section 19 bullet a stable ID and
  retain its wording; map all Section 16 suite requirements and inherited Stage
  1–4 gates to those IDs. Record owner slice, implementation path, exact test
  node or named manual review, fixture mode, command, expected assertion,
  evidence location and current gap/status. Distinguish existing-but-not-rerun,
  missing, blocked and subsequently verified evidence.
- Specifically enumerate all 15 `HYBRID_FALLBACK_REASONS`, their producing layer
  and applicable ML/API/browser checks. Browser selection need not duplicate
  every pure policy case, but each omitted browser case needs an explicit lower
  layer test and rationale. Record absent public contribution routes as absent.
- Acceptance: every acceptance bullet has an owner and evidence route; no
  orphan, blanket pass, unexplained skip or implied Phase 8 carryover. Freeze
  the command/evidence convention below and the functional comparison scope.
- Verify: compare inventory against Section 19 and source/test assertions,
  resolve all linked paths/test names, check Markdown and `git diff --check`.
  No test implementation or live build is needed for this slice.

### 9B — Snapshot, Authority and Label Provenance

**Status: COMPLETE — SYNTHETIC EXTRACTION VERIFIED (2026-09-09).** Depends on
9A `9478e27`. [9B evidence](evidence/stage-5-phase-9b.json) records exact commands,
results, candidate hashes and M01 source review. Added only missing snapshot,
authority, label, aggregate audit and error-contract assertions. No production
code, schema, policy or dependency changes were needed. Public contribution
routes remain absent and actual cohort approval remains blocked; completion of
this bounded slice does not close those Stage 5 release decisions.

Focused ML/API/config: **35 passed**; PostgreSQL snapshot file: **59 passed**;
existing public-consent separation gate: **1 passed**. No skips. Ruff lint and
format checks pass across 207 files; owned Docker projects are removed with no
container/network leftovers. Exact cutoff tests use database-derived recovery
time and microsecond offsets; race tests use committed independent transactions.
Audit state comparisons include all application columns and revision/registry
rows for empty, positive and catalog-mismatch cases. Review removed a redundant
invalid-settings test (configuration already rejects it), reused its existing
assertion and corrected test-file line endings. No application defect found.
No live build, web build or next-slice work was required or started. The single
owning commit hash is reported after creation, not embedded self-referentially.

- Scope: `ml/tests/test_interaction_snapshot.py`, API snapshot repository/command
  unit tests and `tests/integration/test_stage_5_collaborative_snapshot.py`.
  Reuse the guarded disposable PostgreSQL cohort; add only missing cases.
- Acceptance: one database-time repeatable-read cutoff; exact as-of temporal
  boundary, rating threshold, dislike precedence, positive saved-game preference
  and duplicate-source collapse. Consent version/grant/withdrawal/revocation,
  expiry/horizon, deletion, post-cutoff changes and revision races fail closed.
  Events, views, played-only, wishlist-only, unknown and nonpositive rows never
  create an edge. Audit remains read-only, bounded, aggregate-only and truthful
  on insufficiency/catalog mismatch; compare database state before and after.
- Verify: focused snapshot ML/API unit files, then the named PostgreSQL file
  through the integration command below. Use synchronization/transaction
  boundaries for race tests, not timing sleeps. A real database is required;
  a collaborative live build is not required for extraction-only assertions.

### 9C — Collaborative Sparse Math and Pure Scoring

**Status: PLANNED — NOT IMPLEMENTED.** Depends on 9A.

- Scope: `ml/tests/test_collaborative_{contracts,training,sources,lookup,scorer,pipeline}.py`
  and `test_phase3_handoff.py`; reuse small project-authored inputs and the pure
  training/scoring APIs. Brace notation here denotes a file family, not a
  literal PowerShell command argument.
- Acceptance: hand-derived binary CSR, item/pair support, cosine, quantization,
  diagonal removal, threshold/pruning order and stable tie-breaks match exact
  values. Exercise empty/single-user/single-item, duplicate/invalid/non-finite,
  maximum/over-limit inputs and sparse resource guards before allocation.
  The scorer is pure and identity-free, excludes sources/dislikes and reports
  unsupported sources/items/pairs without fabricating scores.
- Verify: selected ML files, then the full ML suite; compare two canonical-input
  permutations and repeated small fixture builds by semantic arrays/identities.
  Expected arithmetic must be independently derived, not copied from the
  production function under test. Temporary fixture builds only; no PostgreSQL
  or live build.

### 9D — Hybrid Matrix and Functional Baseline Comparison

**Status: PLANNED — NOT IMPLEMENTED.** Depends on 9C.

- Scope: existing `test_hybrid_*.py`, `test_phase4_handoff.py` and a small
  reviewable synthetic diagnostic table/output. Extend existing Stage 4/hybrid
  golden traces to explicitly cover popularity, content, feedback,
  collaborative and hybrid candidates/components/ranks. Define each diagnostic
  variant's candidate universe, exclusions and tie-breaks; reuse current policy
  functions without adding product endpoints or new learned baselines.
- Acceptance: all 15 fallback reasons preserve the exact Stage 4 result, order,
  scores and evidence while the Stage 5 envelope truthfully identifies fallback.
  Check collaborative-only union/materialization, exclusions before top-K,
  cold/mixed/empty/tied cases, request-wide missing-edge behavior, active weights,
  fixed-point reconstruction, one played factor, neutral wishlist and no double
  counting. Invalid input/context remains an error rather than silent fallback.
  The five-variant comparison explains differences using exact components and
  makes no Precision/Recall/NDCG, tuning or superiority claim.
- Verify: focused hybrid/handoff tests, full ML suite and two deterministic
  diagnostic runs. Retain only synthetic aggregate/game-level evidence. No
  live build; fixture artifacts are sufficient.

### 9E — Artifact Validation and Operator Failure Safety

**Status: PLANNED — NOT IMPLEMENTED.** Depends on 9A.

- Scope: `ml/tests/test_collaborative_artifacts.py` and API unit suites for
  artifact command/entrypoint, build, recovery, rollback, retirement, readiness
  and lifecycle handoff safety. Keep filesystem/CLI fault tests independent
  from the registered PostgreSQL scenarios owned by 9F.
- Acceptance: exact members/checksums/dtypes/shapes, canonical sparse semantics,
  metadata identities/fingerprints/limits, immutable arrays and safe paths.
  Missing/corrupt/extra/incompatible/stale/expired/retired/privacy-invalid
  bundles cannot become ready. Verify symlink/traversal refusal, no overwrite,
  promotion failure cleanup, read-only validate/inspect/preview/rollback-check,
  matching destructive confirmations and bounded errors. No identity-bearing
  snapshot or executable pickle may survive success or failure.
- Verify: focused loader and operator unit tests with temporary roots and
  injected faults, followed by the affected ML/API unit suites. A mocked
  registration is unit evidence only; actual rollback/recovery and lineage
  acceptance wait for 9F. No live build needed here.

### 9F — PostgreSQL Migrations and Registered Lifecycle

**Status: PLANNED — NOT IMPLEMENTED.** Depends on 9B and 9E.

- Scope: existing Stage 4 migration and Stage 5 registry, authority/label
  invalidation, lifecycle guard/handoff, live-build promotion, operator,
  rollback-check and retirement integration suites. Use the reusable
  `tests/fixtures/collaborative_lifecycle.py` helper and disposable database.
- Acceptance: populated upgrade/downgrade/re-upgrade preserves data expected
  at each revision, constraints/cascades/catalog and current head; event-column
  migration payload detail remains owned by 9G. Prove retained contributor count,
  lineage/revision/authority/horizon checks, concurrent mutation/promotion,
  registration failure/orphan recovery, valid-only rollback, preview/retire/cleanup
  boundaries and no resurrection after deletion, withdrawal or expiry. Ordinary
  startup, migration, seed and non-lifecycle tests preserve registered state and
  artifact bytes. Re-consent never reactivates an invalidated old build.
- Verify: focused PostgreSQL files first, then the complete integration suite
  and `sh infra/run-e2e-live-source.sh`. A real live-source build/register/validate
  cycle is **required**, exclusively from synthetic rows in the guarded
  disposable database. Capture aggregate lineage and mutation/recovery evidence;
  fixture JSON or hand-inserted registry rows alone cannot satisfy this gate.

### 9G — API, OpenAPI and Committed Event Truth

**Status: PLANNED — NOT IMPLEMENTED.** Depends on 9D and 9F.

- Scope: API `test_stage_5_{decision_projection,response_contract,recommendation_event_contract}.py`,
  personalized/hybrid/model-status unit suites, Stage 4 OpenAPI tests, and
  Stage 5 recommendation-event/model-status/orchestration integration files.
- Acceptance: additive model status and unchanged cookie-agnostic, read-only
  stateless route; truthful hybrid/fallback identity and readiness. Every
  acknowledged saved HTTP 200 has exactly one matching event; pre-commit failure
  has none, and ambiguous commit acknowledgement is never success. Response and
  event share exact model/data/policy identities, units and ordering; bounded
  strict JSON, old event compatibility, populated event migrations, retention
  and deletion cascades pass. Required-content failure returns 503 with no event;
  optional failure preserves content and exact Stage 4 ranking behavior.
- Verify: named unit/integration suites and read-only `npm run api:types:check`
  against the disposable running API. Real registered hybrid/invalidation
  scenarios must build live synthetic artifacts; projection/schema/typed-error
  unit cases need no live build. Do not hand-edit generated browser types or
  refresh them merely to suppress drift; investigate the contract first.

### 9H — Web, Browser and Accessibility Matrix

**Status: PLANNED — NOT IMPLEMENTED.** Depends on 9G.

- Scope: generated/client and recommendation-flow/result unit tests, existing
  catalog/persistence/recommendation browser specs, hybrid/fallback fixture specs
  and `lifecycle.live.smoke.spec.ts`. Extend only demonstrated browser gaps.
- Acceptance: server order and evidence are preserved without client ranking;
  positive applied contribution controls explanation. Neutral fallback, no social
  proof, safe errors, loading/empty state, stale-response cancellation,
  request-only opt-out, saved rehydration, re-consent, expiry, invalidation and
  clear-data boundaries work. Product consent and private contribution helper
  evidence stay distinct. Verify keyboard, focus, live announcements, no
  serious/critical axe violations and responsive layouts. Record actual
  Chromium and critical Firefox/WebKit scenarios, plus justified mode skips;
  a skipped required scenario is not a pass.
- Verify: web unit/type/lint/format/build checks, followed by
  `sh infra/run-e2e-content.sh`, `sh infra/run-e2e-fixture.sh` and
  `sh infra/run-e2e-lifecycle.sh`. Debug a single spec/project/phase first, then
  rerun the owning wrapper. Fixture UI checks do not need live builds;
  registered lifecycle browser transitions **do**. Keep failure media private
  until scanned; screenshots alone cannot prove response/event agreement.

### 9I — Diagnostic Coverage and Uncovered Branch Review

**Status: PLANNED — NOT IMPLEMENTED.** Depends on 9B–9H.

- Scope: existing pytest-cov and V8 tooling; record measured API/ML/web scope,
  branch/line/statement denominators as applicable, excluded/generated code and
  meaningful uncovered failure paths. Distinguish unit, PostgreSQL and browser
  evidence; do not label unit-only coverage as full application coverage.
- Acceptance: each important uncovered boundary maps to an existing integration/
  browser assertion, a focused new regression, or an explicit blocker. No new
  arbitrary percentage threshold or tests that mirror implementation. Coverage
  output must identify the actual executed modules: container ML installation
  versus mounted source matters. Keep raw reports/caches out of Git and scan
  sanitized summaries for local paths, identities and credentials.
- Verify: API `--cov=app --cov-branch`, ML
  `--cov=gamelens_recommender --cov-branch` with `--cov-report=term-missing`, and
  web `npm run test:coverage`. Use separate output files/runs to prevent accidental
  overwrites; verify collection and exclusions before interpreting numbers.
  If PostgreSQL coverage is collected, explicitly opt into its disposable suite;
  selected live-build tests still require real synthetic builds. No live build
  merely to generate unit/V8 reports. Rerun affected gates after any gap fix.

### 9J — Dependency, Security, Privacy and Release Input Review

**Status: PLANNED — NOT IMPLEMENTED.** Depends on 9A for inventory and the final
9I code/lock/image state for closure.

- Scope: API/ML pyprojects and locks, web package/lock/overrides, Docker base and
  built images, ignore/build-context rules, configuration descriptions and the
  Stage 5 release diff. Separate direct/transitive Python/Node packages, OS image
  packages, tooling licenses and dataset provenance; UCSD remains read-only
  preflight, not approved training input.
- Acceptance: clean locked installs, Python package integrity/runtime imports,
  full and production npm audits, current Python and image vulnerability scans,
  and license/attribution review have explicit scope, versions, timestamps and
  dispositions. Freeze scanner commands/versions before execution; unavailable
  scanners/advisory feeds or unknown licenses remain incomplete, not clean.
  No unresolved actionable security, privacy, identity, isolation or data-loss
  failure may be waived by an old Phase 4/8 result. Record non-actionable findings
  with evidence and residual limitations, never an unqualified zero-risk claim.
- Verify: `python -m pip check`, imports in the actual API/ML runtime, clean
  `npm ci`, `npm audit` and `npm audit --omit=dev` in a disposable web environment;
  named Python/image scanners selected and recorded in this slice. Inspect
  final source/lock/generated-file diff and runtime outputs, snapshots, artifact
  members, logs, browser state/media, coverage, caches and environment files for
  credentials/internal user identities/raw interaction payloads. Retain safe
  metadata only. No collaborative live build is needed for scanning; Docker/web
  production builds are separate checks. Any dependency remediation must be
  bounded and rerun affected gates before 9K; broader upgrades need a named slice.

### 9K — Combined Clean Quality Gate and Replay

**Status: PLANNED — NOT IMPLEMENTED.** Depends on passing 9I and 9J, with all
earlier slices closed against the candidate implementation.

- Scope: compose existing commands into an explicit Phase 9 runbook. Reuse
  `python infra/run-phase8.py` for its implemented combined isolation checks,
  including two clean live/lifecycle replays; add the 9A inventory, five-baseline
  diagnostic, coverage and current security/license gates it does not own. Do
  not rename historical Phase 8 evidence or claim a nonexistent Phase 9 target.
  A new wrapper is optional only if command gaps justify it and is implemented
  and tested explicitly in this future slice, never hidden inside ordinary tests.
- Acceptance: all Stage 5 and complete Stage 1–4 suites pass, plus Ruff,
  strict TypeScript, ESLint, Prettier, production build, live OpenAPI drift,
  dependency/runtime and every Compose mode check. Verify non-root services,
  read-only artifact mounts, project ownership/isolation, ordinary-operation
  nonmutation and teardown on success/setup/validation/browser/signal failure.
  Two fresh synthetic replays must match semantic artifact/order evidence;
  database-time cutoffs/build IDs may differ and must not be falsely compared
  as identical full live bundle bytes. Recheck exact response/event agreement.
- Verify: run the frozen complete manifest on a clean candidate tree with
  explicit disposable project IDs. Retain actual counts/skips/durations, runtime
  and image identities, hashes/sizes, aggregate lineage/event diagnostics and
  teardown results. Current security scans must identify these same locks/images.
  Resume interruptions with exact provenance and preserved failures; do not
  describe a resumed run as uninterrupted. Required platform/coverage/matrix
  gaps block completion; additional untested platforms remain explicit limits.
  Real synthetic live builds are **mandatory** at this final integration gate.

### 9L — Final Documentation Comparison and Phase Handoff

**Status: PLANNED — NOT IMPLEMENTED.** Depends on passing 9K.

- Scope: one docs-only commit comparing the final implementation and retained
  Phase 9 evidence against the inventory below. Record each row as corrected or
  reviewed/no-change with exact source/evidence reference; do not simply copy
  planned outcomes into an as-built section.

  | Required documentation | Compare against |
  | --- | --- |
  | Root, API, ML, web, infra and scripts READMEs | Actual Make/package scripts, CLI parsers, runners, shell/working directory, fixture modes, build/validate order, expected exits, teardown and measured gates |
  | Data, fixture and external-source READMEs | Synthetic versus PostgreSQL-derived source, consent/authority, thresholds, lineage, privacy and unchanged external-source restrictions |
  | Architecture, data model and recommendation design | Actual loading/readiness, registry/invalidation, migration head, fallback, model/policy and response/event semantics |
  | Roadmap; Stage 5 Sections 15–19 and this slice ledger | Phase 8 historical evidence, Phase 9 actual completion/commits, per-criterion outcomes, direct commands and remaining Phase 10 work |
  | Stage 5 Sections 21–23 | Measured decisions, deviations, known blockers and evidence provenance; Stage 6 handoff and Stage 5 completion remain pending until Phase 10 and all applicable acceptance gates close |
  | Configuration and dependency descriptions across these docs | Actual `.env.example`, Settings, Compose/Dockerfiles, pyprojects/locks, package scripts and frozen constants; no fictional toggle, stale version or expanded product consent claim |

- Acceptance: all numerical claims trace to the exact tested revision/logs;
  historical results retain their labels; no planned command/field is described
  as implemented. All 9A rows have final dispositions, with unresolved required
  work blocking closure. Record what Phase 10 must still finalize rather than
  converting Sections 22–23 into a premature release certificate.
- Verify: local links/anchors, Markdown formatting, command/parser/runner
  equality, evidence totals/provenance, `git diff --check` and staged docs-only
  review. No new live build for prose reconciliation. If a corrected command
  is not covered by 9K evidence, replay its smallest real workflow; a discovered
  implementation/configuration defect returns to an owning repair slice and
  affected gates before this docs commit can close.

### Execution Modes, Commands and Live-Build Checkpoints

The commands below are existing entry points for **future implementation**,
not commands executed by this planning change. Run from the repository root
unless noted. Use `sh` for shell wrappers (Git Bash/POSIX shell on this Windows
host); Make recipes with POSIX environment assignments are not native
PowerShell syntax. Avoid using the development database or artifact directory.

| Gate | Existing command / execution rule |
| --- | --- |
| Focused API unit | `docker compose run --build --rm --no-deps quality python -m pytest tests/unit/<actual-test-file>.py -q -p no:cacheprovider`; substitute a real inventory file/node |
| Focused ML | `docker compose run --build --rm --no-deps quality python -m pytest /workspace/ml/tests/<actual-test-file>.py -q -p no:cacheprovider`; rebuild the image after ML source changes |
| Full fast suites | `make test`, `make test-ml`, `make lint`; direct Docker equivalents are in the Makefile and READMEs |
| Focused PostgreSQL | Use `docker compose --project-name <unique-test-project> -f infra/docker-compose.test.yml run --build --rm test-api python -m pytest --run-integration -m integration tests/integration/<actual-test-file>.py -q -p no:cacheprovider`; service dependency starts guarded test-db. Always remove this exact owned project in a finally/trap path and verify no leftovers. No fallback to `DATABASE_URL` from development |
| Full PostgreSQL | Same owned-project command using `tests/integration`, or the combined runner's integration gate; preserve `--run-integration -m integration` and the existing reset guards |
| Web | From `apps/web`, existing `typecheck`, `lint`, `format:check`, `test`, `test:coverage`, `build`, `api:types:check` npm scripts; use the documented test API URL/consent environment. Drift check requires a reachable disposable API and remains read-only |
| Browser / fixture / live / lifecycle | `sh infra/run-e2e-content.sh`, `sh infra/run-e2e-fixture.sh`, `sh infra/run-e2e-live-source.sh`, `sh infra/run-e2e-lifecycle.sh`; use each wrapper's ownership/teardown and mode guards |
| Combined infrastructure base | `python infra/run-phase8.py` (`make test-phase8` equivalent); Phase 9 adds the inventory, diagnostics and current release-input reviews, not implicit training in `make test` |

Here **live build** means the explicit database extractor -> sparse builder ->
immutable artifact -> PostgreSQL registry/lineage -> validation/readiness path
with `source_kind=live`. It is still project-authored synthetic test data, not
an approved real/local user cohort. A JSON fixture build, Docker image build,
Next.js production build or running API is not evidence of that path.

- **Not required:** this planning commit, 9A, 9B extraction-only checks, 9C,
  9D, 9E, unit/V8-only 9I, 9J scans and evidence-backed 9L prose edits.
- **Required:** 9F registered lifecycle gate, 9G real registered
  hybrid/invalidation integration scenarios, 9H lifecycle browser scenarios,
  and 9K clean live-source/lifecycle replay. 9I needs it only if collecting
  coverage from tests which themselves exercise live building.
- Audit the guarded disposable cohort first, build to a new immutable path,
  register and validate before selecting the artifact for API startup. Rebuild
  when testing a new post-mutation cohort/lineage; restarting, re-consenting or
  toggling readiness is not a rebuild. Deliberate corrupt/invalidated cases must
  remain unavailable instead of being repaired automatically by test setup.
- Ordinary unit/web commands, request handling, startup, migrations, catalog
  seed and teardown never acquire an implicit train/promote capability. An
  explicitly selected lifecycle test may build its isolated test artifacts;
  teardown removes only proven-owned disposable resources.

### Per-Slice Commit and Evidence Rules

For each future slice, record its dependency revisions, files changed, exact
commands/working directory and fixture mode, expected/actual exits, observed
test counts/skips and duration, evidence path/hash, findings/fixes and remaining
limitations. A slice with no demonstrated missing tests can close with a
documentation/evidence commit after its focused gates pass; do not add empty
tests just to satisfy a suggested `test:` subject. Never commit a failing gate
as verified or fill future result cells with expected counts.

9K should retain a sanitized machine-readable record under `docs/evidence/`
following the 8H provenance convention, with exact runtime/lock/image identities,
test/coverage scope, semantic artifact and ordering comparisons, privacy and
teardown checks. Keep raw logs/media/coverage in ignored local output, review
them before publishing summaries and never retain raw user rows or credentials.
Record tested clean parent SHA and, if changes were tested before committing,
the exact candidate diff identity; do not invent the commit's own future hash.
After each commit, verify its hash, docs/test ownership and clean working tree.

Any substantive correction after 9K invalidates the relevant final evidence:
rerun its focused gate and affected dependent gates, then reconcile docs against
the repaired candidate. Docs-only corrections with established command/evidence
provenance do not require another live build. Phase 9 closes only after 9L's
comparison is recorded; Phase 10 owns final release documentation and the
verified Stage 6 handoff.

## 17. Implementation Phase 10: Documentation and Release Preparation

### Objective

Make the implemented behavior reproducible, distinguish evidence from
limitations, and leave a precise Stage 6 input contract.

### Work

1. Update root, API, web, ML, infrastructure, data, architecture, data-model,
   recommendation-design, roadmap, environment, command, and plan documents.
2. Replace Section 21 proposals with exact as-built identities, thresholds,
   schemas, weights, commands, migrations, counts, and deviations.
3. Convert Section 22 from provisional to verified handoff and populate Section
   23 only from passing evidence.
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
- Completion evidence matches logs and does not extrapolate from synthetic data.

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

The external-source, Phase 0–1 audit, guarded Phase 2 fixture-artifact, and Phase
7 lifecycle command names are frozen as implemented. Commands use the
repository root unless noted. Bare `python -m app.commands...` syntax requires
`apps/api` as working directory, installed API/ML dependencies and explicit
operator settings. Placeholder paths/IDs are not runnable production approval.
POSIX environment assignments require `sh`; PowerShell uses `$env:NAME`
assignments as in the API README. Make audit wrappers emit `summary`; the
`--format json` forms below are parser-supported machine-readable alternatives.
For exact container wrapper expansions, see the [Makefile](../Makefile).

Phase 8 entry points (POSIX `sh`, Git Bash on Windows, and Docker required):

| Optional Make wrapper | Exact direct equivalent from repository root |
| --- | --- |
| `make test-web-e2e` | `sh infra/run-e2e-content.sh` |
| `make test-e2e-fixture` | `sh infra/run-e2e-fixture.sh` |
| `make test-e2e-live-source` | `sh infra/run-e2e-live-source.sh` |
| `make test-e2e-lifecycle` | `sh infra/run-e2e-lifecycle.sh` |
| `make test-phase8` | `python infra/run-phase8.py` (Python 3.12+) |

The [infra README](../infra/README.md) describes explicit setup/build/validation,
scenario selection, immutable paths and project-owned failure/teardown handling.

| Capability                                                                                  | Optional Make wrapper                | Required direct equivalent                                                                                                                                                                                                             |
| ------------------------------------------------------------------------------------------- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Verify local UCSD source identity                                                           | `make ucsd-steam-verify`             | `docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam verify --root /workspace --format json`                                                                  |
| Profile UCSD ingestion preparation                                                          | `make ucsd-steam-prepare`            | `docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam prepare --root /workspace --format json`                                                                 |
| Audit UCSD source-level support                                                             | `make ucsd-steam-audit`              | `docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam audit --root /workspace --format json`                                                                   |
| Check committed UCSD aggregate report                                                       | `make ucsd-steam-audit-check`        | `docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam audit --root /workspace --check-report data/external/ucsd-steam/suitability-audit.json --format summary` |
| Report the default-off live interaction gate or audit explicitly enabled eligible live data | `make collaborative-audit`           | `python -m app.commands.collaborative_snapshot audit --source live --format json`                                                                                                                                                      |
| Audit the project-authored test fixture                                                     | `make collaborative-fixture-audit`   | `ENVIRONMENT=test COLLABORATIVE_ALLOW_TEST_FIXTURE=true python -m app.commands.collaborative_snapshot audit --source fixture --format json`                                                                                            |
| Build a new guarded fixture bundle                                                          | `make collaborative-build`           | `docker compose --profile quality run --build --rm --no-deps -e COLLABORATIVE_ALLOW_TEST_FIXTURE=true quality python -m app.commands.collaborative_artifact build --source fixture`                                                    |
| Validate the configured guarded fixture bundle                                              | `make collaborative-validate`        | `docker compose --profile quality run --rm --no-deps -e COLLABORATIVE_ALLOW_TEST_FIXTURE=true quality python -m app.commands.collaborative_artifact validate`                                                                          |
| Inspect guarded fixture-bundle metadata                                                     | none required                        | `docker compose --profile quality run --rm --no-deps -e COLLABORATIVE_ALLOW_TEST_FIXTURE=true quality python -m app.commands.collaborative_artifact inspect`                                                                           |
| Build and register an explicitly approved live bundle                                       | none required                        | `python -m app.commands.collaborative_artifact build --source live --output <unused-path> --build-id <id> --confirm-live-build <id>`                                                                                                   |
| Recover exact orphan-bundle registration                                                    | none required                        | `python -m app.commands.collaborative_artifact recover --artifact <path> --build-id <id> --confirm-live-recovery <id>`                                                                                                                 |
| Check one valid-only manual rollback candidate                                              | none required                        | `python -m app.commands.collaborative_artifact rollback-check --artifact <path>`                                                                                                                                                       |
| Invalidate exact active registry state                                                      | none required                        | `python -m app.commands.collaborative_artifact invalidate --build-id <id> --confirm-invalidation <id>`                                                                                                                                 |
| Retire exact invalidated registry state                                                     | none required                        | `python -m app.commands.collaborative_artifact retire --build-id <id> --confirm-retirement <id>`                                                                                                                                       |
| Preview obsolete-bundle retirement                                                          | none required                        | `python -m app.commands.collaborative_artifact retirement-preview --artifact-set <exact-root>`                                                                                                                                         |
| Confirm obsolete-bundle cleanup                                                             | no broad wrapper                     | `python -m app.commands.collaborative_artifact cleanup --artifact-set <exact-root> --confirm-cleanup <exact-preview-value>`                                                                                                            |
| Preview or execute interrupted-filesystem recovery                                          | no broad wrapper                     | `python -m app.commands.collaborative_artifact recover-files --artifact-set <exact-root> --target <exact-target> --kind build\|cleanup [--execute --writers-stopped --confirm-recovery <exact-preview-value>]`                         |
| Build existing content artifact                                                             | `make model-build`                   | Existing `recommendation_artifact build` command                                                                                                                                                                                       |
| Validate existing content artifact                                                          | `make model-validate`                | Existing `recommendation_artifact validate` command                                                                                                                                                                                    |
| Inspect component status                                                                    | none required                        | `GET /api/v1/models/status`                                                                                                                                                                                                            |
| Run focused ML tests                                                                        | `make test-ml`                       | Existing documented pytest command                                                                                                                                                                                                     |
| Run API and PostgreSQL gates                                                                | `make test`, `make test-integration` | Existing documented direct commands                                                                                                                                                                                                    |
| Run web and browser gates                                                                   | `make test-web`, `make test-web-e2e` | Existing documented npm/Compose commands                                                                                                                                                                                               |
| Validate all Compose files                                                                  | `make config`                        | Existing direct `docker compose ... config --quiet` commands                                                                                                                                                                           |

Existing command meanings must not change. No startup, request, migration, seed,
broad test, or teardown command may fit a model, install an unpinned dependency,
purge user data, retire an artifact, or silently rebuild a bundle. Mutable
commands require exact targets and fail safely on ambiguity.

## 19. Acceptance Criteria

Stage 5 is complete only when all applicable criteria below pass:

- **S5-AC-01.** All Stage 1–4 migrations, contracts, privacy behavior, commands, artifacts,
  fast tests, integration tests, web tests, browser tests, and Docker workflows
  remain green.
- **S5-AC-02.** `POST /api/v1/recommendations` remains cookie-agnostic, content-only,
  request-scoped, read-only, and contract-compatible.
- **S5-AC-03.** Data source, purpose, authority, cutoff, catalog mapping, consent, retention,
  deletion, provenance, and limitations are documented.
- **S5-AC-04.** Existing Stage 4 consent is not silently reused for aggregate training.
- **S5-AC-05.** Declining contribution does not create training eligibility; the documented
  request-only or saved-personalization fallback remains usable.
- **S5-AC-06.** The audit is read-only, aggregate-only, deterministic, bounded, and returns
  typed suitability reasons without fitting.
- **S5-AC-07.** Snapshot cutoff comes from PostgreSQL and one repeatable-read, read-only
  transaction.
- **S5-AC-08.** Temporal state, reaction precedence, rating threshold, saved positive game
  preference, and duplicate-source collapse match the frozen label policy.
- **S5-AC-09.** Unknown, viewed, played-only, wishlist-only, low-rating, disliked, and
  recommendation-event rows never become positive cosine edges.
- **S5-AC-10.** Recommendation events remain committed-generation audit records and are
  excluded from training by code, query, test, and documentation.
- **S5-AC-11.** Internal IDs and credentials remain outside snapshots, artifacts, logs,
  events, responses, browser state, reports, and committed fixtures.
- **S5-AC-12.** Live user label rows and ephemeral cohort mappings are not retained as a
  reusable snapshot file after build success or failure.
- **S5-AC-13.** Any identity-bearing contributor lineage stays protected in PostgreSQL and
  exists only to enforce lifecycle invalidation.
- **S5-AC-14.** Cleared, withdrawn, revoked, expired, or deleted contributions cannot enter a
  new build or continue through a serveable old artifact.
- **S5-AC-15.** Artifact/registry revision identity, bounded readiness/invalidation state,
  expected contributor count, consent version, validity horizon, and catalog
  fingerprint are checked before use without a per-request contributor scan;
  promotion also proves the source revision did not change during
  extraction/build.
- **S5-AC-16.** The deterministic fixture is explicitly project-authored, isolated from
  development data, and never presented as a real-user or quality dataset.
- **S5-AC-17.** A fixture artifact is serveable only in guarded disposable test/E2E mode and
  is rejected by ordinary development and production configuration.
- **S5-AC-18.** Structural and activation thresholds fail with `insufficient_data` rather than
  promoting a trivial live artifact.
- **S5-AC-19.** Fitting and serving use bounded sparse operations and never persist an
  unbounded dense user-item or item-item matrix.
- **S5-AC-20.** Hand-calculated item support, pair support, raw cosine, quantization,
  self-edge removal, pruning, and tie-breaks match implementation exactly.
- **S5-AC-21.** The artifact has exact model/schema/code identity, source kind, cutoff,
  catalog and interaction fingerprints, label policy, thresholds, build ID,
  revision, validity, aggregates, resource limits, and member checksums.
- **S5-AC-22.** Artifact files contain no executable pickle, user matrix, user row, user ID,
  stable pseudonym, credential, or raw interaction payload.
- **S5-AC-23.** Missing, corrupt, incompatible, oversized, stale, expired, privacy-invalid,
  retired, or catalog-mismatched bundles never become collaborative-ready.
- **S5-AC-24.** Build targets are immutable; validation is read-only; promotion is crash-safe;
  rollback accepts only a still-valid registered artifact.
- **S5-AC-25.** The collaborative scorer is pure, bounded, identity-free, deterministic, and
  excludes all source and disliked games.
- **S5-AC-26.** Unsupported users, sources, items, or pairs receive no fabricated
  collaborative score.
- **S5-AC-27.** Candidate union allows a valid collaborative-only candidate before exclusions
  and top-K.
- **S5-AC-28.** A collaborative-only candidate receives explicitly materialized
  content/platform/popularity/base/affinity evidence without weakening the
  existing Stage 3 zero-content eligibility contract.
- **S5-AC-29.** Hybrid weights are request-wide, versioned engineering defaults rather than
  learned or quality-optimized values.
- **S5-AC-30.** Under an active collaborative request, a candidate with no retained edge has
  unsupported/zero collaborative evidence and no candidate-level weight
  reallocation; this behavior is golden-tested and deferred to Stage 6 for
  evaluation.
- **S5-AC-31.** A reproducible fixture comparison records baseline candidates, components, and
  ranks while making no recommendation-quality claim.
- **S5-AC-32.** Base, platform, popularity, feedback affinity, collaborative, played, and
  final values remain independently observable and reconstructible.
- **S5-AC-33.** Each named signal is weighted once; component contributions sum exactly in
  fixed-point units.
- **S5-AC-34.** Played adjustment occurs once after the pre-played hybrid score, dislikes
  remain hard exclusions, and wishlist remains neutral.
- **S5-AC-35.** Every collaborative-unavailable or unsupported path matches Stage 4 scores,
  order, response reason, and evidence exactly.
- **S5-AC-36.** Content readiness survives optional collaborative failure, while model status
  and personalized output expose truthful mode and bounded reason.
- **S5-AC-37.** The saved response, `stage-5-v1` event, and generated browser type share the
  same model/data/policy identity and component units.
- **S5-AC-38.** Every commit-acknowledged personalized HTTP 200 has exactly one matching
  bounded event; known pre-commit failures have none; ambiguous commit
  acknowledgement is not returned as success.
- **S5-AC-39.** Event payloads contain no prose, credentials, identities, unbounded source
  lists, or state dump, and never become training labels.
- **S5-AC-40.** Browser code preserves server order and performs no ranking math.
- **S5-AC-41.** Collaborative explanation appears only for a positive applied contribution and
  makes no “users like you” or quality claim.
- **S5-AC-42.** Consent, withdrawal, fallback, loading, empty, failure, keyboard, focus,
  announcement, accessibility, and responsive states pass their gates.
- **S5-AC-43.** Commands have direct equivalents, immutable paths, stable exit behavior,
  read-only defaults where appropriate, and guarded destructive confirmation.
- **S5-AC-44.** Ordinary startup, request handling, migration, seed, tests, and teardown do
  not train, promote, retire, or delete artifacts or user data.
- **S5-AC-45.** Dependency locks, licenses, security checks, Compose validation, non-root
  execution, OpenAPI drift, privacy scan, and final release review pass.
- **S5-AC-46.** Documentation distinguishes current Stage 4 behavior, implemented Stage 5
  evidence, provisional policy defaults, and deferred Stage 6 evaluation.
- **S5-AC-47.** No Precision/Recall/NDCG or other formal quality result, superiority claim,
  real-user claim, invented count, timing, or artifact size appears without the
  appropriate later evidence.

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

**Risk:** Collaborative candidates are limited to the content shortlist and the
implementation is hybrid in name only.

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

Phase 0–7 source preflight, first-party snapshot, consent/revision, fixture,
aggregate audit, sparse trainer, offline artifact, pure scoring, hybrid policy,
lifecycle readiness, saved API/event projection, and browser-presentation
decisions are implemented. Guarded live operations are tested only with explicit
disposable data; they do not approve a production cohort or product contribution
flow.

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
3. Source deletion is immediate relational state removal. User deletion cascades
   consent/preferences/interactions and advances the revision. Withdrawal,
   revocation, expiry changes, feedback changes, and catalog changes likewise
   invalidate the captured revision. No Phase 0–1 live row-level derived file
   exists.
4. Live extraction initializes a verified PostgreSQL
   `REPEATABLE READ, READ ONLY` transaction by pinning `pg_current_snapshot()`
   and capturing one `clock_timestamp()` cutoff before returning to extraction.
   A fresh transaction verifies the captured revision before an aggregate report
   is emitted. Eligible users require current base consent, unexpired/unrevoked
   state, and the configured contribution version granted and not withdrawn by
   the cutoff.
5. Temporal state includes `occurred_at <= cutoff` and
   `superseded_at IS NULL OR superseded_at > cutoff`. Stable GameLens slugs and
   the exact content-catalog fingerprint cross the ML boundary; internal IDs and
   per-user mapping do not.
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
   fingerprint remain unchanged. The resulting binary CSR is canonical and uses
   `int64` arithmetic so the allowed 256-contributor case cannot overflow.
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
   free canonical JSON, validates bounded NPY headers/dtype/shape/trailing
   bytes, and recomputes graph support/cosine coherence. Catalog mismatch,
   expected revision or consent mismatch, and `now >= valid_until` fail closed
   with typed reason codes. Returned arrays have immutable byte backing.
6. The builder creates an exclusive promotion lock and temporary sibling, fsyncs
   members, writes the manifest last, loads the temporary bundle through the
   production validator, optionally performs the mandatory last-moment live
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
9. The project-authored fixture deterministically produces 12 contributors, 6
   retained items, 36 positive edges, and 20 directed neighbors. Equivalent
   reordered input produces byte-identical semantic members and immutable loaded
   arrays. Hand-calculated cosine quantization includes the `707107` golden case
   and pair-support-one exclusion.
10. Verification covers support cascades, duplicate profiles, overflow, top-K
    ties, caps, corruption, missing/extra members, traversal, JSON/NPY safety,
    dtype/shape/CSR/cosine coherence, catalog/revision/consent mismatch, expiry,
    promotion races, cleanup, privacy, determinism, and the real fixture
    pipeline. The full ML suite has 155 passes; one symlink case is skipped on
    the current Windows host because it cannot create symlinks and remains
    runnable on capable systems. All 200 API unit tests, Ruff, and
    `git diff --check` pass.

### As-Built Phase 3 Pure Scoring Decisions

1. Query sources are immutable stable-slug records with kinds `liked`, `rating`,
   and `saved_game`. Dislikes dominate all positive forms; liked-over-rating and
   feedback-over-saved precedence, recency/slug ordering, and five-positive plus
   five-saved caps are applied once by
   `canonicalize_collaborative_query_sources()`.
2. Sparse lookup resolves only canonical source rows through `slug_to_index` and
   exact `neighbor_indptr` slices. Unsupported sources and supported zero-degree
   rows remain distinct. At most 10 source rows, 100 neighbors per row, 1,000
   visited edges, and 1,000 returned candidates are permitted.
3. `CollaborativeScorer` computes each candidate as the round-half-up integer
   mean of all present stored `similarity_units`. Missing edges do not enter the
   numerator or denominator. Source and dislike exclusions precede return;
   candidates order by collaborative units descending then slug ascending.
4. Results carry policy identity, canonical source partitions, exact candidate
   units/item support, every contributing edge with pair support, bounded
   diagnostics, and typed reasons for recommendations, empty input, unsupported
   sources, no edges, and all-excluded candidates. Contract errors return no
   partial result and the scorer performs no fallback.
5. `ContentRanker.materialize_base_candidates()` scores at most 1,000 exact
   catalog rows and preserves zero-content candidates with exact platform,
   popularity, and base units. Existing `score_candidates()` eligibility,
   ranking, evidence, and Stage 3 wrapper behavior remain unchanged.
6. `FeedbackRanker.materialize_affinity_candidates()` returns exact affinity
   units and profile-active state for the same bounded slug seam. The existing
   Stage 4 `rank()` path delegates to the shared calculation without changing
   items, ordering, played adjustment, explanations, policy identity, or result
   reasons.
7. The production-loaded fixture trace uses source `emberfall-tactics`, exact
   CSR offset range `[4, 8)`, and four deterministic candidates. The
   collaborative-only `starbound-couriers` handoff has collaborative/content/
   platform/popularity/base/affinity units `428571/0/1000000/599117/159912/0`
   plus empty genre, tag, and selected-game content evidence. Catalog
   fingerprints match before outputs are joined by stable slug.
8. Stable Phase 3 contracts are exported from the package root. Internal CSR
   lookup helpers are not root exports. Complexity and purity boundaries are
   recorded in code; `collaborative.py` imports neither content nor feedback
   rankers and performs no I/O, identity lookup, weights, played adjustment,
   top-K, fallback, prose, or HTTP mapping.
9. Slice commits are `73b4528`, `7a57dcd`, `5e25a64`, `844c695`, `a5b755c`,
   `d0b6676`, and `fa0ebd0`. The focused Phase 3 set passes 154 tests; the full
   ML suite passes 256 with one Windows symbolic-link capability skip. Ruff
   lint/format, mutation, permutation, privacy-string, resource-bound, and Stage
   3/4 characterization gates pass with no new dependency.
10. Candidate union origin, hybrid weights, played application after hybrid
    blending, final rank, serving fallback, readiness, lifecycle validation,
    API/event schemas, UI evidence, and ranking-quality claims remain outside
    Phase 3 and are not implied by these fixture results.

### As-Built Phase 4 Hybrid Policy Decisions

1. The frozen policy is `gamelens-hybrid-ranking/1.0.0`. Immutable contracts
   define `hybrid` and `stage_4_fallback` modes; `content`, `collaborative`, and
   `both` candidate origins; the complete unavailable/no-support fallback
   taxonomy; policy identities; bounded component records; and typed
   configuration, input, and result failures.
2. `FeedbackRanker.prepare_ranking_context()` exposes one reusable immutable
   Stage 4 calculation containing the exact baseline, affinity profile, played
   state, and collaborative query context. Existing `FeedbackRanker.rank()`
   delegates through that seam without changing its public result, identity,
   evidence, score, or order.
3. The hybrid candidate union joins exact content/base, affinity, and retained
   collaborative candidates by stable slug before final top-K. It assigns one
   explicit origin, preserves zero-content collaborative candidates, retains
   exact source-edge evidence, and cannot reintroduce selected positive sources
   or dislikes.
4. Policy weights use the 1,000,000 fixed-point scale. A request with an active
   affinity profile assigns base/affinity/collaborative weights
   `800000/100000/100000`; an inactive profile assigns `900000/0/100000`.
   Contributions use the existing round-half-up integer operation, then the
   existing `500000` played factor applies once after blending.
5. Final ordering is frozen by final score, pre-played score, base contribution,
   collaborative contribution, affinity contribution, raw content score,
   popularity score, and slug. Exact contribution-sum, played-delta, top-K,
   duplicate, tie, exclusion, and permutation tests reconstruct every output.
6. Materialized hybrid recommendations expose raw Stage 3 components, base and
   policy weights/contributions, affinity and collaborative evidence, played
   adjustment, candidate origin, policy identities, diagnostics, and positive
   sources. Deterministic cautious prose is derived only from those structured
   facts and does not claim that similar users prefer an item.
7. Public `HybridRanker` accepts a typed ready or unavailable collaborative
   outcome. Every unavailable reason and every scorer no-support reason returns
   `Stage4FallbackResult` containing the exact unchanged Stage 4 result. Query-
   source or dislike-context mismatches fail as typed invalid input instead of
   silently falling back.
8. Stable Phase 4 policy/result/orchestrator contracts are exported from the
   package root. Candidate-union, scoring, and recommendation-materialization
   stage records/functions remain internal so callers cannot assemble partial
   policy results.
9. The production-built and production-loaded Phase 2 fixture reaches the public
   hybrid policy deterministically. Its collaborative-only `starbound-couriers`
   row has base/affinity/collaborative units `159912/0/428571`, weighted
   contributions `127930/0/42857`, and final units `170787`. Repeated runs
   preserve output and artifact bytes; privacy-string checks find no fixture
   profile key or user/credential field. This is a functional diagnostic, not
   recommendation-quality evidence.
10. Slice commits are `23132a0`, `2447e26`, `d547e3f`, `6e3e181`, `18e6ad4`,
    `8556744`, and `10a5c79`. The focused Phase 3/4 handoff and hybrid suite
    passes 68 tests; the full ML suite passes 331 with one Windows symbolic-link
    capability skip. Ruff lint/format and diff checks pass with no new
    dependency.

### As-Built Phase 5 Lifecycle and Orchestration Decisions

1. `COLLABORATIVE_ARTIFACT_PATH` remains independent from the required content
   path. Application construction loads the optional bundle once through the
   production validator and freezes its arrays; no startup/request hot reload,
   repair, fit, promotion, or mutation exists. A fixture bundle requires both
   `ENVIRONMENT=test` and `COLLABORATIVE_ALLOW_TEST_FIXTURE=true`.
2. Pure readiness returns exactly `not_configured`, `fixture_only`,
   `insufficient_data`, `unavailable`, `stale`, or `ready`. Its bounded reason
   taxonomy covers configuration, fixture authority, support, integrity,
   compatibility, revision, privacy, expiry, catalog identity, and retirement.
   Only guarded fixture and valid live `ready` states carry an artifact into
   scoring.
3. Migration `0007_stage_5_artifact_registry` adds live-only
   `collaborative_artifact_builds` and database-only
   `collaborative_artifact_contributors`. The build row freezes build/revision,
   lifecycle, invalidation epoch, expected/current contributor counts, consent,
   catalog/interaction fingerprints, cutoff/validity, and timestamps. A trigger
   maintains current count. Hot-path readiness selects at most one indexed build
   row and never scans contributor membership.
4. Migration `0008_stage_5_authority_loss` enforces current contributor
   authority before lineage insertion. Contribution withdrawal/version change,
   session expiry/revocation, or user deletion invalidates every affected active
   build in the same database transaction, advances the invalidation epoch, and
   records database time before membership can disappear.
5. Migration `0009_stage_5_label_changes` records the build cutoff and installs
   constraint triggers for saved-game and interaction label loss/change under
   `gamelens-collaborative-labels/1.0.0`. Only an included pre-cutoff positive
   disappearing or ceasing to be positive invalidates the build. A new post-
   cutoff positive is future build input. The expected schema head is
   `0009_stage_5_label_changes`.
6. `GET /api/v1/models/status` preserves top-level required-content semantics
   and adds `components.content` plus `components.collaborative` with bounded
   state, reason, and source kind. Content remains available through every
   optional failure. The generated browser type was updated from OpenAPI; no
   parallel handwritten type was added.
7. `HybridRankingOrchestrator` receives immutable content service, loaded
   optional component, and the public Phase 4 hybrid ranker. It prepares one
   Stage 4 context, invokes collaborative scoring only for usable readiness,
   maps scorer failures fail-closed, and returns exact Stage 4 fallback for all
   11 lifecycle and 4 no-support reasons. Stateless recommendation behavior is
   unchanged.
8. `PersonalizedRankingDecisionService` resolves database time and, for a live
   artifact, one registry row inside the saved request's existing repeatable-
   read transaction. A nested savepoint converts readiness SQL failure to
   `artifact_incompatible` without poisoning the required event transaction. It
   returns the typed hybrid/fallback result, readiness, and one exact legacy
   Stage 4 result.
9. At the Phase 5 handoff, the public saved mapping deliberately used that
   legacy Stage 4 result and committed a `stage-4-v1` event. For a true hybrid
   result, the legacy result was computed and retained separately; for fallback,
   it was the exact object carried by `Stage4FallbackResult`. Therefore Phase 5
   emitted neither a hybrid HTTP 200 nor a mislabeled event. Phase 6
   subsequently maps that internal decision to both public contracts from the
   same fixed-point values.
10. Slice commits are `0eab24f`, `189ce4c`, `a6d7a34`, `fb7251f`, `4f52547`,
    `7e10882`, `aefb425`, and `66af706`. Verification passes 311 API unit, 98
    disposable-PostgreSQL, and 331 ML tests with one Windows symbolic-link
    capability skip. Ruff lint/format passes across 165 Python files, generated
    OpenAPI types have no drift, and the Docker test stack is removed. No Phase
    6 response/event/browser result or recommendation-quality metric is claimed.

### As-Built Phase 6 Response, Event, and Product Decisions

1. The saved personalized response is additive. It preserves Stage 4 model,
   data, feedback-policy, base, affinity, played, evidence, and generation
   fields while adding `ranking_mode`, one of 15 bounded fallback reasons,
   hybrid/collaborative identity, candidate origin, aggregate support/source
   edges, component weights, and exact contributions. The stateless Stage 3
   response remains unchanged.
2. Migration `0010_stage_5_event_contract` is the Phase 6 Alembic head, later
   advanced by Phase 7's data-preserving `0011_stage_5_lifecycle_guard`. It
   preserves readable `legacy-v1` and `stage-4-v1` rows, adds nullable bounded
   Stage 5 mode/fallback/hybrid/collaborative columns, indexes mode/time, and
   requires all-or-none hybrid identity or reason-only fallback identity for
   `stage-5-v1`. Result summaries remain JSON arrays capped at 20 items.
3. One pure projector receives the immutable `PersonalizedRankingDecision` and
   derives both the response and compact event record from the same fixed-point
   values. Hybrid and every fallback reason have equality/reconstruction
   characterization; ordering, top-K, JSON shape, and source-edge bounds are
   deterministic, and ranking is not invoked again during projection.
4. `POST /api/v1/me/recommendations` activates that projector inside the
   existing repeatable-read transaction. Each committed HTTP 200 correlates to
   exactly one `stage-5-v1` event; known pre-commit failures insert none, and
   commit-acknowledgement/ambiguous-outcome behavior remains the Stage 4
   contract. The stateless route neither reads collaborative lineage nor changes
   its response/event behavior.
5. A fallback event records content and feedback identity, explicit
   `stage_4_fallback` mode, and one bounded reason while all hybrid and
   collaborative identity columns remain null. A hybrid event records complete
   hybrid/collaborative identity and reconstructible compact component units.
   Recommendation events remain excluded from labels and source revision.
6. FastAPI OpenAPI is the single browser-contract source. The generated
   TypeScript file includes the additive response and component-status fields;
   the runtime client rejects malformed/unknown response shapes without a
   handwritten parallel interface. The public request-only client behavior is
   unchanged.
7. The saved-results component renders the exact server array order and formats
   returned values without sorting, reweighting, or score recomputation. It
   presents hybrid mode or a neutral usable fallback and shows aggregate
   interaction support/source evidence only when a positive collaborative
   contribution was applied. Ordinary UI omits model fingerprints, lineage,
   contributor identities, social proof, probability claims, and quality claims.
8. Loading uses a polite live status; failures use an alert and keyboard retry;
   valid empty results preserve saved-context guidance; ready/error headings
   receive post-commit focus. Responsive and forced-colors styles keep the
   saved-result evidence usable at representative viewports.
9. Slice commits are `8c1c4f9`, `fe784e2`, `c2ddd2d`, `0bbdc58`, `9ab9f68`, and
   `51664b5` for 6A–6F. The Phase 6 handoff passes 365 API unit, 109
   disposable-PostgreSQL, 331 ML (plus one Windows symlink capability skip), and
   86 web tests. Ruff lint/format passes across 172 Python files; strict
   TypeScript, ESLint, production build, OpenAPI drift, and diff checks pass.
10. A focused no-retry Docker browser gate passes five cases: axe on Chromium,
    Firefox, and WebKit plus request-only and saved-personalization responsive
    checks on Chromium. The browser/API stack uses disposable PostgreSQL and
    removes its containers, networks, volumes, and artifacts after the run.
    These gates prove contracts and functional behavior, not recommendation
    quality, representativeness, or Stage 5 completion.

### As-Built Phase 7 Derived-Data Lifecycle Decisions

1. Operator output is deterministic JSON with stable typed error envelopes and
   exit status two for refused operations. Read-only commands require explicit
   paths where ambiguity could otherwise select a configured artifact.
2. The live path remains default-off and requires enabled live data, a separate
   contribution-consent version, enabled promotion, an explicit build ID, and an
   exact matching confirmation. It extracts ephemeral identity-free lineage,
   builds and validates an immutable unused target, then registers exact retained
   contributor membership in one deliberate transaction.
3. Filesystem publication precedes registry commit, so a registry failure can
   leave a complete orphan directory but never a serveable half-state. `recover`
   revalidates exact artifact metadata, current revision, catalog, consent,
   aggregate matrix facts, and retained lineage before registering it. It never
   reactivates an invalidated or retired row.
4. Registry validity is separate from serving selection. Multiple active rows
   may coexist so a prior still-valid bundle remains a rollback candidate; only
   `COLLABORATIVE_ARTIFACT_PATH` is loaded. A new positive revision does not
   invalidate older retained lineage, while authority or included-label loss
   invalidates every affected active row transactionally.
5. `rollback-check` is read-only and shares the serving-readiness resolver. It
   accepts only a structurally valid registered live artifact whose row is
   active with epoch zero and whose build/revision/cutoff/count/consent/catalog/
   interaction/validity facts match. Success explicitly reports that no
   configuration changed and a manual configuration update plus restart remains
   required.
6. `invalidate` and `retire` require exact build-ID confirmations. Invalidation
   is idempotent, retirement requires invalidation first, and retired state is
   terminal. Migration `0011_stage_5_lifecycle_guard` changes no data and blocks
   lifecycle reversal, skipped invalidation, epoch rewind, and rewriting an
   already recorded lifecycle timestamp even through direct SQL.
7. `retirement-preview` performs a bounded direct-child inventory, discloses no
   contributor membership, refuses unregistered or malformed live bundles, and
   separates protected active/configured/content paths from invalidated or
   retired candidates. Its confirmation binds the resolved database, artifact-
   set inventory, and exact retirement selection.
8. `cleanup` requires that exact confirmation and repeats the preview before
   moving each unchanged candidate into a receipt-backed quarantine. It verifies
   bounded filenames, sizes, hashes, registry status, and protection facts before
   physical deletion; it makes no registry write. Confirmation mismatch, target
   drift, path escape/link, root paths, configured artifacts, active builds, and
   development-database execution fail closed.
9. `recover-files` is preview-first for stopped-builder temp/lock remnants and
   interrupted cleanup quarantine. It relies only on an exact target, bounded
   marker/receipt/file hashes, current registry status, database fingerprint,
   exact confirmation, `--execute`, and `--writers-stopped`. It does not infer
   process death, register an orphan, or resurrect lifecycle state.
10. Startup, requests, migration, seed, broad tests, and ordinary Compose
    teardown do not fit, promote, invalidate, retire, recover, or clean a bundle.
    Destructive test execution additionally requires the triple disposable-
    PostgreSQL gate and an artifact-set descendant of the system temporary root.
11. Slice commits are `03985e3`, `23c2c62`, `b48aa41`, `f997b23`, `7b2bf74`,
    `7740223`, `0dc057d`, and `3fabc72` for 7A–7H. Direct-CLI import-cycle fix
    `3e274be` adds a fresh-interpreter smoke gate. The current handoff passes 782
    combined API-unit/ML tests and 143 disposable-PostgreSQL integration tests.
    Ruff lint/format passes across 194 Python files, OpenAPI has no drift, privacy
    scans find no contributor identifier in output/log/artifacts, and Docker test
    resources are removed.
12. Phase 7 proves operational safety and lifecycle correctness on synthetic
    disposable data. It does not grant product contribution consent, approve a
    production live cohort or external dataset, establish recommendation
    quality, or claim the Phase 8 browser lifecycle.

### As-Built External-Source Decisions

1. Source kind is `external_snapshot`; report schema is 1; manifest schema is 1;
   the source remains `local-raw-sources-verified-not-integrated`.
2. `verify`, `prepare`, and `audit` are read-only standard-library commands.
   JSON is the machine format and `--format summary` is the human format.
   Expected blocked integration exits zero; source/manifest safety errors exit
   two. No audit module command downloads source data, writes, fits, promotes,
   or mutates PostgreSQL. A requested container image build may obtain image
   dependencies.
3. All manifest members must pass exact path, HTTPS host, compressed size,
   bounded SHA-256, gzip CRC/shape, expanded size, line-count, maximum-line, and
   no-blank-line checks. Every compressed identity is verified before any source
   literal is parsed and rechecked after scanning or parsing.
4. Parser caps are 2 MiB per line, 2 GB expanded per member, 5,000,000 top-level
   records, 20,000,000 nested rows, 500,000 transient users, 100,000 transient
   items, 2,000,000 review pairs, 10,000,000 pair contributions, and 1,000,000
   distinct item pairs. Source user IDs are capped at 256 characters and item
   IDs at 32. The parser is `ast.literal_eval`; executable and structurally
   invalid literals fail with typed errors.
5. Preparation policy `ucsd-steam-review-recommend-preparation-v1` uses
   source-native `recommend=true` only, collapses same-flag user/item
   duplicates, excludes conflicts, and never promotes ownership, playtime, or
   false reviews. The policy is explicitly not an approved Stage 5 label.
6. Source-level thresholds are two items per profile, two profiles per item, and
   two profiles per pair; diagnostic activation minima are 10 profiles, 20
   edges, and 5 items. A deterministic queue-based bipartite two-core reaches
   the same user/item fixed point without repeated full rescans. The JSON report
   records the algorithm and pass count; this does not freeze the future
   model-builder pruning policy.
7. Candidate profiles are sorted item tuples; the multiset retains duplicate
   profiles and is sorted before canonical JSON/SHA-256 hashing. Source user
   keys are used only for transient grouping and are never emitted.
8. The exact verified file/profile/support counts, manifest fingerprint,
   candidate fingerprint, distributions, limits, and privacy flags are in
   [`data/external/ucsd-steam/suitability-audit.json`](../data/external/ucsd-steam/suitability-audit.json).
   Source-level structural support passes, but approved training eligibility and
   functional-build readiness remain false.
9. Source identity is verified. Source provenance is recorded but not
   ingestion-approved. License/redistribution, GameLens catalog mapping, Stage 5
   label authority, fixture activation, and live consent/lifecycle gates remain
   blocked. The catalog schema has nullable `external_id`; all 30 seed payloads
   omit it and use the null default, and no reviewed Steam mapping artifact
   exists. No title matching is attempted.
10. No dependency changed. The dedicated `ucsd-source-audit` service mounts
    `data/` and `ml/` read-only, uses a read-only root filesystem, and disables
    runtime networking. The general `quality` service mounts `data/catalog/`,
    `data/fixtures/`, and the committed UCSD manifest and aggregate-audit files
    read-only; it never mounts ignored `data/external/ucsd-steam/payload/`
    bytes. Thirty-five focused UCSD cases and all 105 ML tests pass; the
    committed-report check also passes against the full local source.

### As-Built Phase 8 Docker and Fixture Decisions

Slices 8A–8I are complete; the [execution ledger](#phase-8-completed-slice-record)
records the owning commits. The verification records and final comparison
inventory follow here. The committed JSON
fixture remains test-only and unregistrable as live. Separate guarded synthetic
PostgreSQL rows exercise real live extraction, immutable builds, lineage and
invalidation. Builders run explicitly; API selection is load-once/read-only;
ordinary operations do not mutate artifacts or registry. Shared teardown checks
ownership and absence of leftover resources. No migration or ranking policy
changed; schema head remains `0011_stage_5_lifecycle_guard`.

GNU Make was unavailable; direct Python/shell/Docker commands supplied equivalent
scope. Interrupted combined execution was recovered per exact project and
resumed, with two successful fresh live/lifecycle suffixes. The web/API shared
network namespace required web recreation after API restart. Evidence is
functional and synthetic, with no production contribution authority or Stage 6
quality conclusion. Slice 8I changes documentation only.

The following dated records preserve the original tested revisions, commands,
counts and deviations. Statements about deferred slices describe the checkpoint
on that record's date; the completed ledger in Section 15 gives current status.
The 8I comparison and link counts describe commit `d0e86f9`, before this
consolidation. The standalone Phase 8 planning document has been merged into
Sections 15 and 21, and references now target this Stage 5 plan. The aggregate
[8H evidence](evidence/stage-5-phase-8h.json) remains unchanged.

#### Slices 8A–8E verification record — 2026-09-06

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

#### Slice 8F verification record — 2026-09-06

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

#### Slice 8G verification record — 2026-09-07

- **Implementation commit and tested tree:** `693808f`; the final hash
  was reported from Git after commit creation. The complete lifecycle workflow
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

#### Slice 8H verification record — 2026-09-09

- **Implementation:** `35082f2`, based on clean revision
  `693808f1b6c4eafafc32e2071e0b021cf9ca44f6`; its final hash was reported after
  commit creation. Changes are confined to test infrastructure, regression checks
  and this slice's documentation. No serving, ranking, response/event contract or
  migration change was made. Schema head remains `0011_stage_5_lifecycle_guard`.
- **Retained evidence:** [aggregate machine-readable record](evidence/stage-5-phase-8h.json)
  contains exact command arrays, expected/actual exits, durations, log SHA256s,
  runtime versions, image IDs/digests, artifact hashes/sizes, registry aggregates,
  fixture semantic identities and replay comparisons. Raw logs and private browser
  state are not committed. Accepted command execution totals **4357.03 seconds**;
  this excludes aborted/exploratory attempts and supplemental final static checks.
- **Invocation:** `python infra/run-phase8.py` ran all configuration, quality,
  PostgreSQL, web, teardown-fault and fixture gates. Host/runner interruptions
  required exact-project recovery and resuming the remaining
  `sh infra/run-e2e-live-source.sh` and `sh infra/run-e2e-lifecycle.sh` commands.
  Each completed twice on fresh disposable projects with the same implementation.
  Evidence therefore combines a successful prefix and resumed replay suffix;
  it is not claimed as one uninterrupted process. GNU Make was unavailable, so
  Python/direct shell/Docker equivalents exercised the commands behind the targets.
- **Combined results:** all Compose definitions/modes parsed; **502 API unit,
  333 ML, 151 PostgreSQL integration, 86 web unit, 38 Stage 1–4 browser tests**
  passed. The content browser invocation had 14 intentional mode-specific skips.
  Web typecheck, lint, format, production build and live OpenAPI drift checks
  passed, as did API/ML Ruff lint and format. The standalone
  `sh infra/run-e2e-content.sh` wrapper also passed its 38 browser tests and cleanup.
- **Fixture/live/lifecycle:** fixture builds replayed twice with identical
  semantic identities; all seven optional fallback reasons and required-content
  503/no-event behavior passed (**18 browser tests**). Live-source saved hybrid
  requests committed exactly one matching event each. Both live ordering hashes
  were `161d8d81a9c07f7ca2ab1ea11f4b1dea581e8f5e4b288a1716d51e88fc7754e8`.
  Each lifecycle replay passed six scenarios, **26 browser phases** and event
  counts `[4, 3, 3, 3, 3, 3]`, with six verified project teardowns.
- **No implicit mutation:** before/after snapshots matched around ordinary
  startup/restart, migration, catalog seed and ordinary config/health tests.
  Lifecycle restart/setup preserved artifact and registry snapshots too. Each
  live snapshot contained 23 files: content **69743 bytes**, previous collaborative
  **3640 bytes**, current collaborative **3639 bytes**; registry aggregates had
  two builds, 24 contributor-lineage rows and one revision row. Cross-run live
  comparison uses semantic ordering; captured cutoffs need not be byte-identical.
- **Isolation/privacy/teardown:** actual API/web processes ran as UID 1000;
  project-owned API artifact mounts were read-only. Image/topology checks passed
  for private payload exclusion, server-only secrets, no Docker socket, no host
  data mounts and no published test ports. Credential/identity log scans passed;
  snapshots emit only hashes/counts. Shared ownership-aware cleanup passed normal
  completion, setup failure, missing-artifact validation failure, actual injected
  Playwright failure and SIGTERM with expected exits **0/41/1/1/130**. Ownership
  was captured before removal and zero leftovers verified. Final Docker inventory
  contained no E2E resources; existing development resources were not removed.
- **Host:** Windows 11 `10.0.26200`, Docker Desktop Linux x86_64, Engine 29.7.2,
  Compose 5.4.0, host Python 3.12.10, API Python 3.12.13, Node 24.18.0,
  npm 11.16.0 and PostgreSQL 16.14. Exact image SHA256s are in the evidence file.
  Native Windows/macOS artifact filesystems and other architectures remain
  untested; these functional synthetic-data results confer no production-data
  authority or ranking-quality evidence.
- **Review fixes/deviations:** added writable temporary space for ordinary pytest
  in the read-only smoke container, corrected stale topology assertions and
  validated actual fault exit codes. Restart testing exposed web remaining in an
  old shared API network namespace; runners now stop web, restart API, recreate
  web into the current namespace, then check web restart separately. Browser-side
  connectivity and regression checks cover this boundary. Final runner Ruff
  lint/format, individual shell syntax checks and `git diff --check` passed after
  review. Host termination cannot execute traps; exact interrupted projects were
  recovered separately. These are execution/infrastructure adjustments, with no
  reduction of the slice acceptance scope.
- **Docs boundary:** updated only the infra usage notes and 8H evidence/status.
  At that checkpoint slice **8I remained PLANNED and unstarted**; the subsequent
  8I record below completes documentation reconciliation. Phase 9/10 gates and
  final Stage 5/6 handoff remain separate work.

Phase 8 exits only when a fresh isolated stack reproducibly builds and validates
both artifact types, serves hybrid, invalidates a real registered test build,
serves exact fallback, exercises real re-consent/clear-data boundaries, and tears
down safely, with all slice gates and the final documentation comparison recorded.

#### Slice 8I reconciliation record — 2026-09-09

**Scope and baseline:** documentation only, based on clean `35082f2` on
`feat/stage-5-collaborative-and-hybrid-ranking`. That commit owns the passing
8H implementation; docs commit `d0e86f9` completed Phase 8. No runtime, configuration, schema, dependency or
test behavior changes are included. No Phase 9/10 work was started.

##### Required comparison inventory

Each row was checked against the committed implementation and retained 8H
execution, not inferred from the original proposed topology.

| Document | Outcome | Compared source and finding |
| --- | --- | --- |
| [Root README](../README.md) | Corrected | [Makefile](../Makefile), [root Compose](../docker-compose.yml), [8H evidence](evidence/stage-5-phase-8h.json): Phase 8 completion, combined command, explicit live-build capability and remaining release boundaries. Existing development startup commands reviewed/no-change. |
| [API README](../apps/api/README.md) | Corrected | [CLI parser](../apps/api/app/commands/collaborative_artifact.py), [operator safety](../apps/api/app/commands/operator_safety.py), [retirement service](../apps/api/app/services/collaborative_retirement.py): command context, test temporary-root paths, current evidence and lifecycle status. Endpoint/response contract reviewed/no-change. |
| [ML README](../ml/README.md) | Corrected | [interaction contract](../ml/src/gamelens_recommender/interaction_snapshot.py), [CLI parser](../apps/api/app/commands/collaborative_artifact.py), [8H evidence](evidence/stage-5-phase-8h.json): completion and ML count; frozen policies, caps, fixture audit/build/validate/inspect syntax reviewed/no-change. |
| [Web README](../apps/web/README.md) | Corrected | [package scripts](../apps/web/package.json), [Playwright configuration](../apps/web/playwright.config.ts), [content runner](../infra/run-e2e-content.sh), [lifecycle runner](../infra/run-e2e-lifecycle.sh): current browser evidence, ownership-aware direct command and separate contribution authority. |
| [Infra README](../infra/README.md) | Corrected | [E2E Compose](../infra/docker-compose.e2e.yml), [combined runner](../infra/run-phase8.py), [ownership helper](../infra/e2e-ownership.sh): current schema head, mode selection, paths, build/validation ordering, restart and teardown, measured host limitations and resumed execution. |
| [Scripts README](../scripts/README.md) | Corrected | [Makefile](../Makefile) and [infra runner](../infra/run-phase8.py): scripts directory remains reserved; actual orchestration lives under infra and requires repository-root invocation. |
| [Data README](../data/README.md) | Corrected | [cohort helper](../apps/api/tests/fixtures/collaborative_lifecycle.py), [live probe](../apps/api/tests/fixtures/e2e_live_source.py), [lifecycle helper](../apps/api/tests/fixtures/e2e_lifecycle.py): JSON versus real database-derived source, guards, database-time eligibility, separate authority, lineage and aggregate-only outputs. External-source policy reviewed/no-change. |
| [Fixture README](../data/fixtures/README.md) | Corrected | [JSON fixture](../data/fixtures/interactions/collaborative-interactions.json), [cohort helper](../apps/api/tests/fixtures/collaborative_lifecycle.py): implemented loader/build language and distinct synthetic PostgreSQL cohort; fixture cannot receive live registry status. |
| [Architecture](architecture.md) | Corrected | [component factory](../apps/api/app/services/recommendation/application.py), [lifecycle service](../apps/api/app/services/collaborative_lifecycle.py), [isolation probe](../apps/api/tests/fixtures/e2e_isolation.py): full-stack completion, one-time selection and ordinary-operation immutability. Component and registry boundaries reviewed/no-change. |
| [Data model](data-model.md) | Corrected | [migrations](../apps/api/alembic/versions), [registry repository](../apps/api/app/repositories/collaborative_registry.py), [8H evidence](evidence/stage-5-phase-8h.json): historical count labelled, current head and PostgreSQL evidence; no new schema or event contract. |
| [Recommendation design](recommendation-design.md) | Corrected | [fallback/fixture probe](../apps/api/tests/fixtures/e2e_fixture_stack.py), [response projection](../apps/api/app/services/recommendation/projection.py): full-stack completion; scoring/response/event semantics reviewed/no-change. |
| [Roadmap](roadmap.md) | Corrected | [8H evidence](evidence/stage-5-phase-8h.json) and this ledger: Phase 8 complete, Stage 5 pending Phases 9–10, Stage 6 quality handoff provisional. |
| [Stage 5 plan](#15-implementation-phase-8-docker-configuration-and-full-stack-fixtures), Section 15 | Corrected | [combined runner](../infra/run-phase8.py) and [8H evidence](evidence/stage-5-phase-8h.json): measured completion, counts, replays, host and interruption caveats. |
| Stage 5 plan, Section 18 | Corrected | [Makefile](../Makefile), [artifact parser](../apps/api/app/commands/collaborative_artifact.py), [audit parser](../apps/api/app/commands/collaborative_snapshot.py): actual runner equivalents, shell/working-directory requirements, summary versus JSON output, exact placeholders. |
| Stage 5 plan, Section 21 | Corrected | [8H evidence](evidence/stage-5-phase-8h.json) and owning `35082f2`: as-built decisions and execution deviations; remaining release requirements separated. |
| Stage 5 plan, Section 22 | Corrected | Phase 8 synthetic functional evidence acknowledged; final Stage 6 handoff remains provisional until Stage 5 acceptance/release gates pass. |
| Stage 5 plan, Section 23 | Reviewed/no-change to pending status; references corrected | Full Stage 5 completion remains pending; Phase 8 evidence does not finalize the release inventory. |
| Phase 8 plan and slice ledger (now Section 15) | Corrected | Git history resolves 8G to `693808f` and 8H to `35082f2`; original survey and older verification records remain explicitly historical. All slice statuses and current handoff reconciled. |
| Configuration descriptions across the inventory | Reviewed/no-change to configuration | [.env.example](../.env.example), [Settings](../apps/api/app/core/config.py), [root Compose](../docker-compose.yml), [test Compose](../infra/docker-compose.test.yml), [E2E Compose](../infra/docker-compose.e2e.yml), [frozen constants](../ml/src/gamelens_recommender/interaction_snapshot.py): blank optional path; separate default-off extraction/promotion, contribution version and test-only fixture gate; mutual exclusion; normal services force fixture off; minima 2/2/2 and 10/20/5 are constants, not environment knobs. Server authority stays out of `NEXT_PUBLIC_*`. |

##### Verification and evidence provenance

The retained 8H record was reconciled with all 57 local logs: every SHA256,
expected/actual exit and privacy-scan result matched. Recorded command durations
sum to 4357.03 seconds. Test summaries confirm 502 API unit, 333 ML, 151
PostgreSQL integration, 86 web unit, 38 inherited browser, 18 fixture/fallback
browser and 26 lifecycle phases in each of two replays. These are 8H results,
not newly executed 8I test counts. Existing earlier-phase counts remain labelled
as historical; no current release/security or quality claim is inferred from them.

The commands newly documented here are the exact Make/runner equivalents already
executed in 8H. Native PowerShell operator examples describe parser syntax with
operator-selected paths, not a claim of a verified native filesystem build.
No new PostgreSQL/live-source/browser build was needed for prose reconciliation,
as required by the 8I gate. Existing command/isolation regression tests were run
as a focused supplemental check; no tests were added for documentation changes.

| 8I check | Result |
| --- | --- |
| Local-link targets/Markdown heading anchors, balanced fences and formatting review of every changed document | Passed: 159 local links across 14 Markdown documents. |
| From `apps/web`: `node node_modules/prettier/bin/prettier.cjs --check README.md` | Passed after formatting. |
| PowerShell AST parse of API README command blocks; documented Make/runner equality and Python AST check | 20 PowerShell blocks and 5 exact runner equivalents passed; combined Python runner syntax passed. |
| Root Compose (`model`, `quality`, `source-audit`), test Compose, E2E content, fixture, fixture+fallback, live-source and lifecycle `config --quiet` | Passed. Fallback requires the fixture profile, as selected by its runner. |
| Individual `sh -n` checks for the five E2E runners and shared ownership helper | Passed. |
| `docker compose --profile quality run --rm --no-deps quality python -m pytest tests/unit/test_collaborative_artifact_command.py tests/unit/test_collaborative_artifact_entrypoint.py tests/unit/test_e2e_isolation.py -q -p no:cacheprovider` | 49 passed in 36.69s; CLI/runner/Make comparison passed. |
| `git diff --check` and final staged diff review | Passed; documentation only. |

**Review fixes and deviations:** corrected stale completion and fixture-only
build claims, obsolete schema-head/browser descriptions, operator path/context
ambiguity and the old direct Compose browser invocation. An initial standalone
`fallback` profile parse failed because it depends on `fixture`; checking the
actual runner combination passed. This was a verification invocation correction,
not a topology change. Prettier initially could not resolve its plugin when
invoked from the repository root; running it from `apps/web`, as required by the
package workflow, passed. All 8H interruption/recovery and platform limitations
remain visible. No slice scope deviation; no new live build or next slice.

The remaining implementation must resolve and record:

1. Product contribution-consent copy, public grant/re-consent/withdrawal routes,
   and approval to audit an actual live cohort. Saved personalization must
   remain a separate purpose.
2. Actual approved live cohort/exclusion aggregates and the explicit decision to
   activate live build or remain fixture-only.
3. Phases 9–10 final dependency/license, security, coverage, acceptance inventory
   and release documentation. Phase 8 guarded fixture/live-source topology,
   hybrid/fallback/lifecycle browser acceptance and isolation are now verified;
   their evidence does not substitute for these remaining release gates.

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
Phases 5–7 have verified lifecycle registry/readiness, synchronized public
response/event projection, generated client ownership, cautious browser
presentation, and guarded operator lifecycle safety. The handoff is not final:
Phase 8 has completed guarded full-stack browser acceptance and reproducible
isolation checks over synthetic data. Phases 9–10 must still complete the full
release gate and final documentation; this Stage 6 handoff remains provisional.
Before Stage 5 is marked complete, this section must change from “should leave”
to verified facts only.

## 23. Verified Completion Record

Pending complete Stage 5 implementation. The verified Phase 0–7 source/audit,
offline-artifact, pure-scoring, hybrid-policy, lifecycle-readiness,
internal-orchestration, response/event, generated-client, and
browser-presentation, and operator-lifecycle slices, plus the completed Phase 8
isolation/documentation handoff, are recorded in Section 21 and the slice ledger;
they are not a Stage 5 completion claim.

When every Section 19 gate passes, this section must record the implementation
commit/PR, runtime and lock versions, migration head, consent/lifecycle
decision, data audit, snapshot and artifact identities/sizes, aggregate label
counts, deterministic examples, exact commands, test counts, coverage,
durations, Compose and image checks, browser/accessibility evidence, dependency
and privacy review, limitations, and the finalized Stage 6 handoff. It must not
contain invented values or formal ranking-quality claims.
