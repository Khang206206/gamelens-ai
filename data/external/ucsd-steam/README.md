# UCSD Steam source evidence

**Status: verified local source identity; integration blocked.**

This directory keeps reviewable metadata and aggregate-only evidence for the
read-only UCSD Steam source preflight. It does not contain a redistributable or
approved training dataset.

Tracked files:

- [`manifest.json`](manifest.json) pins the three source URLs, retrieval date,
  sizes, SHA-256 values, gzip shape, attribution, and closed integration gates.
- [`suitability-audit.json`](suitability-audit.json) records the deterministic,
  identity-free aggregate source audit emitted from the pinned local bytes.

Local source bytes, when present, use this ignored layout:

```text
payload/
|-- v1-user-items/australian_users_items.json.gz
|-- v1-reviews/australian_user_reviews.json.gz
`-- v2-item-metadata/steam_games.json.gz
```

Keep those files compressed and immutable. The `payload/` directory is ignored
by Git and must never be force-added or redistributed from this repository.
The upstream dataset page requests citation, but no dataset license or
redistribution grant is recorded here; citation is not a license grant.

## Read-only commands

```powershell
make ucsd-steam-verify
make ucsd-steam-prepare
make ucsd-steam-audit
make ucsd-steam-audit-check
```

The dedicated Compose service mounts `data/` and `ml/` read-only, disables
networking, and uses a read-only root filesystem. The workflow has no download
path, writes no processed data, fits no model, promotes no artifact, and does
not mutate PostgreSQL. Preparation parses only byte-verified, bounded records
with `ast.literal_eval`; it never uses `eval`.

The exact committed-report check is:

```powershell
docker compose --profile source-audit run --build --rm --no-deps ucsd-source-audit python -m gamelens_recommender.ucsd_steam audit --root /workspace --check-report data/external/ucsd-steam/suitability-audit.json --format summary
```

## Verified aggregate facts

The committed audit was produced from the three pinned local gzip files. It
records 88,310 v1 user/item records with 5,153,209 nested item rows; 25,799 v1
review records with 59,305 review rows; and 32,135 v2 metadata records.

Under the project-defined preparation policy, unambiguous v2 metadata aligns
47,492 candidate pairs across 23,127 source profiles and 2,869 source items.
The deterministic support filter retains 9,792 profiles, 33,049 edges, and
1,516 items, with 6,481 item pairs having support of at least two. These are
source-structure diagnostics only.

`ready_for_functional_build`, `approved_training_eligibility`, and
`integration_ready` remain false. License and redistribution authority,
provenance approval for ingestion, Stage 5 label authority, GameLens catalog
mapping, fixture activation, and live consent/lifecycle evidence remain
blocking gates. No UCSD row is mapped into the GameLens catalog, training path,
artifact, API, or serving path.
