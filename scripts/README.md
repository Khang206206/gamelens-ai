# Project scripts

Cross-project task scripts will live here when a Make target requires logic
that should be testable and portable.

Through Stage 5 Phase 5, short database, artifact, API, web, quality, and
integration-test operations remain in the root Makefile, package command
modules, or direct `docker compose` commands. No cross-project script is needed
yet. Add one only when cross-platform cleanup or orchestration can no longer
remain clear and independently testable at those existing boundaries.
