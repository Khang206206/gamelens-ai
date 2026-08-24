# Project-authored catalog

[`games.json`](games.json) contains the deterministic GameLens development
catalog: 30 fictional games and their explicit taxonomy references. The records
were authored for this repository, contain no downloaded cover binaries, and
do not support claims about real-world popularity or recommendation quality.

The API seed command reads this file from `data/catalog/games.json`. Changes
must remain deterministic and must pass the seed safety, catalog API, artifact,
and integration tests that consume the catalog.
