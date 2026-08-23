# Data

This area holds project-owned development data and documents the policy for
future imported datasets.

Locations are:

- `seed/games.json` contains the Stage 1 deterministic catalog: 30 fictional,
  project-authored games and their explicit taxonomy references.
- `raw/` for immutable local source data that is normally ignored by Git.
- `processed/` for reproducible generated datasets that are ignored by Git.
- `audits/` for committed aggregate-only, non-row-level verification evidence.

Ignored local directories are created when their first source or generated
artifact is added. Every external dataset must record its source, license or
redistribution status, retrieval date, checksum, and transformation steps.
Copyrighted cover images must not be committed.

The Stage 1 seed has no external source, cover binaries, or real-world
performance claims. It is distributed under the repository license and is
intended only for repeatable local development and tests.

## Stage 5 interaction-source boundary

The
[Stage 5 collaborative-and-hybrid plan](../docs/stage-5-collaborative-hybrid-ranking-plan.md)
defines a future interaction-data boundary. No external or real-user
interaction dataset is committed or integrated. A local UCSD Steam source
snapshot may be placed under ignored `raw/` storage for Stage 5 pipeline work;
its presence does not make it a serveable or approved training artifact. Local
Stage 4 sessions are application state, not an approved training dataset.

### Local UCSD Steam source layout

The expected ignored source paths are:

```text
raw/ucsd-steam/
|-- v1-user-items/australian_users_items.json.gz
|-- v1-reviews/australian_user_reviews.json.gz
`-- v2-item-metadata/steam_games.json.gz
```

Keep these downloads compressed and immutable. Their exact source URLs,
source-page attribution, retrieval date, absence of recorded raw
transformations, compressed and expanded sizes, line counts, maximum line
sizes, and verified SHA-256 values are recorded in
[`manifests/ucsd-steam/source-v1.json`](manifests/ucsd-steam/source-v1.json).
The raw files remain ignored and must not be force-added to Git. Each source
directory contains only a tracked `.gitkeep` placeholder in the repository.

The upstream page identifies Version 1 review and user/item downloads plus
Version 2 item metadata, describes the files as loose JSON/Python
dictionaries, and requests citation. No dataset license or redistribution
grant is recorded in this repository. Citation is not a license grant, so
redistribution and ingestion stay blocked.

### Read-only verification and ingestion preparation

The standard-library workflow in
[`ucsd_steam.py`](../ml/src/gamelens_recommender/ucsd_steam.py) has three
report commands:

```powershell
make ucsd-steam-verify
make ucsd-steam-prepare
make ucsd-steam-audit
make ucsd-steam-audit-check
```

The dedicated `ucsd-source-audit` runtime mounts `data/` and `ml/`
read-only, uses a read-only root filesystem, and has networking disabled.
`verify` checks the fail-closed manifest, all compressed sizes and SHA-256
values, gzip CRC/shape, line counts, expanded sizes, and maximum line sizes,
then repeats the compressed identity check after scanning. `prepare` verifies
every archive before streaming bounded records through `ast.literal_eval`;
it never uses `eval`. It emits schema, duplicate, validity, and v1-to-v2
source alignment aggregates. `audit` adds deterministic fixed-point support
distributions and a fingerprint over the sorted multiset of candidate
profiles.

The exact container command used to emit machine-readable audit JSON is:

```powershell
docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam audit --root /workspace --format json
```

The exact no-write comparison with the committed aggregate report is:

```powershell
docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam audit --root /workspace --check-report data/audits/ucsd-steam/source-v1-suitability.json --format summary
```

The audit runtime is read-only: it has no source-download path and does not
decompress to disk, write a processed dataset, fit a model, promote an artifact,
or mutate PostgreSQL. The optional image build may obtain image dependencies.
Source user keys are private transient grouping keys and are absent from stdout
and the committed report. `make ucsd-steam-audit-check` canonically compares
a new audit with the committed JSON and exits two with `report_mismatch` if it
drifts.

### Verified aggregate audit

The committed
[`source-v1-suitability.json`](audits/ucsd-steam/source-v1-suitability.json)
is the exact aggregate JSON emitted on 2026-08-23 from the three local files
matching the manifest. The high-signal source profile is:

| Source member | Top-level records | Nested rows | Distinct source users/items |
| --- | ---: | ---: | ---: |
| v1 user/items | 88,310 | 5,153,209 items | 87,626 users; 10,978 items |
| v1 reviews | 25,799 | 59,305 reviews | 25,485 users; 3,682 items |
| v2 metadata | 32,135 | n/a | 32,132 distinct IDs; 32,131 unambiguous IDs |

The review rows collapse to 58,431 user/item pairs: 51,692 unambiguous
`recommend=true` candidate pairs, 6,739 false-only pairs, and no observed
true/false conflict. This is a project-defined preparation signal, not an
approved Stage 5 label. Ownership and all playtime values are profile-only
diagnostics and never candidate positives.

Unambiguous v2 metadata aligns with 47,492 candidate pairs across 23,127
source profiles and 2,869 source items. Three deterministic user/item
fixed-point passes leave 9,792 profiles, 33,049 edges, and 1,516 items; 6,481
item pairs have support of at least two. Matrix density is 0.002226320662. The
identity-free candidate-profile fingerprint is
`eafce3dcdd6cde57ec5eacf1746b83f0a3e269c0fc9069b2da2bf5d78ecd9f66`.

Those counts show only that a non-degenerate source-level sparse cohort can be
formed under the preparation policy. `ready_for_functional_build` and
`approved_training_eligibility` remain false. The catalog schema has a
nullable `external_id`; all 30 seed payloads omit that field and therefore use
its null default. No reviewed Steam mapping artifact is present. The audit
therefore attempts no GameLens mapping and reports zero target-mapped
pairs/items. Source
provenance is recorded but not approved for ingestion; Stage 5 label authority,
license/redistribution, catalog mapping, activatable fixture evidence, and live
consent/lifecycle evidence remain blocking gates.

Stage 5 may add a deterministic project-authored multi-user fixture under
`seed/` for exact snapshot, cosine, hybrid, fallback, and lifecycle tests. Its
records must be visibly synthetic and isolated from ordinary development
seeding. A fixture artifact may load only in a disposable test/E2E environment
with an explicit test-only flag; development and production must reject it.
Passing tests on that fixture is functional evidence only.
The in-process source fixtures in `ml/tests/test_ucsd_steam.py` are unit-test
inputs, not that versioned or activatable Stage 5 fixture.

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
stays disabled. Before any external source is ingested, it requires an exact
source URL and source attribution, verified rights-holder information where
applicable, approved license/redistribution authority, retrieval date, original
checksum, reviewed catalog-mapping rules, transformations, limitations, and
evidence for the applicable activation and lifecycle gates.
