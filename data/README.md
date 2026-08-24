# Data

This directory separates project-owned inputs from external-source evidence and
local-only payloads. A file being present locally does not make it approved for
training, serving, redistribution, or quality claims.

## Layout

| Path | Git policy | Purpose |
| --- | --- | --- |
| `catalog/` | Tracked | Project-authored catalog used by development and tests. |
| `fixtures/` | Tracked after review | Small, deterministic, visibly synthetic test inputs owned by the project. |
| `external/<source>/` | Metadata tracked | Source manifest, source-specific policy, and aggregate-only audit evidence. |
| `external/<source>/payload/` | Ignored | Immutable local source bytes used only by an approved read-only verifier. |
| `private/` | Ignored | Local restricted material that must never be committed. |
| `generated/` | Ignored | Reproducible processed datasets and other generated data artifacts. |
| `raw/`, `processed/` | Ignored legacy paths | Kept ignored to prevent accidental commits from older workflows. |

The current catalog is [`catalog/games.json`](catalog/games.json): 30 fictional,
project-authored games with explicit taxonomy references. It has no external
source, cover binaries, or real-world performance claims and is distributed
under the repository license.

No external or real-user interaction dataset is committed or integrated. The
Stage 5 interaction fixture has not been added yet; its requirements are
recorded in [`fixtures/README.md`](fixtures/README.md).

## External-source policy

Before an external source can be ingested, its tracked metadata must record:

- exact source URL and attribution;
- rights-holder information where applicable;
- license and redistribution authority;
- retrieval date and original checksum;
- transformations and limitations;
- reviewed target-catalog mapping; and
- evidence for the applicable fixture, consent, retention, deletion, and
  activation gates.

Payload bytes remain ignored even when verification is allowed. Verifiers must
fail closed, perform no download, keep their source mounts read-only, and emit
only aggregate evidence without user identifiers. Generated datasets and model
artifacts must not be committed unless a later reviewed contract explicitly
allows a small project-authored fixture.

The UCSD Steam source is documented separately at
[`external/ucsd-steam/README.md`](external/ucsd-steam/README.md). Its source
identity and aggregate suitability were measured, but license/provenance
approval, label authority, GameLens catalog mapping, fixture activation, and
live-data lifecycle gates remain blocked. It is explicitly not integrated.
