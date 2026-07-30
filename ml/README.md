# Machine-learning workspace

**Status:** Stage 3 engineering plan ready; implementation has not started.

The detailed
[Stage 3 content-recommendation engineering plan](../docs/stage-3-content-recommendation-mvp-plan.md)
defines the first implementation sequence and acceptance gate.

This directory is the planned boundary for deterministic catalog
preprocessing, the popularity baseline, TF-IDF feature construction, sparse
artifact generation, pure ranking logic, reproducibility metadata, ML tests,
and later offline evaluation. The API will own HTTP orchestration and online
inference; the browser will never train or rank.

Model building will remain an explicit offline operation, separate from API
requests and ordinary application startup. Generated artifacts will carry
model/version, configuration, data fingerprint, compatibility, and checksum
metadata and remain ignored by Git unless a small deterministic fixture is
explicitly required and documented for tests.

No ML package, dependency lock, build command, model artifact, recommendation
endpoint, or evaluation result exists yet. The current API still exposes only
the replaceable recommendation-service protocol and honest `not_configured`
status. Stage 3 will introduce request-scoped content recommendations;
feedback persistence begins in Stage 4, collaborative filtering in Stage 5,
and formal ranking evaluation in Stage 6.
