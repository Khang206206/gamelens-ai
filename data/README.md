# Data

This area will hold project-owned development data and documented imported
datasets.

Planned locations are:

- `seed/` for small deterministic seed records committed to the repository.
- `raw/` for immutable local source data that is normally ignored by Git.
- `processed/` for reproducible generated datasets that are ignored by Git.

These directories will be created when their first real artifact is added.
Every external dataset must record its source, license, retrieval date, and
transformation steps. Copyrighted cover images must not be committed.
