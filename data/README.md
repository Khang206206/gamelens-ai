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
