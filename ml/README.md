# Machine-learning workspace

This directory is the future boundary for offline preprocessing, training,
evaluation, artifacts, tests, notebooks, and experiment reports.

Training will remain separate from online API requests. Generated artifacts
will be versioned by metadata but ignored by Git unless a small deterministic
fixture is explicitly needed for tests.

Stage 3 introduces the first TF-IDF content model. Collaborative filtering is
not planned until Stage 5.
