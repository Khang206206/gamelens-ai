# Project scripts

Cross-project task scripts will live here when a Make target requires logic
that should be testable and portable.

Stage 1 keeps short database, API, quality, and integration-test operations in
the root Makefile or direct `docker compose` commands. A script should be added
only when cross-platform cleanup or orchestration can no longer remain clear
and testable there.
