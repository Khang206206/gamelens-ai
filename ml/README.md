# Machine-learning workspace

**Status:** Stage 3 has not started.

This directory is the future boundary for offline preprocessing, training,
evaluation, artifacts, tests, notebooks, and experiment reports.

Training will remain separate from online API requests. Generated artifacts
will be versioned by metadata but ignored by Git unless a small deterministic
fixture is explicitly needed for tests.

Stage 1 provides only the replaceable recommendation-service protocol and an
honest `not_configured` model-status implementation. No model artifact,
training pipeline, recommendation endpoint, or evaluation result exists yet.
Stage 3 introduces the first TF-IDF content model. Collaborative filtering is
not planned until Stage 5.
