# Project scripts

Cross-project task scripts will live here when a Make target requires logic
that should be testable and portable.

Stage 0 does not include empty shell wrappers. Current PostgreSQL tasks are
short enough to call directly from the root Makefile or with `docker compose`.
