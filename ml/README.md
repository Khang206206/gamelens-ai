# Machine-learning workspace

**Status:** Stage 3 content recommendation MVP complete and verified 2026-08-07.

This directory owns deterministic catalog normalization, the popularity
baseline, TF-IDF feature construction, sparse artifact serialization, pure
ranking logic, and ML tests. The API owns PostgreSQL snapshot extraction, HTTP
orchestration, and catalog response models; the browser never trains or ranks.
The complete decision and verification record is in the
[Stage 3 plan](../docs/stage-3-content-recommendation-mvp-plan.md).

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

The Stage 3 gate passes 25 ML tests with 81% diagnostic branch-aware package
coverage.

On the 30-game seed fixture, the verified bundle contains 1,037 vocabulary
terms and 1,399 sparse nonzeros, occupies 69,743 bytes, and built from the
database in 0.43 seconds. Ten complete validation loads from the Docker Desktop
bind mount had min/median/max latency of 89.64/95.54/274.79 ms. These are local
diagnostics, not performance guarantees or recommendation-quality evidence.

Persistent preferences and feedback begin in Stage 4, collaborative filtering
in Stage 5, and formal offline ranking evaluation in Stage 6.
