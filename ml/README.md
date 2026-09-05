# Machine-learning workspace

**Status:** Stage 4 feedback policy complete and verified 2026-08-13; Stage 5
external-source preflight and implementation Phases 0–7 verified through
2026-09-03; Phase 8 Docker, configuration, and full-stack fixtures is next.

This directory owns deterministic catalog normalization, the popularity
baseline, TF-IDF feature construction, sparse artifact serialization, pure
ranking logic, and ML tests. The API owns PostgreSQL snapshot extraction, HTTP
orchestration, and catalog response models; the browser never trains or ranks.
The complete decision and verification record is in the
[Stage 3 plan](../docs/stage-3-content-recommendation-mvp-plan.md).

The
[Stage 4 feedback-and-persistence plan](../docs/stage-4-feedback-persistence-plan.md)
is complete and verified. The package now exposes a pure feedback-aware ranker
in addition to the unchanged Stage 3 request-scoped ranker. It still receives no
user identity or mutable database object and stores no durable state.

The detailed
[Stage 5 collaborative-and-hybrid plan](../docs/stage-5-collaborative-hybrid-ranking-plan.md)
is being implemented in reviewable phases. The package now contains canonical
interaction-profile serialization, fingerprinting, bounded aggregate auditing, a
strict project-authored fixture loader, the sparse item-item trainer, and the
separate collaborative artifact builder/validator/loader. It also exposes the
Phase 3 canonical source selector, bounded CSR lookup/scorer, and exact-row base
and affinity materializers plus the Phase 4 `gamelens-hybrid-ranking/1.0.0`
policy. Phase 5 consumes these pure contracts from the API through optional
lifecycle readiness and internal saved-request orchestration. Phase 6 exposes
the resulting decision through synchronized saved response/event and browser
contracts. Phase 7 connects the existing pure ML build contract to guarded API
operator lifecycle commands without adding online fitting or mutable model state.
No product contribution-consent flow or approved production live cohort exists.

## Stage 5 Phase 0–1 interaction audit

`gamelens-collaborative-labels/1.0.0` treats a saved positive game preference,
an active like, or an active rating of at least 7 as one binary positive edge.
An active dislike dominates every positive source. Low ratings, views,
played-only state, wishlist-only state, recommendation events, non-game
preferences, superseded rows, post-cutoff rows, and ineligible contributors do
not become positives.

The API supplies only a sorted multiset of sorted stable-slug profiles plus the
exact content-catalog fingerprint. This package never receives a credential or
emits an internal user ID/cohort mapping. It computes a fixed canonical
interaction fingerprint, bounded aggregate distributions, deterministic two-core
support diagnostics, and typed insufficiency reasons without writing a row-level
snapshot.

Fixture reads are capped at 1,000,000 bytes and reject duplicate or unrecognized
schema keys, non-finite constants, and bool/int/float JSON type aliases before
audit.

The test-only fixture audit is:

```powershell
make collaborative-fixture-audit
```

The verified fixture has 12 profiles, 36 positive edges, and 6 items and passes
the functional activation thresholds. The report always keeps
`approved_live_training_eligibility=false`; this result is neither live-data
approval nor recommendation-quality evidence.

## Stage 5 Phase 2 collaborative artifact

The implemented baseline consumes identity-free profiles, applies the same
deterministic user/item support fixed point as the audit, and builds a canonical
binary `int64` CSR. Bounded sparse pair counts produce raw cosine similarities;
self-edges and pair support below two are removed. Similarities are quantized
round-half-up at scale 1,000,000. Top neighbors are selected by similarity, pair
support, then stable slug and serialized in canonical neighbor-index order. The
fixture resolves to 12 retained profiles, 6 items, 36 positives, and 20 directed
neighborhood edges.

Model `gamelens-item-item-cosine` version `1.0.0` uses artifact schema `1` and
code compatibility `stage-5-v1`. Its exact directory members are:

```text
manifest.json
item-slugs.json
item-support.npy
neighbors-indices.npy
neighbors-indptr.npy
similarity-units.npy
pair-support.npy
```

The manifest binds configuration, aggregate diagnostics, catalog and interaction
fingerprints, source/build identity, validity horizon, exact member sizes, and
SHA-256 checksums. The artifact excludes the contributor matrix, internal IDs,
stable user keys, credentials, interaction rows, and recommendation events. The
bounded loader disables pickle and rejects an unexpected member set, symlinks,
traversal, malformed JSON/NPY, checksum or dtype/shape mismatch, noncanonical
CSR, invalid support/cosine values, catalog or revision mismatch, and expiry.
Returned arrays have immutable byte backing.

The guarded functional workflow is:

```powershell
make collaborative-build
make collaborative-validate
docker compose --profile quality run --rm --no-deps `
  -e COLLABORATIVE_ALLOW_TEST_FIXTURE=true quality `
  python -m app.commands.collaborative_artifact inspect
```

Fixture build requires `ENVIRONMENT=test` and the explicit fixture gate,
validates a temporary sibling with the production loader, and promotes only to
an unused path. The API's separate live operator path remains default-off and
requires explicit live-data, consent-version, promotion, build-ID, and exact-
confirmation gates before this same builder can receive an eligible PostgreSQL
snapshot. Validation and inspection bind the artifact to the catalog read from
`--catalog`, which defaults to the canonical seed file.

## Stage 5 Phase 3 pure collaborative scoring

`canonicalize_collaborative_query_sources()` applies dislike, liked/rating,
saved-game precedence, recency/slug ordering, deduplication, and fixed caps
before artifact access. `CollaborativeScorer` then visits only exact CSR source
rows and at most 1,000 stored edges, computes round-half-up integer means from
present similarities, excludes every query source and dislike, and returns
stable candidates with complete contributing-edge evidence, pair support,
bounded diagnostics, policy identity, and typed no-support reasons.

`ContentRanker.materialize_base_candidates()` and
`FeedbackRanker.materialize_affinity_candidates()` score an exact bounded slug
set without changing Stage 3/4 eligibility or final ranking wrappers. The
fixture handoff proves `starbound-couriers` can arrive with zero content units
and exact collaborative/content/platform/popularity/base/affinity units
`428571/0/1000000/599117/159912/0`. Candidate union, weights, played adjustment
after hybrid blending, final rank, and fallback are implemented by Phase 4.

## Stage 5 Phase 4 hybrid policy

`HybridRanker` unions exact content/base, affinity, and collaborative candidates
by stable slug before final top-K. With an active affinity profile it applies
base/affinity/collaborative weights `800000/100000/100000`; without one it uses
`900000/0/100000`. Contributions use the shared round-half-up 1,000,000 scale,
then the `500000` played factor applies once. Complete structured evidence,
candidate origin, component identities, and deterministic cautious prose make
every score reconstructible.

Every typed unavailable or no-support collaborative outcome returns a
`Stage4FallbackResult` containing the exact unchanged Stage 4 result. Query-
source/dislike context mismatches fail as invalid input rather than silently
fall back. The production-loaded fixture proves a collaborative-only candidate
can enter the union, but it remains functional evidence rather than a quality
comparison.

Phase 5 now supplies the loader, lifecycle readiness, and saved-request
orchestration around this package. Phase 6 maps the complete hybrid decision to
one public response and matching `stage-5-v1` event. Matrix factorization,
neural models, online fitting, shrinkage tuning, and formal quality evaluation
remain outside this phase.

## UCSD Steam source preflight

`gamelens_recommender.ucsd_steam` uses only the Python 3.12 standard library.
The audit runtime never downloads source data, rewrites or extracts the pinned
archives, fits or promotes a model, or deletes data. It first verifies the
manifest and every compressed size and SHA-256, streams each gzip member through
manifest-specific shape bounds capped at 2 MiB per line and 2 GB per member,
then rechecks compressed identity after scanning. Loose Python-literal records
are parsed with `ast.literal_eval`, never `eval`.

The dedicated `ucsd-source-audit` service mounts `data/` and `ml/` read-only,
has a read-only root filesystem, and disables runtime networking.
`docker compose ... --build` may still obtain image dependencies; the audit
module itself has no source-download path.

`prepare` emits source-schema and v1-to-v2 alignment aggregates only. `audit`
additionally collapses duplicate source user/item reviews, treats
`recommend=true` as a preparation-only candidate signal, and measures sparse
support after deterministic user/item fixed-point pruning. Ownership, playtime,
and `recommend=false` never become candidates. Source user keys exist only in
bounded process memory and neither the command nor its report writes a row-level
snapshot or emits an identifier.

Run the pinned-container human summaries from the repository root:

```powershell
make ucsd-steam-verify
make ucsd-steam-prepare
make ucsd-steam-audit
make ucsd-steam-audit-check
```

The full container command that emits deterministic machine-readable JSON is:

```powershell
docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam audit --root /workspace --format json
```

The exact no-write comparison with the committed aggregate report is:

```powershell
docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam audit --root /workspace --check-report data/external/ucsd-steam/suitability-audit.json --format summary
```

Replace `audit` with `verify` or `prepare` for the other reports.
`make ucsd-steam-audit-check` reruns the audit and compares its JSON by
canonical JSON type and value with the committed report; a mismatch is the typed
`report_mismatch` error. The local ignored archives must already exist at the
manifest paths. The aggregate
[source-v1 report](../data/external/ucsd-steam/suitability-audit.json) records
the verified 2026-08-23 run. Passing its source-only support thresholds does not
approve a label or integration: no Stage 5 label authority, dataset
license/redistribution grant, ingestion-approved provenance, GameLens Steam-ID
mapping, UCSD-backed activatable fixture evidence, or live consent/lifecycle
proof is recorded.

## Package and reproducibility

`gamelens-recommender` targets Python 3.12 and exactly pins NumPy 2.5.1, SciPy
1.18.0, and scikit-learn 1.9.0. `requirements.lock` also pins the quality and
transitive graph. pandas is intentionally absent: the canonical snapshot and
sparse feature pipeline do not require a dataframe dependency.

Catalog records are sorted by stable game slug and normalized with NFKC plus
collapsed whitespace before canonical JSON serialization and SHA-256
fingerprinting. Feature documents repeat title twice, genre and tag tokens three
times, and developer, publisher, and description once. The word TF-IDF space
uses one- and two-grams, sublinear term frequency, L2 normalization, and float64
values.

The popularity baseline applies a 50-vote Bayesian rating prior against the
catalog-weighted mean, min-max normalizes rating and the synthetic popularity
signal, and combines them at 70% and 30%. A constant input range maps to 0.5.

## Ranking

The anonymous content vector is the normalized selected-game centroid or the
taxonomy preference vector. When both exist they contribute 65% and 35% before
renormalization. Candidate scores combine content 80%, preferred-platform
overlap 10%, and popularity 10%.

All ordering inputs are quantized to a fixed scale of 1,000,000 using
round-half-up. Ties resolve by final score, content score, popularity score,
then stable slug. Selected games and candidates with zero content support are
excluded. Returned prose is generated only from the same structured evidence
that accompanies each score.

## Stage 4 feedback policy

`FeedbackRanker` implements policy `gamelens-feedback-adjustment/1.0.0` over the
immutable Stage 3 artifact. Saved preferences produce the base context; dislikes
are hard exclusions; likes and ratings of at least 7 (when no reaction exists)
produce a deduplicated, most-recent-five artifact-vector profile. Positive
source games are excluded from their own results. When that profile exists, base
and affinity scores blend at 90% and 10%; otherwise the exact base score/order
is retained. Played candidates remain eligible with a 0.5 factor, while wishlist
is neutral. Filtering and adjustment occur before top-K.

The policy receives only stable slugs and immutable bounded feedback context. It
never receives an internal user ID, raw/digested credential, consent metadata,
or mutable database object, and it never writes into an artifact. Every
intermediate uses the 1,000,000 fixed scale and round-half-up contributions.
Ordering resolves by final score, pre-played score, base score, affinity,
content, popularity, then stable slug. Returned evidence separately exposes
base, affinity, and played contributions.

`ContentRanker.score_candidates()` and `materialize_candidate()` expose the
pre-top-K boundary needed by feedback ranking. The Stage 3 `rank()` wrapper,
model `gamelens-content-tfidf/1.0.0`, artifact schema `1`, and compatibility
`stage-3-v1` remain unchanged.

## Content artifact contract

Model `gamelens-content-tfidf` version `1.0.0` uses artifact schema `1` and code
compatibility `stage-3-v1`. A bundle contains `manifest.json`, three transparent
JSON members, and five non-pickle NPY arrays for TF-IDF and CSR data. The loader
uses `allow_pickle=False`, checks the exact member set, sizes, SHA-256 digests,
dtypes, shapes, finite values, canonical CSR indices, non-negative feature
weights, IDF weights of at least one, L2-normalized rows, feature configuration,
resource caps, and catalog fingerprint before returning immutable arrays. Builds
write a temporary sibling and promote only after validation.

Generated bundles live under ignored `ml/artifacts/`; only `.gitkeep` is
tracked. Build and validate against the migrated and seeded development database
from the repository root:

```powershell
docker compose up -d db
docker compose run --build --rm api python -m alembic upgrade head
docker compose run --build --rm api python -m app.db.seed
docker compose --profile model run --build --rm model-builder `
    python -m app.commands.recommendation_artifact build
docker compose --profile model run --rm --no-deps model-builder `
    python -m app.commands.recommendation_artifact validate
```

Both commands consume the same `MODEL_ARTIFACT_PATH` as the API. Bundles are
immutable: rotate that setting to a new directory before rebuilding, validate
it, then recreate the API. The previous directory remains available for an
explicit rollback. Because the hardened loader now rejects non-canonical CSR
matrices, operators upgrading an existing Stage 3 bundle must rotate and rebuild
it rather than patch or overwrite the old directory.

Run the focused suite with `make test-ml`, or directly:

```powershell
docker compose run --build --rm --no-deps quality `
    python -m pytest /workspace/ml/tests -q -p no:cacheprovider
```

The Stage 3 gate passed 25 ML tests with 81% diagnostic branch-aware package
coverage. The current Phase 6 handoff passes the complete 331-test ML suite with
one symbolic-link rejection case capability-skipped on this Windows host; that
case remains runnable on systems that permit symlink creation. Cross-stack
evidence also passes 365 API unit, 109 disposable-PostgreSQL, and 86 web tests.
Ruff lint and format checks pass across 172 Python files, and generated OpenAPI
types have no drift. No new ML dependency or diagnostic coverage percentage was
introduced for Phase 6. The 38-case exact-host Docker browser matrix passes in
1.3 minutes without retry. The rebuilt no-cache `gamelens-ai-api:stage4-test`
image with digest prefix `11b2f940731e` removes unused Debian `perl-base` after
all install steps, resolving its earlier two critical and two high findings.
Runtime imports, `pip check`, and all 49 PostgreSQL tests remain green. Its
comprehensive Docker Scout scan reports 0 critical, 0 high, 3 medium, 27 low,
and 2 unspecified findings across 193 packages; its only-fixed scan reports no
actionable fixed advisory. Final release diff/privacy review is clean.

On the 30-game seed fixture, the verified bundle contains 1,037 vocabulary terms
and 1,399 sparse nonzeros, occupies 69,743 bytes, and built from the database in
0.43 seconds. Ten complete validation loads from the Docker Desktop bind mount
had min/median/max latency of 89.64/95.54/274.79 ms. These are local
diagnostics, not performance guarantees or recommendation-quality evidence.

Persistent preferences and lifecycle lineage live in the API/database rather
than this package. The collaborative artifact, pure scorer/materializers, and
hybrid ranking policy are implemented and consumed by Phase 5 internal API
orchestration. Phase 6 public personalized hybrid response/event fields and
conditional browser evidence consume those pure outputs without changing ML.
Formal offline ranking evaluation remains roadmap Stage 6 work. The synthetic
catalog and authored interaction fixture validate deterministic behavior only,
not recommendation quality.
