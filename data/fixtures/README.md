# Project-authored fixtures

This directory is reserved for small, deterministic, visibly synthetic data
owned by GameLens. External dataset excerpts, real user identifiers, copied
reviews, and generated snapshots do not belong here.

No activatable Stage 5 interaction fixture is committed yet. When implemented,
it must be versioned separately from normal development seeding, document its
generation and expected labels, and load only when `ENVIRONMENT=test` and the
explicit fixture-only flag are both enabled. Development and production must
reject a fixture artifact.

Fixture results demonstrate functional behavior and reproducibility only. They
are not evidence of recommendation quality or representative user behavior.
