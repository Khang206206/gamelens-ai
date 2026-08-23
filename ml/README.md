# Machine-learning workspace

**Status:** Stage 4 feedback policy complete and verified 2026-08-13; Stage 5
external-source preflight slice verified 2026-08-23.

This directory owns deterministic catalog normalization, the popularity
baseline, TF-IDF feature construction, sparse artifact serialization, pure
ranking logic, and ML tests. The API owns PostgreSQL snapshot extraction, HTTP
orchestration, and catalog response models; the browser never trains or ranks.
The complete decision and verification record is in the
[Stage 3 plan](../docs/stage-3-content-recommendation-mvp-plan.md).

The
[Stage 4 feedback-and-persistence plan](../docs/stage-4-feedback-persistence-plan.md)
is complete and verified. The package now exposes a pure feedback-aware ranker in
addition to the unchanged Stage 3 request-scoped ranker. It still receives no
user identity or mutable database object and stores no durable state.

The detailed
[Stage 5 collaborative-and-hybrid plan](../docs/stage-5-collaborative-hybrid-ranking-plan.md)
is ready. The package now contains only the read-only UCSD Steam
source-verification, preparation, and aggregate-audit slice of Phases 0–1. No
collaborative trainer, artifact, loader, scorer, hybrid policy, consent-aware
live extractor, versioned activatable Stage 5 interaction fixture, guarded
fixture E2E evidence, or serveable Stage 5 snapshot exists. The focused unit
tests use a separate in-process synthetic source fixture.

## Planned Stage 5 scope

The proposed baseline is binary sparse item-item cosine over a consent- and
retention-qualified snapshot supplied by the API extractor. It will keep raw
cosine, minimum user/item/pair support, deterministic top-neighbor pruning,
the existing fixed scale, and stable-slug ties. Matrix factorization, neural
models, online fitting, shrinkage tuning, and formal quality evaluation remain
outside this stage.

Stage 5 plans a separate transparent collaborative bundle containing only
item neighborhoods, item/pair support, configuration, catalog and interaction
fingerprints, aggregate diagnostics, lifecycle identity, and checksums. It
will not contain the user matrix, internal IDs, stable pseudonyms, credentials,
raw interactions, or recommendation events. The different artifact is needed
because consent, deletion, freshness, invalidation, and rebuild differ from
the catalog-content lifecycle.

A pure collaborative scorer will expose supported neighbor evidence, and a
versioned hybrid policy will combine base, feedback-affinity, collaborative,
and played components once. Unsupported or invalid collaborative state must
return exact Stage 4 ranking through an explicit fallback. These are planned
contracts, not current package behavior or recommendation-quality claims.

## UCSD Steam source preflight

`gamelens_recommender.ucsd_steam` uses only the Python 3.12 standard library.
The audit runtime never downloads source data, rewrites or extracts the pinned
archives, fits or promotes a model, or deletes data. It first verifies the
manifest and every compressed size and SHA-256, streams each gzip member
through manifest-specific shape bounds capped at 2 MiB per line and 2 GB per
member, then rechecks compressed identity after scanning. Loose Python-literal
records are parsed with `ast.literal_eval`, never `eval`.

The dedicated `ucsd-source-audit` service mounts `data/` and `ml/`
read-only, has a read-only root filesystem, and disables runtime networking.
`docker compose ... --build` may still obtain image dependencies; the audit
module itself has no source-download path.

`prepare` emits source-schema and v1-to-v2 alignment aggregates only.
`audit` additionally collapses duplicate source user/item reviews, treats
`recommend=true` as a preparation-only candidate signal, and measures sparse
support after deterministic user/item fixed-point pruning. Ownership, playtime,
and `recommend=false` never become candidates.
Source user keys exist only in bounded process memory and neither the command
nor its report writes a row-level snapshot or emits an identifier.

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
docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam audit --root /workspace --check-report data/audits/ucsd-steam/source-v1-suitability.json --format summary
```

Replace `audit` with `verify` or `prepare` for the other reports.
`make ucsd-steam-audit-check` reruns the audit and compares its JSON
by canonical JSON type and value with the committed report; a mismatch is the typed
`report_mismatch` error. The local ignored archives must already exist at the
manifest paths. The aggregate
[source-v1 report](../data/audits/ucsd-steam/source-v1-suitability.json)
records the verified 2026-08-23 run. Passing its source-only support thresholds
does not approve a label or integration: no Stage 5 label authority, dataset
license/redistribution grant, ingestion-approved provenance, GameLens Steam-ID
mapping, activatable Stage 5 fixture evidence, or live consent/lifecycle proof
is recorded.

## Package and reproducibility

`gamelens-recommender` targets Python 3.12 and exactly pins NumPy 2.5.1, SciPy
1.18.0, and scikit-learn 1.9.0. `requirements.lock` also pins the quality and
transitive graph. pandas is intentionally absent: the canonical snapshot and
sparse feature pipeline do not require a dataframe dependency.

Catalog records are sorted by stable game slug and normalized with NFKC plus
collapsed whitespace before canonical JSON serialization and SHA-256
fingerprinting. Feature documents repeat title twice, genre and tag tokens
three times, and developer, publisher, and description once. The word TF-IDF
space uses one- and two-grams, sublinear term frequency, L2 normalization, and
float64 values.

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

`FeedbackRanker` implements policy
`gamelens-feedback-adjustment/1.0.0` over the immutable Stage 3 artifact. Saved
preferences produce the base context; dislikes are hard exclusions; likes and
ratings of at least 7 (when no reaction exists) produce a deduplicated,
most-recent-five artifact-vector profile. Positive source games are excluded
from their own results. When that profile exists, base and affinity scores
blend at 90% and 10%; otherwise the exact base score/order is retained. Played
candidates remain eligible with a 0.5 factor, while wishlist is neutral.
Filtering and adjustment occur before top-K.

The policy receives only stable slugs and immutable bounded feedback context.
It never receives an internal user ID, raw/digested credential, consent
metadata, or mutable database object, and it never writes into an artifact.
Every intermediate uses the 1,000,000 fixed scale and round-half-up
contributions. Ordering resolves by final score, pre-played score, base score,
affinity, content, popularity, then stable slug. Returned evidence separately
exposes base, affinity, and played contributions.

`ContentRanker.score_candidates()` and `materialize_candidate()` expose the
pre-top-K boundary needed by feedback ranking. The Stage 3 `rank()` wrapper,
model `gamelens-content-tfidf/1.0.0`, artifact schema `1`, and compatibility
`stage-3-v1` remain unchanged.

## Artifact contract

Model `gamelens-content-tfidf` version `1.0.0` uses artifact schema `1` and code
compatibility `stage-3-v1`. A bundle contains `manifest.json`, three transparent
JSON members, and five non-pickle NPY arrays for TF-IDF and CSR data. The loader
uses `allow_pickle=False`, checks the exact member set, sizes, SHA-256 digests,
dtypes, shapes, finite values, canonical CSR indices, non-negative feature
weights, IDF weights of at least one, L2-normalized rows, feature configuration,
resource caps, and catalog fingerprint before returning immutable arrays.
Builds write a temporary sibling and promote only after validation.

Generated bundles live under ignored `ml/artifacts/`; only `.gitkeep` is
tracked. Build and validate against the migrated and seeded development
database from the repository root:

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
matrices, operators upgrading an existing Stage 3 bundle must rotate and
rebuild it rather than patch or overwrite the old directory.

Run the focused suite with `make test-ml`, or directly:

```powershell
docker compose run --build --rm --no-deps quality `
    python -m pytest /workspace/ml/tests -q -p no:cacheprovider
```

The Stage 3 gate passed 25 ML tests with 81% diagnostic branch-aware package
coverage. The current Stage 4 worktree passes 52 ML tests with 83% diagnostic
coverage plus Ruff lint and format checks across 112 Python files. Cross-stack
evidence also passes 184 fast API, 76 web, and 49 disposable-PostgreSQL tests.
The 38-case exact-host Docker browser matrix passes in 1.3 minutes without
retry. The rebuilt
no-cache `gamelens-ai-api:stage4-test` image with digest prefix `11b2f940731e`
removes unused Debian `perl-base` after all install steps,
resolving its earlier two critical and two high findings. Runtime imports,
`pip check`, and all 49 PostgreSQL tests remain green. Its comprehensive Docker
Scout scan reports 0 critical, 0 high, 3 medium, 27 low, and 2 unspecified
findings across 193 packages; its only-fixed scan reports no actionable fixed
advisory. Final release diff/privacy review is clean.

On the 30-game seed fixture, the verified bundle contains 1,037 vocabulary
terms and 1,399 sparse nonzeros, occupies 69,743 bytes, and built from the
database in 0.43 seconds. Ten complete validation loads from the Docker Desktop
bind mount had min/median/max latency of 89.64/95.54/274.79 ms. These are local
diagnostics, not performance guarantees or recommendation-quality evidence.

Persistent preferences live in the API/database rather than this package.
Collaborative filtering and hybrid ranking have a detailed Stage 5 plan but
are not implemented. Formal offline ranking evaluation remains Stage 6 work.
The synthetic catalog and any future authored interaction fixture validate
deterministic behavior only, not recommendation quality.
