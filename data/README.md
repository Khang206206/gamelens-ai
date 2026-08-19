# Data

This area holds project-owned development data and documents the policy for
future imported datasets.

Locations are:

- `seed/games.json` contains the Stage 1 deterministic catalog: 30 fictional,
  project-authored games and their explicit taxonomy references.
- `raw/` for immutable local source data that is normally ignored by Git.
- `processed/` for reproducible generated datasets that are ignored by Git.

Generated directories will be created when their first real artifact is added.
Every external dataset must record its source, license, retrieval date, and
transformation steps. Copyrighted cover images must not be committed.

The Stage 1 seed has no external source, cover binaries, or real-world
performance claims. It is distributed under the repository license and is
intended only for repeatable local development and tests.

## Planned Stage 5 interaction data

The
[Stage 5 collaborative-and-hybrid plan](../docs/stage-5-collaborative-hybrid-ranking-plan.md)
defines a future interaction-data boundary. No external or real-user
interaction dataset is currently committed, downloaded, or integrated. Local
Stage 4 sessions are application state, not an approved training dataset.

Stage 5 may add a deterministic project-authored multi-user fixture under
`seed/` for exact snapshot, cosine, hybrid, fallback, and lifecycle tests. Its
records must be visibly synthetic and isolated from ordinary development
seeding. A fixture artifact may load only in a disposable test/E2E environment
with an explicit test-only flag; development and production must reject it.
Passing tests on that fixture is functional evidence only.

An approved external or project-authored materialized snapshot belongs under
ignored `processed/` storage and must record source kind, source/license
authority, retrieval cutoff, catalog fingerprint, label/filter configuration,
transformation version, aggregate counts, and checksum. A live PostgreSQL
snapshot is instead streamed through bounded build memory and removed on both
success and failure; only its aggregate audit, lineage, fingerprint, and final
item-level artifact may remain. The guarded builder may use internal IDs
transiently for grouping but must not serialize IDs, token digests,
credentials, stable user pseudonyms, raw per-user mappings, or a reusable live
row-level snapshot.

Cleared feedback, consent withdrawal, revocation, expiry, retention, and user
deletion must affect snapshot eligibility and invalidate any affected
serveable artifact. If that lifecycle cannot be proven, live-data training
stays disabled. Every future external source additionally requires its exact
URL/owner, license, retrieval date, original checksum, catalog-mapping rules,
transformations, redistribution policy, and limitations before ingestion.
