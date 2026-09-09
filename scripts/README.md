# Project scripts

This directory remains reserved; there is no runtime script here. Short commands
live in the root [Makefile](../Makefile), API command modules and
[web package scripts](../apps/web/package.json).

Phase 8 orchestration lives in [infra](../infra/README.md): the explicit
[combined gate](../infra/run-phase8.py), content/fixture/live-source/lifecycle
shell runners and shared [ownership-aware cleanup](../infra/e2e-ownership.sh).
Run `python infra/run-phase8.py` from the repository root with Python 3.12+,
POSIX `sh` (Git Bash on Windows), and Docker Desktop Linux containers; the
optional equivalent is `make test-phase8`. Individual workflows and their exact
Make equivalents are listed in the infra README. These commands explicitly
build disposable test artifacts and never run during ordinary test collection.
