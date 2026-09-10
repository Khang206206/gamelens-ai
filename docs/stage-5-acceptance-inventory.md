# Stage 5 acceptance inventory — slice 9A

**9A mapping and 9B/9C/9D focused runtime checks verified through 2026-09-10.** Surveyed clean parent `f4d9be7` after completed 8I (`d0e86f9`), plan consolidation (`47d132b`) and Phase 9 planning (`f4d9be7`). No repository `AGENTS.md` was found. 9A, synthetic extraction 9B, pure ML 9C and hybrid/baseline 9D are complete; 9E–9L and Phase 10 remain unstarted. See the [9B evidence](evidence/stage-5-phase-9b.json), [9C evidence](evidence/stage-5-phase-9c.json) and [9D evidence](evidence/stage-5-phase-9d.json) for current checks; the 9A mapping below remains historical unless explicitly updated. Schema head remains `0011_stage_5_lifecycle_guard`.

The [machine-readable inventory](evidence/stage-5-acceptance-inventory.json) is the canonical route/command contract. This readable view gives every unchanged Section 19 bullet a stable `S5-AC-01`–`S5-AC-47` ID. Route references compose the implementation path, exact assertion node or named review, fixture mode, command, expected result and evidence destination; a route is not a passing gate. The [9A record](evidence/stage-5-phase-9a.json) records only static verification.

## Status and evidence convention

- **EXISTING_NOT_RERUN:** Source assertion inspected; no Phase 9 execution evidence.
- **MISSING:** Required deliverable or current evidence absent; owning future slice must resolve.
- **BLOCKED:** Explicit authority/product/release decision required; synthetic checks do not remove block.
- **VERIFIED:** Only after recorded successful command/review on identified candidate; none of the runtime gates is verified in 9A.

The original 9A automated routes were **EXISTING_NOT_RERUN**. Routes R02–R05 are now **VERIFIED** by 9B, R11/R12/R16 by 9C and R17–R20/R27/R29 by 9D; other routes retain their recorded status. A row can additionally have MISSING evidence or a BLOCKED decision. No runtime result is VERIFIED in 9A. Final owners must disposition the whole criterion, including unasserted subclauses, rather than treating the listed representative assertions as exhaustive coverage.

Future evidence is `docs/evidence/stage-5-phase-9<slice>.json`, keyed by route and acceptance IDs; 9K cross-references the focused records. These are reserved destinations, not links to existing evidence. Keep raw output under ignored `tmp/phase9-<run-id>/`; retain only privacy-reviewed aggregate summaries and hashes. The historical [8H record](evidence/stage-5-phase-8h.json) is context only.

Each execution record must contain full clean parent SHA and candidate diff SHA256, owning slice/IDs, exact argv/cwd, fixture mode and selected nodes/projects/scenarios, expected and actual exits, observed test counts and skip reasons, duration, applicable runtime/lock/image identities, sanitized evidence path/SHA256, fixes/replay provenance and remaining blocks. No future test counts are filled in. Verify commit hash, docs/test ownership and clean Git after committing; do not insert the commit’s own future hash into its contents.

## Command and fixture modes

Commands are frozen to current entry points in the [Makefile](../Makefile), [runner](../infra/run-phase8.py), [web package](../apps/web/package.json) and parent plan Section 16. Placeholders must be substituted with inventory nodes and exact owned disposable project names. The JSON stores the expanded Python command for each node. Parametrized nodes run every case; a narrower case selection must be recorded.

### API

Working directory: repository root.

`docker compose run --build --rm --no-deps quality python -m pytest {node} -q -p no:cacheprovider`

Remove apps/api/ prefix from each exact Python node; execute each node or combine selected nodes.

Fixture: Unit/mocked or SQLite contracts only; not PostgreSQL proof.

### ML

Working directory: repository root.

`docker compose run --build --rm --no-deps quality python -m pytest /workspace/{node} -q -p no:cacheprovider`

Use ml/tests/file.py::test_name; pytest expands every parametrized case unless explicitly recorded.

Fixture: Small authored in-memory inputs and temporary JSON fixture artifacts; no live source.

### PG

Working directory: repository root.

`docker compose --project-name {owned-project} -f infra/docker-compose.test.yml run --build --rm test-api python -m pytest --run-integration -m integration {node} -q -p no:cacheprovider`

Remove apps/api/ prefix. Unique disposable test project only, test-db dependency and existing reset guards; always finally/trap down exact owned project and verify zero leftovers.

Fixture: Synthetic disposable PostgreSQL; tests may create registered lineage without invoking live builder. Never development DATABASE_URL.

### PG-LIVE

Working directory: repository root.

`Same exact PG command, selecting the listed live-build test node.`

Audit synthetic cohort, explicit extract/build/register/validate before serving; no JSON-fixture substitution.

Fixture: Real source_kind=live path on project-authored disposable PostgreSQL, not actual users.

### WEB

Working directory: apps/web.

`npm run test -- {file}; npm run typecheck`

Select the exact listed test file (all its literal it titles); use documented NEXT_PUBLIC_API_URL test endpoint and NEXT_PUBLIC_CONSENT_VERSION=stage-4-v1. Semicolon denotes separate commands; record each exit.

Fixture: Vitest mocked API; cannot prove browser or live API behavior.

### DRIFT

Working directory: apps/web.

`npm run api:types:check`

Point script at reachable disposable API per scripts/api-types.mjs; read-only. Record endpoint configuration without secrets.

Fixture: Running test API plus committed generated types.

### CONTENT

Working directory: repository root.

`sh infra/run-e2e-content.sh`

Use wrapper isolation/setup/project teardown; Chromium full, Firefox/WebKit *.smoke.spec.ts. Record selected files and mode skips.

Fixture: Disposable real content stack, synthetic catalog; inherited Stage 1–4 browser gates.

### FIXTURE

Working directory: repository root.

`sh infra/run-e2e-fixture.sh`

Wrapper owns two fixture semantic builds/probes, fallback variants and browser project selection; inspect wrapper, do not run all fallback cases blindly.

Fixture: Guarded JSON fixture artifact, test environment, immutable paths, required-content oracle/probe.

### LIFECYCLE

Working directory: repository root.

`sh infra/run-e2e-lifecycle.sh`

Use serialized phase/scenario runner; unique owned project and explicit private test controls; verify teardown for every scenario.

Fixture: Synthetic PostgreSQL registered live artifacts. Six scenarios: runner is authoritative.

### LIVE

Working directory: repository root.

`sh infra/run-e2e-live-source.sh`

Explicit audited synthetic live build/register/readiness; preserve semantic identity and event evidence.

Fixture: Disposable PostgreSQL-derived source_kind=live.

### CROSS

Working directory: repository root (web scripts: apps/web).

`python infra/run-phase8.py`

Existing combined infrastructure base only; full API/ML/PG/web, isolation and two live/lifecycle replays. 9K must additionally collect 9I diagnostics and 9J current release-input evidence; no test-phase9 target exists.

Fixture: Owned isolated modes; no implicit training in ordinary make test.

### MANUAL

Working directory: repository root.

`Named review M01–M07: inspect the listed paths and compare against its expected assertion; retain signed-off findings and source/candidate hashes.`

A named review is an evidence route, not a claim of execution or a substitute for required runtime checks.

Fixture: Source-only for 9A mapping; final artifact/image/log outputs for future reviews.

Use POSIX `sh`/Git Bash for wrappers. For PostgreSQL, finally/trap cleanup must run `docker compose --project-name {owned-project} -f infra/docker-compose.test.yml down --volumes --remove-orphans` only for the proven-owned disposable project, then inspect its labelled resources for zero leftovers. Never substitute the development database. For web scripts use the documented test API URL and consent version; PowerShell environment assignments differ from POSIX syntax. Current scan tool invocations belong to 9J and must be recorded from the actual installed tools.

9A needs no PostgreSQL, Docker, browser, production web build or live build. 9F, registered 9G scenarios, lifecycle 9H scenarios and 9K require the real extractor → builder → registry/lineage → readiness path over synthetic PostgreSQL. A JSON fixture build or a running API does not prove that path.

## Acceptance rows

### S5-AC-01

All Stage 1–4 migrations, contracts, privacy behavior, commands, artifacts, fast tests, integration tests, web tests, browser tests, and Docker workflows remain green.

Owner: **9K**. Routes: [R31](#r31), [I01](#i01), [I02](#i02), [I03](#i03), [I04](#i04), [I05](#i05), [I06](#i06), [I07](#i07), [I08](#i08), [I09](#i09), [I10](#i10).

Current disposition: Pending complete inherited regression run.

### S5-AC-02

`POST /api/v1/recommendations` remains cookie-agnostic, content-only, request-scoped, read-only, and contract-compatible.

Owner: **9G**. Routes: [R01](#r01).

Current disposition: Existing assertions; no Phase 9 run.

### S5-AC-03

Data source, purpose, authority, cutoff, catalog mapping, consent, retention, deletion, provenance, and limitations are documented.

Owner: **9B**. Routes: [M01](#m01), [R02](#r02), [R03](#r03).

Current disposition: BLOCKED actual user cohort authority; synthetic source documentation exists.

### S5-AC-04

Existing Stage 4 consent is not silently reused for aggregate training.

Owner: **9B**. Routes: [R04](#r04), [M01](#m01).

Current disposition: VERIFIED in the synthetic extraction/default-off scope of 9B; production authority and final release gates remain separate.

### S5-AC-05

Declining contribution does not create training eligibility; the documented request-only or saved-personalization fallback remains usable.

Owner: **9B**. Routes: [R04](#r04), [W02](#w02), [M01](#m01).

Current disposition: BLOCKED public contribution decline/product decision; request-only and separate default-off checks exist.

### S5-AC-06

The audit is read-only, aggregate-only, deterministic, bounded, and returns typed suitability reasons without fitting.

Owner: **9B**. Routes: [R03](#r03).

Current disposition: VERIFIED in the synthetic extraction/default-off scope of 9B; production authority and final release gates remain separate.

### S5-AC-07

Snapshot cutoff comes from PostgreSQL and one repeatable-read, read-only transaction.

Owner: **9B**. Routes: [R02](#r02).

Current disposition: VERIFIED in the synthetic extraction/default-off scope of 9B; production authority and final release gates remain separate.

### S5-AC-08

Temporal state, reaction precedence, rating threshold, saved positive game preference, and duplicate-source collapse match the frozen label policy.

Owner: **9B**. Routes: [R02](#r02), [R05](#r05).

Current disposition: VERIFIED in the synthetic extraction/default-off scope of 9B; production authority and final release gates remain separate.

### S5-AC-09

Unknown, viewed, played-only, wishlist-only, low-rating, disliked, and recommendation-event rows never become positive cosine edges.

Owner: **9B**. Routes: [R05](#r05).

Current disposition: VERIFIED in the synthetic extraction/default-off scope of 9B; production authority and final release gates remain separate.

### S5-AC-10

Recommendation events remain committed-generation audit records and are excluded from training by code, query, test, and documentation.

Owner: **9B**. Routes: [R05](#r05), [R24](#r24), [M01](#m01).

Current disposition: Code/query and test exclude events; documentation review pending.

### S5-AC-11

Internal IDs and credentials remain outside snapshots, artifacts, logs, events, responses, browser state, reports, and committed fixtures.

Owner: **9J**. Routes: [R13](#r13), [R22](#r22), [R24](#r24), [M02](#m02).

Current disposition: MISSING current full privacy review. Transient extractor mapping and protected DB lineage are the documented internal exception, never persisted/exported snapshots.

### S5-AC-12

Live user label rows and ephemeral cohort mappings are not retained as a reusable snapshot file after build success or failure.

Owner: **9F**. Routes: [R06](#r06), [R14](#r14), [M02](#m02).

Current disposition: Existing temporary cleanup/report checks; success/failure nonretention filesystem review pending.

### S5-AC-13

Any identity-bearing contributor lineage stays protected in PostgreSQL and exists only to enforce lifecycle invalidation.

Owner: **9F**. Routes: [R07](#r07), [M02](#m02).

Current disposition: Existing database lineage constraints; access/privacy review pending.

### S5-AC-14

Cleared, withdrawn, revoked, expired, or deleted contributions cannot enter a new build or continue through a serveable old artifact.

Owner: **9F**. Routes: [R02](#r02), [R08](#r08), [B03](#b03), [M01](#m01).

Current disposition: Synthetic lifecycle checks exist; actual cohort/product authority BLOCKED.

### S5-AC-15

Artifact/registry revision identity, bounded readiness/invalidation state, expected contributor count, consent version, validity horizon, and catalog fingerprint are checked before use without a per-request contributor scan; promotion also proves the source revision did not change during extraction/build.

Owner: **9F**. Routes: [R06](#r06), [R07](#r07), [R09](#r09).

Current disposition: Existing bounded readiness and promotion race assertions; rerun pending.

### S5-AC-16

The deterministic fixture is explicitly project-authored, isolated from development data, and never presented as a real-user or quality dataset.

Owner: **9B**. Routes: [R03](#r03), [R10](#r10), [M01](#m01).

Current disposition: Project-authored fixture documented; no real-user claim.

### S5-AC-17

A fixture artifact is serveable only in guarded disposable test/E2E mode and is rejected by ordinary development and production configuration.

Owner: **9E**. Routes: [R10](#r10), [B02](#b02).

Current disposition: Guarded fixture assertions and real config rejection probe exist.

### S5-AC-18

Structural and activation thresholds fail with `insufficient_data` rather than promoting a trivial live artifact.

Owner: **9F**. Routes: [R11](#r11), [R28](#r28).

Current disposition: Structural/activation assertions exist; final trivial-live promotion boundary audit pending.

### S5-AC-19

Fitting and serving use bounded sparse operations and never persist an unbounded dense user-item or item-item matrix.

Owner: **9C**. Routes: [R11](#r11), [R13](#r13), [M02](#m02).

Current disposition: Verified bounded pure fitting/scoring and temporary identity-free sparse artifact in 9C; small injected caps test exact/over boundaries before allocations/products and actual 100-neighbor/1000-visited-edge boundaries pass. Release-wide M02 review remains owned by 9J.

### S5-AC-20

Hand-calculated item support, pair support, raw cosine, quantization, self-edge removal, pruning, and tie-breaks match implementation exactly.

Owner: **9C**. Routes: [R12](#r12).

Current disposition: Verified exact CSR/support/cosine/decimal goldens, threshold before top-K, support then slug ties, nonfinite rejection and canonical/repeated fixture semantics in 9C.

### S5-AC-21

The artifact has exact model/schema/code identity, source kind, cutoff, catalog and interaction fingerprints, label policy, thresholds, build ID, revision, validity, aggregates, resource limits, and member checksums.

Owner: **9E**. Routes: [R13](#r13), [R14](#r14), [R06](#r06).

Current disposition: Metadata and lifecycle assertions exist; not newly verified.

### S5-AC-22

Artifact files contain no executable pickle, user matrix, user row, user ID, stable pseudonym, credential, or raw interaction payload.

Owner: **9E**. Routes: [R13](#r13), [M02](#m02).

Current disposition: Member/privacy assertions exist; full release scan pending.

### S5-AC-23

Missing, corrupt, incompatible, oversized, stale, expired, privacy-invalid, retired, or catalog-mismatched bundles never become collaborative-ready.

Owner: **9E**. Routes: [R09](#r09), [R10](#r10), [R13](#r13), [R14](#r14).

Current disposition: Loader/readiness rejection assertions exist; see all-reason matrix.

### S5-AC-24

Build targets are immutable; validation is read-only; promotion is crash-safe; rollback accepts only a still-valid registered artifact.

Owner: **9E**. Routes: [R13](#r13), [R14](#r14), [R15](#r15).

Current disposition: Filesystem safety and PostgreSQL rollback assertions exist; rerun by 9E/9F.

### S5-AC-25

The collaborative scorer is pure, bounded, identity-free, deterministic, and excludes all source and disliked games.

Owner: **9C**. Routes: [R16](#r16), [M02](#m02).

Current disposition: Verified pure bounded immutable scoring, source/dislike exclusion, deterministic order, no file I/O and identity-free public contracts in 9C. Release-wide M02 scan remains pending 9J.

### S5-AC-26

Unsupported users, sources, items, or pairs receive no fabricated collaborative score.

Owner: **9C**. Routes: [R16](#r16), [R20](#r20).

Current disposition: Verified empty, unsupported, zero-degree and mixed pure-scoring contexts and absent pairs without fabricated scores in 9C. Hybrid/API gates remain with 9D/9G.

### S5-AC-27

Candidate union allows a valid collaborative-only candidate before exclusions and top-K.

Owner: **9D**. Routes: [R17](#r17).

Current disposition: Verified R17 union/materialization before exclusion and top-K in 9D; loaded five-variant diagnostic also admits d-collaborative with zero content.

### S5-AC-28

A collaborative-only candidate receives explicitly materialized content/platform/popularity/base/affinity evidence without weakening the existing Stage 3 zero-content eligibility contract.

Owner: **9D**. Routes: [R17](#r17), [R19](#r19).

Current disposition: Verified R17/R19 exact zero-content base/platform/popularity/affinity and empty content evidence in 9D; native content/feedback universes remain unchanged.

### S5-AC-29

Hybrid weights are request-wide, versioned engineering defaults rather than learned or quality-optimized values.

Owner: **9D**. Routes: [R18](#r18), [M03](#m03).

Current disposition: Verified request-wide 80/10/10 and 90/0/10 defaults in R18 and the 9D M03 comparison review. No weights or product policy changed or learned.

### S5-AC-30

Under an active collaborative request, a candidate with no retained edge has unsupported/zero collaborative evidence and no candidate-level weight reallocation; this behavior is golden-tested and deferred to Stage 6 for evaluation.

Owner: **9D**. Routes: [R18](#r18).

Current disposition: Verified missing-edge and artifact-absent cold-content candidates retain 100000 collaborative weight, absent support/score and zero contribution; no per-candidate reallocation. Evaluation remains deferred to Stage 6.

### S5-AC-31

A reproducible fixture comparison records baseline candidates, components, and ranks while making no recommendation-quality claim.

Owner: **9D**. Routes: [R27](#r27), [M03](#m03).

Current disposition: Verified complete popularity/content/feedback/collaborative/hybrid diagnostic for eight small synthetic scenarios, hand-derived arithmetic, repeated canonical semantics and ordered output; see 9D evidence and table.

### S5-AC-32

Base, platform, popularity, feedback affinity, collaborative, played, and final values remain independently observable and reconstructible.

Owner: **9D**. Routes: [R17](#r17), [R18](#r18), [R19](#r19), [R22](#r22).

Current disposition: Verified full ML component observability and independent decimal reconstruction in 9D. Response/event cross-layer R22 remains pending 9G.

### S5-AC-33

Each named signal is weighted once; component contributions sum exactly in fixed-point units.

Owner: **9D**. Routes: [R18](#r18), [R22](#r22).

Current disposition: Verified one weighted contribution per named signal, source collapse and one post-blend played factor with exact fixed-point arithmetic in 9D. Response/event R22 remains pending 9G.

### S5-AC-34

Played adjustment occurs once after the pre-played hybrid score, dislikes remain hard exclusions, and wishlist remains neutral.

Owner: **9D**. Routes: [R17](#r17), [R18](#r18), [R29](#r29).

Current disposition: Verified hard exclusions, played after blending and full-result wishlist neutrality under both active hybrid weight configurations in 9D.

### S5-AC-35

Every collaborative-unavailable or unsupported path matches Stage 4 scores, order, response reason, and evidence exactly.

Owner: **9D**. Routes: [R20](#r20), [R21](#r21), [R22](#r22), [R23](#r23), [B02](#b02), [B03](#b03).

Current disposition: Verified all 15 ML fallback reasons preserve Stage 4 object/results/order/score/reason/evidence with truthful mode in R20. Producer/API/browser R21–R23/B02/B03 remain pending their owners; no cross-layer pass implied.

### S5-AC-36

Content readiness survives optional collaborative failure, while model status and personalized output expose truthful mode and bounded reason.

Owner: **9G**. Routes: [R21](#r21), [R09](#r09), [B02](#b02), [R32](#r32).

Current disposition: Existing optional fallback plus required-content failure probe; no blanket browser equivalence claim.

### S5-AC-37

The saved response, `stage-5-v1` event, and generated browser type share the same model/data/policy identity and component units.

Owner: **9G**. Routes: [R22](#r22), [R23](#r23), [R24](#r24), [R30](#r30), [W03](#w03).

Current disposition: Generated backward-compatibility assertion exists; ownership review and current live OpenAPI drift are pending.

### S5-AC-38

Every commit-acknowledged personalized HTTP 200 has exactly one matching bounded event; known pre-commit failures have none; ambiguous commit acknowledgement is not returned as success.

Owner: **9G**. Routes: [R23](#r23), [R24](#r24), [B02](#b02), [B03](#b03).

Current disposition: Unit commit failure and real event probes exist; registered transaction rerun pending.

### S5-AC-39

Event payloads contain no prose, credentials, identities, unbounded source lists, or state dump, and never become training labels.

Owner: **9G**. Routes: [R24](#r24), [R05](#r05), [M02](#m02).

Current disposition: Existing bounded schemas and label exclusion; current privacy review pending.

### S5-AC-40

Browser code preserves server order and performs no ranking math.

Owner: **9H**. Routes: [W01](#w01), [B01](#b01), [M04](#m04).

Current disposition: Server order assertion exists; no-ranking-math source review pending.

### S5-AC-41

Collaborative explanation appears only for a positive applied contribution and makes no “users like you” or quality claim.

Owner: **9H**. Routes: [R19](#r19), [W01](#w01), [B01](#b01).

Current disposition: Positive applied evidence and cautious-copy assertions exist.

### S5-AC-42

Consent, withdrawal, fallback, loading, empty, failure, keyboard, focus, announcement, accessibility, and responsive states pass their gates.

Owner: **9H**. Routes: [W01](#w01), [W02](#w02), [B01](#b01), [B02](#b02), [B03](#b03), [B04](#b04), [M01](#m01).

Current disposition: BLOCKED public contribution UI/routes; saved-personalization and private lifecycle scenarios exist, not substitutes.

### S5-AC-43

Commands have direct equivalents, immutable paths, stable exit behavior, read-only defaults where appropriate, and guarded destructive confirmation.

Owner: **9E**. Routes: [R15](#r15), [R25](#r25), [M05](#m05).

Current disposition: Existing command guards; parser/exit/direct-equivalent review pending.

### S5-AC-44

Ordinary startup, request handling, migration, seed, tests, and teardown do not train, promote, retire, or delete artifacts or user data.

Owner: **9K**. Routes: [R25](#r25), [R26](#r26), [B02](#b02), [B03](#b03), [M05](#m05).

Current disposition: Explicit synthetic setup may build; ordinary-operation snapshots/ownership checks exist; full replay pending.

### S5-AC-45

Dependency locks, licenses, security checks, Compose validation, non-root execution, OpenAPI drift, privacy scan, and final release review pass.

Owner: **9J**. Routes: [R26](#r26), [R30](#r30), [W03](#w03), [M02](#m02), [M06](#m06).

Current disposition: MISSING current lock/license/security/runtime and release review; 8H is historical only.

### S5-AC-46

Documentation distinguishes current Stage 4 behavior, implemented Stage 5 evidence, provisional policy defaults, and deferred Stage 6 evaluation.

Owner: **9L**. Routes: [M01](#m01), [M03](#m03), [M07](#m07).

Current disposition: MISSING final Phase 9 docs reconciliation; Stage 5 and Stage 6 handoff pending.

### S5-AC-47

No Precision/Recall/NDCG or other formal quality result, superiority claim, real-user claim, invented count, timing, or artifact size appears without the appropriate later evidence.

Owner: **9L**. Routes: [M03](#m03), [M07](#m07).

Current disposition: No quality/count claims authorized; final evidence/prose review pending.

## Assertion routes

Python links resolve to files; append the literal `::test_name` shown to select the exact node. The canonical JSON includes source line and full command. Different modes in one route require separate invocations. Refer to the route’s expected assertion, not just its function name.

### R01

Owner: **9G**; mode: **API**; status: **EXISTING_NOT_RERUN**.

Implementation: [apps/api/app/api/v1/routes/recommendations.py](../apps/api/app/api/v1/routes/recommendations.py).

- [apps/api/tests/unit/test_personalized_recommendations.py](../apps/api/tests/unit/test_personalized_recommendations.py) `::test_stateless_recommendation_ignores_valid_cookie_and_never_writes`
- [apps/api/tests/unit/test_recommendations_api.py](../apps/api/tests/unit/test_recommendations_api.py) `::test_ready_status_and_recommendation_contract`

Expected: Valid cookie is ignored; no persistence writes; Stage 3 response contract remains intact.

Evidence: future `docs/evidence/stage-5-phase-9g.json`, route `R01`.

### R02

Owner: **9B**; mode: **PG**; status: **VERIFIED**.

Implementation: [apps/api/app/repositories/collaborative_snapshot.py](../apps/api/app/repositories/collaborative_snapshot.py).

- [apps/api/tests/integration/test_stage_5_collaborative_snapshot.py](../apps/api/tests/integration/test_stage_5_collaborative_snapshot.py) `::test_extractor_applies_consent_temporal_and_label_precedence`
- [apps/api/tests/integration/test_stage_5_collaborative_snapshot.py](../apps/api/tests/integration/test_stage_5_collaborative_snapshot.py) `::test_repeatable_read_snapshot_and_revision_race_are_detected`
- [apps/api/tests/integration/test_stage_5_collaborative_snapshot.py](../apps/api/tests/integration/test_stage_5_collaborative_snapshot.py) `::test_mutation_after_snapshot_setup_before_extraction_is_a_revision_race`

Expected: Exact eligible slugs and exclusion counts; database cutoff/read-only repeatable-read snapshot; concurrent mutations detected. Exact cutoff, authority and label boundaries are verified in 9B.

Evidence: `docs/evidence/stage-5-phase-9b.json`, route `R02`.

9B verification: [recorded commands and results](evidence/stage-5-phase-9b.json). The canonical route data includes the new exact-boundary, read-only, resource-limit, aggregate/privacy and source-collapse assertions.

### R03

Owner: **9B**; mode: **API+ML+PG**; status: **VERIFIED**.

Implementation: [apps/api/app/commands/collaborative_snapshot.py](../apps/api/app/commands/collaborative_snapshot.py).

- [apps/api/tests/unit/test_collaborative_snapshot_command.py](../apps/api/tests/unit/test_collaborative_snapshot_command.py) `::test_default_live_audit_is_blocked_without_database_access`
- [apps/api/tests/unit/test_collaborative_snapshot_command.py](../apps/api/tests/unit/test_collaborative_snapshot_command.py) `::test_fixture_audit_uses_exact_catalog_and_emits_no_row_snapshot`
- [ml/tests/test_interaction_snapshot.py](../ml/tests/test_interaction_snapshot.py) `::test_project_authored_fixture_is_deterministic_and_aggregate_only`
- [ml/tests/test_interaction_snapshot.py](../ml/tests/test_interaction_snapshot.py) `::test_empty_snapshot_returns_typed_insufficiency_reasons`
- [apps/api/tests/unit/test_collaborative_snapshot_repository.py](../apps/api/tests/unit/test_collaborative_snapshot_repository.py) `::test_source_queries_join_eligibility_without_per_user_bind_expansion`

Expected: Default-off audit never accesses DB; exact aggregate fixture report; typed insufficiency and bounded eligibility query without per-user bind expansion.

Evidence: `docs/evidence/stage-5-phase-9b.json`, route `R03`.

9B verification: [recorded commands and results](evidence/stage-5-phase-9b.json). The canonical route data includes the new exact-boundary, read-only, resource-limit, aggregate/privacy and source-collapse assertions.

### R04

Owner: **9B**; mode: **API+PG**; status: **VERIFIED**.

Implementation: [apps/api/app/core/config.py](../apps/api/app/core/config.py).

- [apps/api/tests/unit/test_config.py](../apps/api/tests/unit/test_config.py) `::test_collaborative_live_data_is_default_off_and_requires_contribution_version`
- [apps/api/tests/integration/test_stage_5_disposable_lifecycle_fixture.py](../apps/api/tests/integration/test_stage_5_disposable_lifecycle_fixture.py) `::test_public_consent_does_not_grant_contribution_and_private_controls_are_repeatable`

Expected: Public saved-personalization consent does not grant contribution; private synthetic controls remain separate.

Evidence: `docs/evidence/stage-5-phase-9b.json`, route `R04`.

9B verification: [recorded commands and results](evidence/stage-5-phase-9b.json). The canonical route data includes the new exact-boundary, read-only, resource-limit, aggregate/privacy and source-collapse assertions.

### R05

Owner: **9B**; mode: **PG+ML**; status: **VERIFIED**.

Implementation: [apps/api/app/repositories/collaborative_snapshot.py](../apps/api/app/repositories/collaborative_snapshot.py).

- [apps/api/tests/integration/test_stage_5_collaborative_snapshot.py](../apps/api/tests/integration/test_stage_5_collaborative_snapshot.py) `::test_revision_tracks_source_tables_but_not_recommendation_events`
- [apps/api/tests/integration/test_stage_5_collaborative_snapshot.py](../apps/api/tests/integration/test_stage_5_collaborative_snapshot.py) `::test_extractor_applies_consent_temporal_and_label_precedence`

Expected: Events neither advance label revision nor enter extracted positives; low rating, views, played, wishlist, dislike and temporal exclusions have explicit assertions.

Evidence: `docs/evidence/stage-5-phase-9b.json`, route `R05`.

9B verification: [recorded commands and results](evidence/stage-5-phase-9b.json). The canonical route data includes the new exact-boundary, read-only, resource-limit, aggregate/privacy and source-collapse assertions.

### R06

Owner: **9F**; mode: **PG-LIVE**; status: **EXISTING_NOT_RERUN**.

Implementation: [apps/api/app/services/collaborative_build.py](../apps/api/app/services/collaborative_build.py).

- [apps/api/tests/integration/test_stage_5_live_build_promotion.py](../apps/api/tests/integration/test_stage_5_live_build_promotion.py) `::test_live_build_registers_retained_lineage_and_preserves_valid_rollback_candidates`
- [apps/api/tests/integration/test_stage_5_live_build_promotion.py](../apps/api/tests/integration/test_stage_5_live_build_promotion.py) `::test_registry_promotion_revision_race_rolls_back_build_and_lineage`
- [apps/api/tests/integration/test_stage_5_live_build_promotion.py](../apps/api/tests/integration/test_stage_5_live_build_promotion.py) `::test_orphan_bundle_recovery_registers_exact_lineage_and_is_idempotent`

Expected: Only retained contributors registered; identity-free report; revision race rolls back registry/lineage; orphan recovery preserves bundle bytes.

Evidence: future `docs/evidence/stage-5-phase-9f.json`, route `R06`.

### R07

Owner: **9F**; mode: **PG**; status: **EXISTING_NOT_RERUN**.

Implementation: [apps/api/app/repositories/collaborative_registry.py](../apps/api/app/repositories/collaborative_registry.py).

- [apps/api/tests/integration/test_stage_5_artifact_registry.py](../apps/api/tests/integration/test_stage_5_artifact_registry.py) `::test_registry_count_is_constant_time_and_user_delete_invalidates_before_serving`
- [apps/api/tests/integration/test_stage_5_artifact_registry.py](../apps/api/tests/integration/test_stage_5_artifact_registry.py) `::test_registry_constraints_reject_invalid_or_inconsistent_lineage`
- [apps/api/tests/integration/test_stage_5_authority_invalidation.py](../apps/api/tests/integration/test_stage_5_authority_invalidation.py) `::test_contributor_lineage_cannot_be_reassigned`

Expected: Bounded registry read; delete invalidates before serving; inconsistent lineage/reassignment rejected; no per-request contributor scan.

Evidence: future `docs/evidence/stage-5-phase-9f.json`, route `R07`.

### R08

Owner: **9F**; mode: **PG**; status: **EXISTING_NOT_RERUN**.

Implementation: [apps/api/app/services/collaborative_lifecycle.py](../apps/api/app/services/collaborative_lifecycle.py).

- [apps/api/tests/integration/test_stage_5_authority_invalidation.py](../apps/api/tests/integration/test_stage_5_authority_invalidation.py) `::test_consent_withdrawal_is_atomic_and_reconsent_does_not_revive_build`
- [apps/api/tests/integration/test_stage_5_authority_invalidation.py](../apps/api/tests/integration/test_stage_5_authority_invalidation.py) `::test_contribution_authority_changes_invalidate_registered_build`
- [apps/api/tests/integration/test_stage_5_authority_invalidation.py](../apps/api/tests/integration/test_stage_5_authority_invalidation.py) `::test_personalization_authority_changes_invalidate_registered_build`
- [apps/api/tests/integration/test_stage_5_authority_invalidation.py](../apps/api/tests/integration/test_stage_5_authority_invalidation.py) `::test_retention_cascade_invalidates_and_decrements_expired_contributor`
- [apps/api/tests/integration/test_stage_5_label_invalidation.py](../apps/api/tests/integration/test_stage_5_label_invalidation.py) `::test_removing_or_overriding_an_included_positive_invalidates_on_commit`

Expected: Withdrawal, authority change, expiry and label removal invalidate on commit; re-consent never revives the old build.

Evidence: future `docs/evidence/stage-5-phase-9f.json`, route `R08`.

### R09

Owner: **9F**; mode: **API+PG**; status: **EXISTING_NOT_RERUN**.

Implementation: [apps/api/app/services/recommendation/readiness.py](../apps/api/app/services/recommendation/readiness.py).

- [apps/api/tests/unit/test_collaborative_readiness.py](../apps/api/tests/unit/test_collaborative_readiness.py) `::test_every_live_lineage_mismatch_fails_closed`
- [apps/api/tests/unit/test_collaborative_readiness.py](../apps/api/tests/unit/test_collaborative_readiness.py) `::test_current_consent_mismatch_invalidates_live_use_without_changing_the_artifact`
- [apps/api/tests/unit/test_collaborative_readiness.py](../apps/api/tests/unit/test_collaborative_readiness.py) `::test_catalog_and_time_are_rechecked_at_the_request_boundary`
- [apps/api/tests/integration/test_stage_5_model_status.py](../apps/api/tests/integration/test_stage_5_model_status.py) `::test_content_and_collaborative_status_share_one_repeatable_read_snapshot`

Expected: Mismatch in revision, count, cutoff, fingerprint, validity or authority fails closed; one status transaction and request-time catalog/time checks.

Evidence: future `docs/evidence/stage-5-phase-9f.json`, route `R09`.

### R10

Owner: **9E**; mode: **API**; status: **EXISTING_NOT_RERUN**.

Implementation: [apps/api/app/core/config.py](../apps/api/app/core/config.py).

- [apps/api/tests/unit/test_config.py](../apps/api/tests/unit/test_config.py) `::test_collaborative_fixture_gate_is_test_only`
- [apps/api/tests/unit/test_config.py](../apps/api/tests/unit/test_config.py) `::test_collaborative_fixture_and_live_authority_are_mutually_exclusive`
- [apps/api/tests/unit/test_collaborative_readiness.py](../apps/api/tests/unit/test_collaborative_readiness.py) `::test_guarded_fixture_is_usable_but_never_presented_as_live_ready`

Expected: Fixture gate rejected outside test; live authority mutually exclusive; fixture readiness never claims live readiness.

Evidence: future `docs/evidence/stage-5-phase-9e.json`, route `R10`.

### R11

Owner: **9C**; mode: **ML**; status: **VERIFIED**.

Implementation: [ml/src/gamelens_recommender/collaborative_training.py](../ml/src/gamelens_recommender/collaborative_training.py).

- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_support_pruning_reaches_the_same_cascading_fixed_point`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_pair_contribution_cap_is_checked_before_sparse_multiplication`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_duplicate_raw_entries_are_bounded_before_profile_materialization`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_distinct_pair_cap_is_checked_before_sparse_multiplication`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_binary_validator_rejects_noncanonical_and_nonbinary_csr`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_empty_single_user_and_single_item_have_no_supported_matrix`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_invalid_profiles_fail_with_typed_input_error`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_duplicate_entries_collapse_to_binary_but_duplicate_contributors_remain`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_matrix_resource_boundaries_reject_before_array_allocation`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_distinct_pair_boundary_rejects_before_sparse_product`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_real_hundred_neighbor_boundary_prunes_stable_ties_without_dense_conversion`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_invalid_fit_configuration_rejects_before_sparse_product`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_total_neighbor_nonzero_boundary_rejects_before_output_array_materialization`

Expected: Support fixed point and resource caps checked before allocation/multiplication; noncanonical/nonbinary CSR rejected.

Evidence: [9C verification](evidence/stage-5-phase-9c.json), route `R11`; focused and full ML suites.

### R12

Owner: **9C**; mode: **ML**; status: **VERIFIED**.

Implementation: [ml/src/gamelens_recommender/collaborative_training.py](../ml/src/gamelens_recommender/collaborative_training.py).

- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_binary_matrix_is_int64_canonical_and_preserves_duplicate_profiles`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_hand_calculated_cosine_quantizes_half_up_to_707107`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_pair_support_one_is_missing_support_not_a_zero_similarity`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_top_k_uses_rank_key_then_serializes_true_index_sorted_csr`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_top_k_slug_tie_break_selects_lexicographically_first_neighbor`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_project_fixture_matches_all_support_and_sparse_neighbor_goldens`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_reordered_equivalent_input_produces_identical_semantic_arrays`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_quantizer_rejects_nonfinite_out_of_range_and_nonnumeric_values`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_quantizer_boundaries_have_independent_decimal_goldens`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_pair_threshold_and_diagonal_removal_precede_top_neighbor_pruning`
- [ml/tests/test_collaborative_training.py](../ml/tests/test_collaborative_training.py) `::test_equal_cosine_uses_pair_support_before_slug_for_top_neighbor`
- [ml/tests/test_collaborative_pipeline.py](../ml/tests/test_collaborative_pipeline.py) `::test_fixture_pipeline_is_deterministic_identity_free_and_immutable`

Expected: Exact support/cosine 707107, missing low-support edges, self-edge-free fixture goldens, sorted CSR and stable pruning/ties; input permutations yield equal arrays.

Evidence: [9C verification](evidence/stage-5-phase-9c.json), route `R12`; focused and full ML suites.

### R13

Owner: **9E**; mode: **ML**; status: **EXISTING_NOT_RERUN**.

Implementation: [ml/src/gamelens_recommender/collaborative_artifacts.py](../ml/src/gamelens_recommender/collaborative_artifacts.py).

- [ml/tests/test_collaborative_artifacts.py](../ml/tests/test_collaborative_artifacts.py) `::test_fixture_round_trip_is_deterministic_private_and_deeply_immutable`
- [ml/tests/test_collaborative_artifacts.py](../ml/tests/test_collaborative_artifacts.py) `::test_loader_rejects_manifest_traversal_and_checksum_corruption`
- [ml/tests/test_collaborative_artifacts.py](../ml/tests/test_collaborative_artifacts.py) `::test_loader_rejects_unsafe_or_malformed_npy_members`
- [ml/tests/test_collaborative_artifacts.py](../ml/tests/test_collaborative_artifacts.py) `::test_loader_rejects_checksum_valid_semantic_corruption`
- [ml/tests/test_collaborative_artifacts.py](../ml/tests/test_collaborative_artifacts.py) `::test_loader_rejects_missing_and_extra_directory_members`

Expected: Exact members and semantic identity, equal builds, immutable arrays, identity-marker exclusion; malformed checksums, formats, dtype/shape and semantic corruption rejected.

Evidence: future `docs/evidence/stage-5-phase-9e.json`, route `R13`.

### R14

Owner: **9E**; mode: **ML**; status: **EXISTING_NOT_RERUN**.

Implementation: [ml/src/gamelens_recommender/collaborative_artifacts.py](../ml/src/gamelens_recommender/collaborative_artifacts.py).

- [ml/tests/test_collaborative_artifacts.py](../ml/tests/test_collaborative_artifacts.py) `::test_loader_rejects_member_and_root_symlinks`
- [ml/tests/test_collaborative_artifacts.py](../ml/tests/test_collaborative_artifacts.py) `::test_live_lifecycle_expectations_and_expiry_are_fail_closed`
- [ml/tests/test_collaborative_artifacts.py](../ml/tests/test_collaborative_artifacts.py) `::test_atomic_promotion_does_not_replace_target_created_after_precheck`
- [ml/tests/test_collaborative_artifacts.py](../ml/tests/test_collaborative_artifacts.py) `::test_production_loader_failure_cleans_temporary_bundle`
- [ml/tests/test_collaborative_artifacts.py](../ml/tests/test_collaborative_artifacts.py) `::test_promotion_never_overwrites_target_or_promotes_after_revision_race`

Expected: Unsafe paths and invalid lifecycle rejected; target remains immutable during competing promotion; temporary bundle/lock cleaned on loader failure.

Evidence: future `docs/evidence/stage-5-phase-9e.json`, route `R14`.

### R15

Owner: **9F**; mode: **PG-LIVE**; status: **EXISTING_NOT_RERUN**.

Implementation: [apps/api/app/commands/collaborative_artifact.py](../apps/api/app/commands/collaborative_artifact.py).

- [apps/api/tests/integration/test_stage_5_rollback_check.py](../apps/api/tests/integration/test_stage_5_rollback_check.py) `::test_rollback_refuses_unusable_candidate_without_mutating_state`
- [apps/api/tests/integration/test_stage_5_retirement_preview.py](../apps/api/tests/integration/test_stage_5_retirement_preview.py) `::test_postgresql_retirement_preview_is_exact_read_only_and_idempotent`
- [apps/api/tests/integration/test_stage_5_retirement_preview.py](../apps/api/tests/integration/test_stage_5_retirement_preview.py) `::test_confirmed_postgresql_cleanup_removes_only_exact_non_active_bundles`
- [apps/api/tests/integration/test_stage_5_retirement_preview.py](../apps/api/tests/integration/test_stage_5_retirement_preview.py) `::test_cleanup_rejects_registry_change_after_preview_without_removing_bundle`
- [apps/api/tests/integration/test_stage_5_retirement_preview.py](../apps/api/tests/integration/test_stage_5_retirement_preview.py) `::test_interrupted_postgresql_cleanup_recovers_from_durable_receipt`

Expected: Rollback and preview read-only; cleanup confirms exact non-active set and rejects changed registry; durable recovery receipt.

Evidence: future `docs/evidence/stage-5-phase-9f.json`, route `R15`.

### R16

Owner: **9C**; mode: **ML**; status: **VERIFIED**.

Implementation: [ml/src/gamelens_recommender/collaborative.py](../ml/src/gamelens_recommender/collaborative.py).

- [ml/tests/test_collaborative_scorer.py](../ml/tests/test_collaborative_scorer.py) `::test_multi_source_score_rounds_half_up_and_returns_complete_ordered_evidence`
- [ml/tests/test_collaborative_scorer.py](../ml/tests/test_collaborative_scorer.py) `::test_expected_sparse_states_return_most_specific_typed_reason`
- [ml/tests/test_collaborative_scorer.py](../ml/tests/test_collaborative_scorer.py) `::test_source_then_dislike_exclusions_are_disjoint_and_can_remove_every_candidate`
- [ml/tests/test_collaborative_scorer.py](../ml/tests/test_collaborative_scorer.py) `::test_equivalent_source_permutations_and_row_visit_order_keep_candidate_output_equal`
- [ml/tests/test_collaborative_scorer.py](../ml/tests/test_collaborative_scorer.py) `::test_scorer_accepts_exact_one_thousand_edge_boundary`
- [ml/tests/test_collaborative_scorer.py](../ml/tests/test_collaborative_scorer.py) `::test_scorer_rejects_one_over_query_source_limit_before_lookup`
- [ml/tests/test_collaborative_scorer.py](../ml/tests/test_collaborative_scorer.py) `::test_mixed_unsupported_and_zero_degree_sources_do_not_dilute_or_invent_scores`
- [ml/tests/test_collaborative_scorer.py](../ml/tests/test_collaborative_scorer.py) `::test_scorer_repeated_calls_are_pure_and_do_not_read_artifact_files`
- [ml/tests/test_collaborative_contracts.py](../ml/tests/test_collaborative_contracts.py) `::test_edge_contract_rejects_nonfinite_noninteger_and_out_of_range_scores`
- [ml/tests/test_collaborative_contracts.py](../ml/tests/test_collaborative_contracts.py) `::test_raw_source_state_accepts_exact_cap_and_rejects_one_more_before_deduplication`

Expected: Pure bounded scoring; exact edge mean and order; four typed no-support states; source/dislike exclusion; 1000-edge boundary and source cap.

Evidence: [9C verification](evidence/stage-5-phase-9c.json), route `R16`; focused and full ML suites.

### R17

Owner: **9D**; mode: **ML**; status: **VERIFIED**.

Implementation: [ml/src/gamelens_recommender/hybrid.py](../ml/src/gamelens_recommender/hybrid.py).

- [ml/tests/test_hybrid_candidate_union.py](../ml/tests/test_hybrid_candidate_union.py) `::test_candidate_union_materializes_exact_components_and_origins_before_top_k`
- [ml/tests/test_hybrid_candidate_union.py](../ml/tests/test_hybrid_candidate_union.py) `::test_candidate_union_applies_prepared_hard_exclusions_after_union`
- [ml/tests/test_hybrid_candidate_union.py](../ml/tests/test_hybrid_candidate_union.py) `::test_candidate_union_chunks_exact_materialization_at_the_phase3_row_bound`

Expected: Union before exclusions/top-K; collaborative-only zero-content materialization preserves base/platform/popularity/affinity evidence and Stage 3 row bound.

Evidence: [9D verification](evidence/stage-5-phase-9d.json), route `R17`; focused and full ML suites. Later-layer evidence remains separate.

### R18

Owner: **9D**; mode: **ML**; status: **VERIFIED**.

Implementation: [ml/src/gamelens_recommender/hybrid.py](../ml/src/gamelens_recommender/hybrid.py).

- [ml/tests/test_hybrid_scoring.py](../ml/tests/test_hybrid_scoring.py) `::test_hybrid_scoring_applies_request_wide_weights_and_played_after_blending`
- [ml/tests/test_hybrid_scoring.py](../ml/tests/test_hybrid_scoring.py) `::test_hybrid_scoring_without_affinity_uses_90_0_10_for_every_candidate`
- [ml/tests/test_hybrid_scoring.py](../ml/tests/test_hybrid_scoring.py) `::test_hybrid_scoring_orders_after_played_adjustment_then_applies_top_k`
- [ml/tests/test_hybrid_scoring.py](../ml/tests/test_hybrid_scoring.py) `::test_full_hybrid_tie_break_ends_with_stable_slug`
- [ml/tests/test_hybrid_scoring.py](../ml/tests/test_hybrid_scoring.py) `::test_hybrid_candidate_ranking_is_frozen_reconstructible_and_internal`
- [ml/tests/test_phase4_handoff.py](../ml/tests/test_phase4_handoff.py) `::test_five_variant_components_reconstruct_without_invented_support`
- [ml/tests/test_phase4_handoff.py](../ml/tests/test_phase4_handoff.py) `::test_loaded_hybrid_top_k_is_prefix_after_union_exclusions_and_played`

Expected: 80/10/10 or 90/0/10 request weights; missing-edge candidate retains 10% weight and zero contribution; exact unit sum, one played factor, top-K after scoring, stable ties.

Evidence: [9D verification](evidence/stage-5-phase-9d.json), route `R18`; focused and full ML suites. Later-layer evidence remains separate.

### R19

Owner: **9D**; mode: **ML**; status: **VERIFIED**.

Implementation: [ml/src/gamelens_recommender/hybrid.py](../ml/src/gamelens_recommender/hybrid.py).

- [ml/tests/test_hybrid_materialization.py](../ml/tests/test_hybrid_materialization.py) `::test_hybrid_materialization_returns_exact_ranked_components_and_evidence`
- [ml/tests/test_hybrid_materialization.py](../ml/tests/test_hybrid_materialization.py) `::test_hybrid_explanations_are_deterministic_cautious_and_evidence_backed`
- [ml/tests/test_hybrid_materialization.py](../ml/tests/test_hybrid_materialization.py) `::test_zero_applied_collaborative_contribution_has_no_collaborative_prose`

Expected: All components retained; deterministic cautious prose only with positive applied contribution.

Evidence: [9D verification](evidence/stage-5-phase-9d.json), route `R19`; focused and full ML suites. Later-layer evidence remains separate.

### R20

Owner: **9D**; mode: **ML**; status: **VERIFIED**.

Implementation: [ml/src/gamelens_recommender/hybrid.py](../ml/src/gamelens_recommender/hybrid.py).

- [ml/tests/test_hybrid_ranker.py](../ml/tests/test_hybrid_ranker.py) `::test_every_unavailable_reason_returns_the_exact_stage4_payload`
- [ml/tests/test_hybrid_ranker.py](../ml/tests/test_hybrid_ranker.py) `::test_every_ready_no_support_reason_returns_the_exact_stage4_payload`
- [ml/tests/test_hybrid_ranker.py](../ml/tests/test_hybrid_ranker.py) `::test_ready_context_or_exclusion_mismatch_fails_without_silent_fallback`
- [ml/tests/test_hybrid_ranker.py](../ml/tests/test_hybrid_ranker.py) `::test_invalid_context_or_feedback_is_an_error_even_when_component_cannot_score`

Expected: All 11 unavailable + 4 unsupported reasons preserve the exact Stage 4 object, full equality, reason and fallback mode with played/disliked/wishlisted state; invalid context/feedback remains the Stage 4 error, never a successful fallback.

Evidence: [9D verification](evidence/stage-5-phase-9d.json), route `R20`; focused and full ML suites. Later-layer evidence remains separate.

### R21

Owner: **9G**; mode: **API**; status: **EXISTING_NOT_RERUN**.

Implementation: [apps/api/app/services/recommendation/hybrid.py](../apps/api/app/services/recommendation/hybrid.py).

- [apps/api/tests/unit/test_hybrid_orchestration.py](../apps/api/tests/unit/test_hybrid_orchestration.py) `::test_every_lifecycle_unavailability_returns_exact_stage4_payload`
- [apps/api/tests/unit/test_hybrid_orchestration.py](../apps/api/tests/unit/test_hybrid_orchestration.py) `::test_every_no_support_reason_returns_exact_stage4_payload`
- [apps/api/tests/unit/test_hybrid_orchestration.py](../apps/api/tests/unit/test_hybrid_orchestration.py) `::test_scorer_failure_isolated_as_artifact_incompatible_stage4_fallback`
- [apps/api/tests/unit/test_hybrid_orchestration.py](../apps/api/tests/unit/test_hybrid_orchestration.py) `::test_content_catalog_failure_keeps_existing_exception_semantics`

Expected: API orchestration preserves exact Stage 4 data for all 15 reasons; scorer failure isolated; required-content failure remains an error.

Evidence: future `docs/evidence/stage-5-phase-9g.json`, route `R21`.

### R22

Owner: **9G**; mode: **API**; status: **EXISTING_NOT_RERUN**.

Implementation: [apps/api/app/services/recommendation/projection.py](../apps/api/app/services/recommendation/projection.py).

- [apps/api/tests/unit/test_stage_5_decision_projection.py](../apps/api/tests/unit/test_stage_5_decision_projection.py) `::test_real_hybrid_decision_projects_once_into_equal_deterministic_contracts`
- [apps/api/tests/unit/test_stage_5_decision_projection.py](../apps/api/tests/unit/test_stage_5_decision_projection.py) `::test_every_fallback_projects_the_exact_stage_4_records_without_identity_leakage`
- [apps/api/tests/unit/test_stage_5_decision_projection.py](../apps/api/tests/unit/test_stage_5_decision_projection.py) `::test_projection_enforces_top_k_and_compact_json_bounds`

Expected: Shared projection gives equal response/event units and identities; bounded top-K/JSON, exact fallback records.

Evidence: future `docs/evidence/stage-5-phase-9g.json`, route `R22`.

### R23

Owner: **9G**; mode: **API**; status: **EXISTING_NOT_RERUN**.

Implementation: [apps/api/app/api/v1/routes/personalized_recommendations.py](../apps/api/app/api/v1/routes/personalized_recommendations.py).

- [apps/api/tests/unit/test_personalized_recommendations.py](../apps/api/tests/unit/test_personalized_recommendations.py) `::test_every_fallback_activates_the_exact_stage_4_decision_and_stage_5_event`
- [apps/api/tests/unit/test_personalized_recommendations.py](../apps/api/tests/unit/test_personalized_recommendations.py) `::test_ready_hybrid_decision_activates_one_correlated_stage_5_response_and_event`
- [apps/api/tests/unit/test_personalized_recommendations.py](../apps/api/tests/unit/test_personalized_recommendations.py) `::test_event_flush_failure_is_known_precommit_failure_with_zero_event`
- [apps/api/tests/unit/test_personalized_recommendations.py](../apps/api/tests/unit/test_personalized_recommendations.py) `::test_event_commit_failure_reports_ambiguous_generation_without_200`
- [apps/api/tests/unit/test_personalized_recommendations.py](../apps/api/tests/unit/test_personalized_recommendations.py) `::test_stage_5_projection_failure_commits_no_partial_event`

Expected: HTTP fallback reason/order/score units and event agree for all 15 reasons; one correlated successful event; zero precommit event; ambiguous commit never returns 200.

Evidence: future `docs/evidence/stage-5-phase-9g.json`, route `R23`.

### R24

Owner: **9G**; mode: **API+PG**; status: **EXISTING_NOT_RERUN**.

Implementation: [apps/api/app/repositories/recommendation_events.py](../apps/api/app/repositories/recommendation_events.py).

- [apps/api/tests/unit/test_stage_5_recommendation_event_contract.py](../apps/api/tests/unit/test_stage_5_recommendation_event_contract.py) `::test_stage_5_event_contract_forbids_raw_or_unbounded_payloads`
- [apps/api/tests/unit/test_stage_5_response_contract.py](../apps/api/tests/unit/test_stage_5_response_contract.py) `::test_stage_5_response_forbids_identity_leakage_and_unbounded_shapes`
- [apps/api/tests/integration/test_stage_5_recommendation_events.py](../apps/api/tests/integration/test_stage_5_recommendation_events.py) `::test_stage_5_repository_persists_hybrid_and_fallback_without_advancing_labels`
- [apps/api/tests/integration/test_stage_5_recommendation_events.py](../apps/api/tests/integration/test_stage_5_recommendation_events.py) `::test_stage_5_events_follow_existing_retention_and_user_cascade`
- [apps/api/tests/integration/test_stage_5_recommendation_events.py](../apps/api/tests/integration/test_stage_5_recommendation_events.py) `::test_0010_populated_upgrade_and_downgrade_preserve_prior_event_rows`

Expected: Bounded identity-free response/event schemas; no label revision change; prior events survive populated migration; retention/delete cascade remains valid.

Evidence: future `docs/evidence/stage-5-phase-9g.json`, route `R24`.

### R25

Owner: **9F**; mode: **PG-LIVE+API**; status: **EXISTING_NOT_RERUN**.

Implementation: [apps/api/app/services/collaborative_build.py](../apps/api/app/services/collaborative_build.py).

- [apps/api/tests/integration/test_stage_5_lifecycle_handoff.py](../apps/api/tests/integration/test_stage_5_lifecycle_handoff.py) `::test_startup_seed_and_populated_migration_do_not_mutate_derived_state`
- [apps/api/tests/integration/test_stage_5_lifecycle_handoff.py](../apps/api/tests/integration/test_stage_5_lifecycle_handoff.py) `::test_operator_cli_lifecycle_handoff_on_disposable_postgresql`
- [apps/api/tests/unit/test_collaborative_build.py](../apps/api/tests/unit/test_collaborative_build.py) `::test_live_build_service_rechecks_default_off_gates_before_database_access`
- [apps/api/tests/unit/test_e2e_isolation.py](../apps/api/tests/unit/test_e2e_isolation.py) `::test_normal_startup_has_no_implicit_model_or_lifecycle_command`

Expected: Explicit operator lifecycle only; startup/seed/populated migration preserve artifact and registry state; default-off fails before DB access.

Evidence: future `docs/evidence/stage-5-phase-9f.json`, route `R25`.

### R26

Owner: **9J**; mode: **API**; status: **EXISTING_NOT_RERUN**.

Implementation: [infra/e2e-ownership.sh](../infra/e2e-ownership.sh).

- [apps/api/tests/unit/test_e2e_isolation.py](../apps/api/tests/unit/test_e2e_isolation.py) `::test_destructive_topology_has_no_host_mounts_socket_or_public_ports`
- [apps/api/tests/unit/test_e2e_isolation.py](../apps/api/tests/unit/test_e2e_isolation.py) `::test_every_runner_uses_shared_ownership_and_signal_cleanup`
- [apps/api/tests/unit/test_e2e_isolation.py](../apps/api/tests/unit/test_e2e_isolation.py) `::test_shared_teardown_preserves_status_and_checks_only_owned_resources`
- [apps/api/tests/unit/test_e2e_isolation.py](../apps/api/tests/unit/test_e2e_isolation.py) `::test_teardown_refuses_development_and_surfaces_removal_failure`

Expected: No host data/socket/public ports in destructive topology; teardown targets proven ownership, preserves failure code and refuses development resources.

Evidence: future `docs/evidence/stage-5-phase-9j.json`, route `R26`.

### R27

Owner: **9D**; mode: **ML**; status: **VERIFIED**.

Implementation: [ml/src/gamelens_recommender/hybrid.py](../ml/src/gamelens_recommender/hybrid.py).

- [ml/tests/test_hybrid_ranker.py](../ml/tests/test_hybrid_ranker.py) `::test_fixture_comparison_freezes_stage4_and_hybrid_candidate_diagnostics`
- [ml/tests/test_phase4_handoff.py](../ml/tests/test_phase4_handoff.py) `::test_phase4_fixture_trace_is_a_frozen_functional_diagnostic`
- [ml/tests/test_phase4_handoff.py](../ml/tests/test_phase4_handoff.py) `::test_five_variant_diagnostic_has_hand_derived_order_and_units`
- [ml/tests/test_phase4_handoff.py](../ml/tests/test_phase4_handoff.py) `::test_five_variant_components_reconstruct_without_invented_support`
- [ml/tests/test_phase4_handoff.py](../ml/tests/test_phase4_handoff.py) `::test_five_variant_diagnostic_repeats_equivalent_canonical_inputs`

Expected: Five native-policy variants across eight synthetic scenarios with independent literal/math goldens, candidate universes/exclusions/tie-breaks/top-K, exact components/support and no quality claims. Two canonical-input permutations produce equal semantic arrays, identities and ordered tables.

Evidence: [9D verification](evidence/stage-5-phase-9d.json), route `R27`; focused and full ML suites. Later-layer evidence remains separate.

### R28

Owner: **9F**; mode: **API+PG**; status: **EXISTING_NOT_RERUN**.

Implementation: [apps/api/app/services/recommendation/readiness.py](../apps/api/app/services/recommendation/readiness.py).

- [apps/api/tests/unit/test_collaborative_readiness.py](../apps/api/tests/unit/test_collaborative_readiness.py) `::test_artifact_below_any_activation_minimum_is_insufficient_data`
- [apps/api/tests/integration/test_stage_5_disposable_lifecycle_fixture.py](../apps/api/tests/integration/test_stage_5_disposable_lifecycle_fixture.py) `::test_disposable_cohort_crosses_support_gate_and_keeps_exclusions_out`

Expected: Each activation minimum fails as insufficient_data; synthetic cohort passes gates and excludes unsupported rows. Full trivial-live promotion boundary disposition remains for 9F.

Evidence: future `docs/evidence/stage-5-phase-9f.json`, route `R28`.

### R29

Owner: **9D**; mode: **ML**; status: **VERIFIED**.

Implementation: [ml/src/gamelens_recommender/feedback.py](../ml/src/gamelens_recommender/feedback.py).

- [ml/tests/test_feedback.py](../ml/tests/test_feedback.py) `::test_wishlist_is_persistable_but_ranking_neutral`
- [ml/tests/test_hybrid_ranker.py](../ml/tests/test_hybrid_ranker.py) `::test_wishlist_is_neutral_through_the_active_hybrid_pipeline`

Expected: Wishlist preserves the complete active-hybrid result and prepared context for positive/saved source, played, collaborative and content candidates under both 80/10/10 and 90/0/10 weights; inherited Stage 4 neutrality also passes in full ML.

Evidence: [9D verification](evidence/stage-5-phase-9d.json), route `R29`; focused and full ML suites. Later-layer evidence remains separate.

### R30

Owner: **9G**; mode: **API**; status: **EXISTING_NOT_RERUN**.

Implementation: [apps/api/app/api/v1/routes/personalized_recommendations.py](../apps/api/app/api/v1/routes/personalized_recommendations.py).

- [apps/api/tests/unit/test_personalized_recommendations.py](../apps/api/tests/unit/test_personalized_recommendations.py) `::test_personalized_openapi_contract_is_exact`
- [apps/api/tests/unit/test_stage_5_response_contract.py](../apps/api/tests/unit/test_stage_5_response_contract.py) `::test_stage_4_schema_remains_valid_while_saved_openapi_activates_stage_5`

Expected: Saved OpenAPI evolves explicitly; Stage 4 schema and stateless contract remain valid.

Evidence: future `docs/evidence/stage-5-phase-9g.json`, route `R30`.

### R31

Owner: **9K**; mode: **PG**; status: **EXISTING_NOT_RERUN**.

Implementation: [apps/api/app/db/seed.py](../apps/api/app/db/seed.py).

- [apps/api/tests/integration/test_postgres.py](../apps/api/tests/integration/test_postgres.py) `::test_migration_created_expected_schema_and_indexes`
- [apps/api/tests/integration/test_postgres.py](../apps/api/tests/integration/test_postgres.py) `::test_seed_is_idempotent`
- [apps/api/tests/integration/test_postgres.py](../apps/api/tests/integration/test_postgres.py) `::test_foreign_keys_are_enforced`
- [apps/api/tests/integration/test_postgres.py](../apps/api/tests/integration/test_postgres.py) `::test_ready_recommendation_uses_postgresql_snapshot_without_writes`
- [apps/api/tests/integration/test_stage_4_migrations.py](../apps/api/tests/integration/test_stage_4_migrations.py) `::test_populated_0002_upgrade_backfills_and_preserves_stage_4_state`

Expected: Inherited schema/index/FK, seed idempotency, read-only content snapshot and populated migration assertions; full suites still required.

Evidence: future `docs/evidence/stage-5-phase-9k.json`, route `R31`.

### R32

Owner: **9G**; mode: **API**; status: **EXISTING_NOT_RERUN**.

Implementation: [apps/api/app/services/recommendation/collaborative.py](../apps/api/app/services/recommendation/collaborative.py).

- [apps/api/tests/unit/test_collaborative_component.py](../apps/api/tests/unit/test_collaborative_component.py) `::test_unconfigured_component_is_immutable_and_does_not_touch_the_loader`
- [apps/api/tests/unit/test_collaborative_component.py](../apps/api/tests/unit/test_collaborative_component.py) `::test_loader_errors_are_normalized_without_exposing_details`
- [apps/api/tests/unit/test_collaborative_component.py](../apps/api/tests/unit/test_collaborative_component.py) `::test_fixture_bundle_requires_both_test_environment_and_explicit_gate`
- [apps/api/tests/unit/test_model_status_api.py](../apps/api/tests/unit/test_model_status_api.py) `::test_status_serializes_every_collaborative_state_without_changing_content`
- [apps/api/tests/unit/test_model_status_api.py](../apps/api/tests/unit/test_model_status_api.py) `::test_collaborative_failure_cannot_turn_content_ready_into_an_outage`

Expected: Intrinsic loader codes normalized without leaking details; fixture requires both guards; optional status cannot take required content down.

Evidence: future `docs/evidence/stage-5-phase-9g.json`, route `R32`.

### R33

Owner: **9F**; mode: **API**; status: **EXISTING_NOT_RERUN**.

Implementation: [apps/api/app/services/recommendation/readiness.py](../apps/api/app/services/recommendation/readiness.py).

- [apps/api/tests/unit/test_collaborative_readiness.py](../apps/api/tests/unit/test_collaborative_readiness.py) `::test_intrinsic_loader_failures_map_to_bounded_readiness_states`
- [apps/api/tests/unit/test_collaborative_readiness.py](../apps/api/tests/unit/test_collaborative_readiness.py) `::test_not_configured_is_an_immutable_unusable_decision`
- [apps/api/tests/unit/test_collaborative_readiness.py](../apps/api/tests/unit/test_collaborative_readiness.py) `::test_every_live_lineage_mismatch_fails_closed`

Expected: Readiness reason/state parameterizations prove intrinsic normalization and registry mismatch precedence.

Evidence: future `docs/evidence/stage-5-phase-9f.json`, route `R33`.

### W01

Owner: **9H**; mode: **WEB**; status: **EXISTING_NOT_RERUN**.

Implementation/helper: [apps/web/src/features/recommendations/personalized-recommendation-results.tsx](../apps/web/src/features/recommendations/personalized-recommendation-results.tsx). Exact test file: [apps/web/src/features/recommendations/personalized-recommendation-results.test.tsx](../apps/web/src/features/recommendations/personalized-recommendation-results.test.tsx).

- `renders server order and only the aggregate contribution that was applied`
- `presents typed fallback as usable and omits aggregate evidence`
- `announces a valid empty saved result without discarding saved context`
- `exposes live loading and keyboard-retry error states`

Expected: Order and applied-only evidence; usable fallback, empty/loading, keyboard retry.

Evidence: future `docs/evidence/stage-5-phase-9h.json`, route `W01`.

### W02

Owner: **9H**; mode: **WEB**; status: **EXISTING_NOT_RERUN**.

Implementation/helper: [apps/web/src/features/recommendations/persistent-recommendation-flow.tsx](../apps/web/src/features/recommendations/persistent-recommendation-flow.tsx). Exact test file: [apps/web/src/features/recommendations/persistent-recommendation-flow.test.tsx](../apps/web/src/features/recommendations/persistent-recommendation-flow.test.tsx).

- `keeps the stateless flow usable and creates no identity before affirmation`
- `invalidates a rendered shortlist when its persisted context changes`
- `re-consents an outdated lifecycle with CSRF and clears all data accessibly`

Expected: Request-only opt-out, stale result invalidation, saved-personalization re-consent/clear; not contribution consent.

Evidence: future `docs/evidence/stage-5-phase-9h.json`, route `W02`.

### W03

Owner: **9G**; mode: **WEB+DRIFT**; status: **EXISTING_NOT_RERUN**.

Implementation/helper: [apps/web/src/lib/api/generated.ts](../apps/web/src/lib/api/generated.ts). Exact test file: [apps/web/src/lib/api/generated.test.ts](../apps/web/src/lib/api/generated.test.ts).

- `keeps Stage 4 model status consumers compatible with optional component metadata`

Expected: Existing generated-type backward-compatibility assertion only; ownership is a source review of generated header/script plus strict typecheck and live api:types:check, not proved by this unit assertion.

Evidence: future `docs/evidence/stage-5-phase-9g.json`, route `W03`.

### B01

Owner: **9H**; mode: **FIXTURE**; status: **EXISTING_NOT_RERUN**.

Implementation/helper: [apps/web/e2e/hybrid-fixture-helpers.ts](../apps/web/e2e/hybrid-fixture-helpers.ts). Exact test file: [apps/web/e2e/hybrid.fixture.spec.ts](../apps/web/e2e/hybrid.fixture.spec.ts).

- `supported saved sources render the exact reconstructible server-ordered hybrid response`
- `saved dislike exclusion and played evidence survive real hybrid regeneration`
- `an unsupported saved source remains an honest cold-start fallback`
- `the request-only path remains stateless and content-only beside a ready fixture`

Expected: Real server order, reconstructible units, exclusions/played, cold source, stateless compatibility; smoke helper adds accessibility.

Evidence: future `docs/evidence/stage-5-phase-9h.json`, route `B01`.

### B02

Owner: **9H**; mode: **FIXTURE**; status: **EXISTING_NOT_RERUN**.

Implementation/helper: [apps/api/tests/fixtures/e2e_fixture_stack.py](../apps/api/tests/fixtures/e2e_fixture_stack.py). Exact test file: [apps/web/e2e/fallback.fixture.spec.ts](../apps/web/e2e/fallback.fixture.spec.ts).

- `an absent or invalid optional artifact preserves the exact Stage 4 browser result`

Expected: Fixture wrapper API probe covers seven reasons; browser subset detailed below. required_content_failure_probe asserts required-content 503 and no event.

Evidence: future `docs/evidence/stage-5-phase-9h.json`, route `B02`.

### B03

Owner: **9H**; mode: **LIFECYCLE**; status: **EXISTING_NOT_RERUN**.

Implementation/helper: [apps/api/tests/fixtures/e2e_lifecycle.py](../apps/api/tests/fixtures/e2e_lifecycle.py). Exact test file: [apps/web/e2e/lifecycle.live.smoke.spec.ts](../apps/web/e2e/lifecycle.live.smoke.spec.ts).

- `serialized live lifecycle phase`

Expected: Six serialized synthetic PostgreSQL lifecycle scenarios, observer exact privacy_invalid fallback, one matching event, safe teardown; private contribution controls are not public routes.

Evidence: future `docs/evidence/stage-5-phase-9h.json`, route `B03`.

### B04

Owner: **9H**; mode: **CONTENT**; status: **EXISTING_NOT_RERUN**.

Implementation/helper: [apps/web/playwright.config.ts](../apps/web/playwright.config.ts). Exact test file: [apps/web/e2e/accessibility.smoke.spec.ts](../apps/web/e2e/accessibility.smoke.spec.ts).

- `key routes have no serious automated accessibility violations`

Expected: Real-stack Chromium primary and Firefox/WebKit smoke; serious/critical axe, keyboard/focus and responsive companion specs.

Evidence: future `docs/evidence/stage-5-phase-9h.json`, route `B04`.

## Named manual reviews

These are pending reviews with concrete inputs and expected findings; mapping their route in 9A does not execute their final release scope.

### M01

**Authority and source review** — owner **9B**, mode **MANUAL**. Synthetic source review is complete in [9B evidence](evidence/stage-5-phase-9b.json); public contribution routes remain ABSENT and actual cohort authority remains **BLOCKED**.

Inputs: [docs/data-model.md](../docs/data-model.md), [data/fixtures/README.md](../data/fixtures/README.md), [apps/api/app/api/v1/router.py](../apps/api/app/api/v1/router.py), [apps/api/tests/fixtures/collaborative_lifecycle.py](../apps/api/tests/fixtures/collaborative_lifecycle.py).

Document source/purpose/cutoff/catalog/retention/limitations; inspect public router and separate contribution defaults. Public grant/re-consent/withdrawal routes and actual cohort approval are ABSENT/BLOCKED. Private synthetic helper is not product consent. Preserve block until an explicit scoped decision is recorded.

Evidence: `docs/evidence/stage-5-phase-9b.json`, review `M01`; retain findings and input hashes.

### M02

**Privacy and identity boundary review** — owner **9J**, mode **MANUAL**, current final evidence **MISSING** (M01 also has a **BLOCKED** authority decision).

Inputs: [apps/api/app/services/collaborative_build.py](../apps/api/app/services/collaborative_build.py), [ml/src/gamelens_recommender/collaborative_artifacts.py](../ml/src/gamelens_recommender/collaborative_artifacts.py), [.gitignore](../.gitignore), [.dockerignore](../.dockerignore).

Review success/failure output, artifacts, logs, events/responses, browser storage/media, reports, coverage/caches and staged files. Only transient in-memory extractor IDs and protected PostgreSQL lineage are allowed; no reusable raw snapshot, credential, user matrix or identity export. Inspect scorer API purity and sparse allocation boundaries. Retain sanitized findings/hashes, never raw payloads.

Evidence: future `docs/evidence/stage-5-phase-9j.json`, review `M02`; retain findings and input hashes.

### M03

**Five-baseline functional comparison review** — owner **9D**, mode **MANUAL**, status **VERIFIED within 9D**.

Inputs: [baseline](../ml/src/gamelens_recommender/baseline.py), [hybrid policy](../ml/src/gamelens_recommender/hybrid.py), [diagnostic generator](../ml/tests/hybrid_diagnostic.py) and [handoff goldens](../ml/tests/test_phase4_handoff.py).

The [eight-scenario table](evidence/stage-5-phase-9d-diagnostic.md) preserves native popularity/content/feedback/collaborative/hybrid candidate semantics, source/dislike exclusions, tie keys and top-K. Independent arithmetic explains support, absent edges, exact contributions and one played factor. Canonical and reversed equivalent inputs produce identical semantic arrays, identities and ordered tables. Retained evidence is synthetic and game-level only; no quality metrics, tuning, superiority or real-user conclusion.

Evidence: [9D verification](evidence/stage-5-phase-9d.json), review `M03`; commands and input/output hashes retained. Public cohort authority remains blocked separately in M01.

### M04

**Browser ownership and selection review** — owner **9H**, mode **MANUAL**, current final evidence **MISSING** (M01 also has a **BLOCKED** authority decision).

Inputs: [apps/web/src/features/recommendations/personalized-recommendation-results.tsx](../apps/web/src/features/recommendations/personalized-recommendation-results.tsx), [apps/web/src/features/recommendations/persistent-recommendation-flow.tsx](../apps/web/src/features/recommendations/persistent-recommendation-flow.tsx).

Inspect no client ranking/filter/reorder, stale-response cancellation and safe errors. Enumerate actual project/scenario tests and every mode skip; selected gate with zero tests or unexpected skip fails. Check keyboard, focus, live regions, responsive state and serious/critical axe.

Evidence: future `docs/evidence/stage-5-phase-9h.json`, review `M04`; retain findings and input hashes.

### M05

**Operator and ordinary-operation review** — owner **9E**, mode **MANUAL**, current final evidence **MISSING** (M01 also has a **BLOCKED** authority decision).

Inputs: [Makefile](../Makefile), [infra/run-phase8.py](../infra/run-phase8.py), [infra/run-e2e-fixture.sh](../infra/run-e2e-fixture.sh), [infra/run-e2e-lifecycle.sh](../infra/run-e2e-lifecycle.sh), [apps/api/app/commands/collaborative_artifact.py](../apps/api/app/commands/collaborative_artifact.py).

Compare direct commands to parsers/Make/wrappers, exact target confirmation and stable failure exits. Trace startup/request/migration/seed/ordinary tests/teardown for no implicit fitting/promotion/retirement/deletion. Project-owned setup/cleanup is explicit, never development data.

Evidence: future `docs/evidence/stage-5-phase-9e.json`, review `M05`; retain findings and input hashes.

### M06

**Current release inputs review** — owner **9J**, mode **MANUAL**, current final evidence **MISSING** (M01 also has a **BLOCKED** authority decision).

Inputs: [apps/api/pyproject.toml](../apps/api/pyproject.toml), [ml/pyproject.toml](../ml/pyproject.toml), [apps/web/package-lock.json](../apps/web/package-lock.json), [docker-compose.yml](../docker-compose.yml), [infra/docker-compose.test.yml](../infra/docker-compose.test.yml), [infra/docker-compose.e2e.yml](../infra/docker-compose.e2e.yml).

MISSING current evidence: collect final Python/npm locks, installed package integrity, licenses, vulnerabilities and remediation, image digests/runtime import/non-root/mount checks, Compose modes, secret scan and final diff. Derive exact scan commands from actual lock/runtime tools in 9J; no invented passing audit today.

Evidence: future `docs/evidence/stage-5-phase-9j.json`, review `M06`; retain findings and input hashes.

### M07

**Final evidence and docs reconciliation** — owner **9L**, mode **MANUAL**, current final evidence **MISSING** (M01 also has a **BLOCKED** authority decision).

Inputs: [docs/stage-5-collaborative-hybrid-ranking-plan.md](../docs/stage-5-collaborative-hybrid-ranking-plan.md), [docs/roadmap.md](../docs/roadmap.md), [README.md](../README.md).

MISSING final Phase 9 evidence: compare all 9L docs inventory, commands, outcomes/hashes, current Stage 4 versus implemented Stage 5 and provisional Stage 6. Required unresolved release decisions block completion; 9A does not finalize Sections 22/23.

Evidence: future `docs/evidence/stage-5-phase-9l.json`, review `M07`; retain findings and input hashes.

## Section 16 suite crosswalk

Every suite bullet is retained verbatim (whitespace normalized) below. Each maps to acceptance IDs whose routes define assertions, commands and owners. Cross-project diagnostics additionally belong to 9I; coverage identifies gaps and is not a passing percentage target.

### S16-01

**Snapshot and provenance suite:** Database-time cutoff, temporal state, reaction precedence, saved-game preference, rating threshold, source collapse, and stable canonical ordering.

Acceptance: [S5-AC-07](#s5-ac-07), [S5-AC-08](#s5-ac-08).

### S16-02

**Snapshot and provenance suite:** Current contribution consent, withdrawal, revocation, expiry, safety horizon, deletion, post-cutoff mutation, and dataset revision.

Acceptance: [S5-AC-04](#s5-ac-04), [S5-AC-05](#s5-ac-05), [S5-AC-07](#s5-ac-07), [S5-AC-14](#s5-ac-14), [S5-AC-15](#s5-ac-15).

### S16-03

**Snapshot and provenance suite:** Explicit proof that recommendation events, views, played-only, wishlist-only, and unknown rows are never positives.

Acceptance: [S5-AC-09](#s5-ac-09), [S5-AC-10](#s5-ac-10).

### S16-04

**Snapshot and provenance suite:** Aggregate-only audit, insufficiency reasons, catalog alignment, and no identity in output.

Acceptance: [S5-AC-03](#s5-ac-03), [S5-AC-06](#s5-ac-06), [S5-AC-11](#s5-ac-11).

### S16-05

**Collaborative ML suite:** Hand-calculated binary CSR, item support, pair support, cosine, quantization, diagonal removal, threshold order, top-neighbor pruning, and stable ties.

Acceptance: [S5-AC-19](#s5-ac-19), [S5-AC-20](#s5-ac-20).

### S16-06

**Collaborative ML suite:** Empty, single-user, single-item, unsupported, duplicate, invalid, oversized, and non-finite inputs.

Acceptance: [S5-AC-18](#s5-ac-18), [S5-AC-19](#s5-ac-19), [S5-AC-20](#s5-ac-20), [S5-AC-25](#s5-ac-25), [S5-AC-26](#s5-ac-26).

### S16-07

**Collaborative ML suite:** Reproducible semantic artifact from equivalent canonical input.

Acceptance: [S5-AC-16](#s5-ac-16), [S5-AC-20](#s5-ac-20), [S5-AC-21](#s5-ac-21).

### S16-08

**Hybrid-ranking suite:** Exact Stage 4 equivalence for every fallback reason.

Acceptance: [S5-AC-35](#s5-ac-35).

### S16-09

**Hybrid-ranking suite:** Positive/source/dislike exclusion before top-K, collaborative-only candidate union, active-component weights, played factor, wishlist neutrality, and fixed-point reconstruction.

Acceptance: [S5-AC-27](#s5-ac-27), [S5-AC-29](#s5-ac-29), [S5-AC-32](#s5-ac-32), [S5-AC-33](#s5-ac-33), [S5-AC-34](#s5-ac-34).

### S16-10

**Hybrid-ranking suite:** Cold user, cold source, cold item, mixed support, empty result, tie, and top-K boundaries.

Acceptance: [S5-AC-25](#s5-ac-25), [S5-AC-26](#s5-ac-26), [S5-AC-27](#s5-ac-27), [S5-AC-35](#s5-ac-35).

### S16-11

**Hybrid-ranking suite:** Request-wide missing-edge behavior and collaborative-only materialization with zero/empty content evidence and exact remaining base components.

Acceptance: [S5-AC-28](#s5-ac-28), [S5-AC-30](#s5-ac-30).

### S16-12

**Artifact and lifecycle suite:** Exact members, checksums, dtypes, shapes, canonical CSR, limits, compatibility, catalog fingerprint, interaction fingerprint, build ID, revision, lineage, validity horizon, immutable arrays, and path safety.

Acceptance: [S5-AC-15](#s5-ac-15), [S5-AC-19](#s5-ac-19), [S5-AC-21](#s5-ac-21), [S5-AC-22](#s5-ac-22).

### S16-13

**Artifact and lifecycle suite:** Missing, corrupt, extra, stale, retired, contributor-deleted, consent-invalid, and expired artifact rejection.

Acceptance: [S5-AC-14](#s5-ac-14), [S5-AC-23](#s5-ac-23).

### S16-14

**Artifact and lifecycle suite:** Crash-safe promotion, read-only validation/preview, guarded cleanup, and valid-only rollback.

Acceptance: [S5-AC-24](#s5-ac-24), [S5-AC-43](#s5-ac-43).

### S16-15

**API and PostgreSQL suite:** Populated upgrade/downgrade/re-upgrade, constraints, foreign-key cascades, revision concurrency, lineage count, transaction isolation, and catalog preservation.

Acceptance: [S5-AC-01](#s5-ac-01), [S5-AC-13](#s5-ac-13), [S5-AC-15](#s5-ac-15), [S5-AC-38](#s5-ac-38).

### S16-16

**API and PostgreSQL suite:** Additive model status, unchanged stateless response, personalized hybrid and fallback responses, typed errors, and one-event-per-committed-200 semantics.

Acceptance: [S5-AC-02](#s5-ac-02), [S5-AC-36](#s5-ac-36), [S5-AC-37](#s5-ac-37), [S5-AC-38](#s5-ac-38).

### S16-17

**API and PostgreSQL suite:** Component identity and fixed-point equality across response/event, plus bounded JSON shapes and retention compatibility.

Acceptance: [S5-AC-37](#s5-ac-37), [S5-AC-38](#s5-ac-38), [S5-AC-39](#s5-ac-39).

### S16-18

**Frontend and browser suite:** Generated type ownership, server-order preservation, conditional evidence, neutral fallback, no unsupported social claim, stale-response cancellation, and safe errors.

Acceptance: [S5-AC-37](#s5-ac-37), [S5-AC-40](#s5-ac-40), [S5-AC-41](#s5-ac-41), [S5-AC-42](#s5-ac-42).

### S16-19

**Frontend and browser suite:** Separate consent/withdrawal when implemented, request-only opt-out, rehydration, expiry, invalidation, clear data, keyboard, focus, live regions, serious/critical axe checks, and responsive layouts.

Acceptance: [S5-AC-04](#s5-ac-04), [S5-AC-05](#s5-ac-05), [S5-AC-14](#s5-ac-14), [S5-AC-42](#s5-ac-42).

### S16-20

**Frontend and browser suite:** Chromium primary matrix and critical Firefox/WebKit paths through the real disposable stack.

Acceptance: [S5-AC-01](#s5-ac-01), [S5-AC-42](#s5-ac-42).

### S16-21

**Cross-project suite:** Ruff lint/format, Python package integrity, strict TypeScript, ESLint, Prettier, production build, OpenAPI drift, npm and Python dependency checks, Compose validation, container runtime imports, non-root permissions, and complete Stage 1–4 regressions.

Acceptance: [S5-AC-01](#s5-ac-01), [S5-AC-43](#s5-ac-43), [S5-AC-45](#s5-ac-45).

### S16-22

**Cross-project suite:** Privacy scans for credentials, internal IDs, raw interactions, generated snapshots, artifact members, reports, browser traces, screenshots, coverage, caches, and environment files.

Acceptance: [S5-AC-11](#s5-ac-11), [S5-AC-12](#s5-ac-12), [S5-AC-22](#s5-ac-22), [S5-AC-39](#s5-ac-39), [S5-AC-45](#s5-ac-45).

## Inherited Stage 1–4 gates

All rows map to S5-AC-01; specialist routes also map to the narrower Stage 5 criteria above. Owner **9K** collects the full inherited runs, with fixes assigned to 9B–9J as appropriate. Status is **EXISTING_NOT_RERUN**; evidence goes to future `docs/evidence/stage-5-phase-9k.json` keyed by I01–I10. The entry path identifies the suite family, not an assertion that one test proves every inherited gate. Run the complete API unit, ML, PostgreSQL and web suites and the content wrapper, not only the selected R31/R01 nodes.

Normative inherited acceptance: [Stage 1](stage-1-backend-database-plan.md#19-acceptance-criteria), [Stage 2](stage-2-frontend-foundation-plan.md#19-acceptance-criteria), [Stage 3](stage-3-content-recommendation-mvp-plan.md#19-acceptance-criteria), [Stage 4](stage-4-feedback-persistence-plan.md#19-acceptance-criteria). The canonical JSON maps **171 inherited Section 19 bullets** individually, with unchanged wording, stable historical IDs, family, owner, evidence route and scope notes. Named review **I-COMPLETE** (9K, MANUAL) checks these mappings against actual full-run selections, records omissions as failures, and retains the per-bullet execution disposition in the 9K record. Historical untrained-only status/planned landing copy evolved explicitly in Stages 3–5; Stage 3 stateless and Stage 4 exact-fallback boundaries still apply. Active Stage 5 collaborative-only eligibility is an explicit extension, not a relaxation of those boundaries. Historical completion is not reused as current PASS.

### I01

Stage 1 schema, migrations, constraints, FK/cascades, seed idempotency/rollback, catalog contract.

Entry path: [apps/api/tests/integration/test_postgres.py](../apps/api/tests/integration/test_postgres.py). Mode: **PG**. Assertion/review routes: [R31](#r31). Expected: preserve all listed inherited behaviors; no unexpected skip, contract change or implicit operation.

### I02

Stage 1 health/config, catalog/metadata/errors, logging/security, launch and seed safety.

Entry path: [apps/api/tests/unit](../apps/api/tests/unit). Mode: **API**. Assertion/review routes: [R01](#r01), [R26](#r26). Expected: preserve all listed inherited behaviors; no unexpected skip, contract change or implicit operation.

### I03

Stage 2 URL navigation, search/filter/sort/pagination, detail/error/empty state, client types and rendering.

Entry path: [apps/web/src](../apps/web/src). Mode: **WEB**. Assertion/review routes: [W03](#w03), [B04](#b04). Expected: preserve all listed inherited behaviors; no unexpected skip, contract change or implicit operation.

### I04

Stage 2 keyboard/focus, responsive navigation, accessibility and browser compatibility.

Entry path: [apps/web/e2e/navigation.smoke.spec.ts](../apps/web/e2e/navigation.smoke.spec.ts). Mode: **CONTENT**. Assertion/review routes: [B04](#b04). Expected: preserve all listed inherited behaviors; no unexpected skip, contract change or implicit operation.

### I05

Stage 3 deterministic content fit/load, artifact/command integrity, request bounds and exact scoring.

Entry path: [ml/tests/test_recommender.py](../ml/tests/test_recommender.py). Mode: **ML**. Assertion/review routes: [R01](#r01), [R31](#r31). Expected: preserve all listed inherited behaviors; no unexpected skip, contract change or implicit operation.

### I06

Stage 3 real-stack recommendation and required-content failure behavior.

Entry path: [apps/web/e2e/recommendations.smoke.spec.ts](../apps/web/e2e/recommendations.smoke.spec.ts). Mode: **CONTENT+FIXTURE**. Assertion/review routes: [R01](#r01), [B02](#b02). Expected: preserve all listed inherited behaviors; no unexpected skip, contract change or implicit operation.

### I07

Stage 4 populated migrations, persistence/retention, isolation, CSRF, origin and anonymous consent.

Entry path: [apps/api/tests/integration/test_stage_4_persistence.py](../apps/api/tests/integration/test_stage_4_persistence.py). Mode: **PG+API**. Assertion/review routes: [R31](#r31), [R23](#r23). Expected: preserve all listed inherited behaviors; no unexpected skip, contract change or implicit operation.

### I08

Stage 4 feedback affinity, exclusions, played/wishlist, saved event/response and commit failure semantics.

Entry path: [ml/tests/test_feedback.py](../ml/tests/test_feedback.py). Mode: **ML+API**. Assertion/review routes: [R18](#r18), [R23](#r23), [R24](#r24), [R29](#r29). Expected: preserve all listed inherited behaviors; no unexpected skip, contract change or implicit operation.

### I09

Stage 4 browser opt-in/rehydration/re-consent/clear, feedback, cookie and protected errors.

Entry path: [apps/web/e2e/persistence.spec.ts](../apps/web/e2e/persistence.spec.ts). Mode: **CONTENT+WEB**. Assertion/review routes: [W02](#w02), [B04](#b04). Expected: preserve all listed inherited behaviors; no unexpected skip, contract change or implicit operation.

### I10

Stages 1–4 direct commands, lint/format/typecheck/build, Docker/runtime, dependency and OpenAPI gates.

Entry path: [Makefile](../Makefile). Mode: **CROSS**. Assertion/review routes: [M05](#m05), [M06](#m06), [W03](#w03), [M07](#m07). Expected: preserve all listed inherited behaviors; no unexpected skip, contract change or implicit operation.

## All 15 fallback reasons

The source of truth is [HYBRID_FALLBACK_REASONS](../ml/src/gamelens_recommender/hybrid.py): 11 unavailable reasons and 4 no-support reasons. For **each row**, R20 selects the corresponding ML parametrization; R21 selects unavailable/no-support API orchestration; R22 and R23 select the same `reason` at projection and HTTP/event boundaries. These injected boundary checks prove exact Stage 4 payload/order/units/reason and truthful Stage 5 envelope, not real production of every state; producer routes supply that separate evidence.

The [fixture wrapper](../infra/run-e2e-fixture.sh) calls `fallback_probe` for seven reasons, but browser services only for missing, corrupt and unsupported-source cases. Its `none` service selections are **API-only**, not skipped browser passes. `privacy_invalid` is selected by the [lifecycle wrapper](../infra/run-e2e-lifecycle.sh). All 15 ML reasons are VERIFIED by [9D](evidence/stage-5-phase-9d.json); producer/API/browser selections remain EXISTING_NOT_RERUN in Phase 9. The canonical JSON records `ml_status` separately from the aggregate row status. Owners: 9D ML, 9F lifecycle producers, 9G API, 9H browser disposition.

| Reason                   | Producing layer                                                                           | Producer checks                                    | Browser / real-stack selection                                        | Omission rationale or selected assertion                                                                                                                                             |
| ------------------------ | ----------------------------------------------------------------------------------------- | -------------------------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `not_configured`         | Unconfigured optional component before loading                                            | [R32](#r32), [R33](#r33)                           | Fixture API probe only                                                | No dedicated browser: same generic fallback presentation as missing artifact; R20/R21/R23 plus producer checks cover reason and exact payload.                                       |
| `fixture_not_allowed`    | Loader/config environment and explicit test gate                                          | [R10](#r10), [R32](#r32), [R33](#r33)              | Fixture API probe plus development/production rejection               | No dedicated browser: authority guard is a server configuration boundary; R20/R21/R23 and R10/R32 cover denial and exact fallback.                                                   |
| `insufficient_data`      | Request readiness activation users/edges/items minima                                     | [R28](#r28)                                        | None                                                                  | No dedicated browser: aggregate threshold arithmetic belongs to R28; R20/R21/R23 assert exact reason/envelope. 9F audits trivial live promotion.                                     |
| `artifact_missing`       | Loader file/path missing mapped by optional component                                     | [R32](#r32), [R33](#r33)                           | Fixture API + Chromium fallback.fixture.spec.ts                       | Browser selected for absent artifact.                                                                                                                                                |
| `artifact_corrupt`       | Loader checksum/format failure normalized by optional component                           | [R13](#r13), [R32](#r32), [R33](#r33)              | Fixture API + Chromium fallback.fixture.spec.ts                       | Browser selected for corrupt artifact.                                                                                                                                               |
| `artifact_incompatible`  | Loader schema/model incompatibility; malformed readiness facts or isolated scorer failure | [R13](#r13), [R21](#r21), [R32](#r32), [R33](#r33) | None                                                                  | No dedicated browser: same unavailable rendering; lower-layer incompatibility and injected scorer-failure checks plus R20/R21/R23 prove reason/payload.                              |
| `artifact_stale`         | Loader revision code or registry build/revision/cutoff/validity identity mismatch         | [R09](#r09), [R32](#r32), [R33](#r33)              | None                                                                  | No dedicated browser: revision mismatch is covered at readiness/registry and all-reason exact fallback; lifecycle browser invalidation produces privacy_invalid, not artifact_stale. |
| `privacy_invalid`        | Missing/malformed lineage, invalidated epoch/status, count/fingerprint/consent mismatch   | [R07](#r07), [R08](#r08), [R09](#r09)              | Lifecycle API + serialized live lifecycle phase                       | Browser selected for actual registered synthetic invalidation; private contribution operations do not implement public consent.                                                      |
| `artifact_expired`       | Loader or request-time validity horizon reached                                           | [R09](#r09), [R14](#r14), [R33](#r33)              | Fixture API probe only                                                | No dedicated browser: time boundary is server-owned; lower-layer expiry checks plus R20/R21/R23 cover exact fallback.                                                                |
| `catalog_stale`          | Loader catalog mismatch or request/registry catalog fingerprint mismatch                  | [R09](#r09), [R14](#r14), [R32](#r32), [R33](#r33) | Fixture API probe only                                                | No dedicated browser: optional catalog mismatch is distinct from required-content failure; R20/R21/R23 and required-content probe cover the boundary.                                |
| `artifact_retired`       | Registered lineage status retired                                                         | [R07](#r07), [R09](#r09), [R33](#r33)              | None                                                                  | No dedicated browser: retirement terminality belongs to registry/readiness tests; R20/R21/R23 retain exact fallback and typed reason.                                                |
| `no_query_sources`       | Pure scorer sees zero query sources                                                       | [R16](#r16)                                        | None                                                                  | No dedicated browser: source-less prepared policy input tested below UI; R20/R21/R23 cover exact fallback, without inventing a UI input path.                                        |
| `no_supported_sources`   | Pure scorer has sources but none on artifact item axis                                    | [R16](#r16)                                        | Fixture API + hybrid.fixture.spec.ts + fallback.fixture.smoke.spec.ts | Chromium hybrid cold source and Chromium/Firefox/WebKit fallback smoke selected.                                                                                                     |
| `no_candidate_edges`     | Pure scorer has supported sources but zero visited retained edges                         | [R16](#r16)                                        | None                                                                  | No dedicated browser: supported zero-degree row is a hand-authored sparse case; R16 plus R20/R21/R23 prove no fabricated evidence.                                                   |
| `no_eligible_candidates` | Pure scorer visited edges but source/dislike exclusions remove every candidate            | [R16](#r16)                                        | None                                                                  | No dedicated browser: R16 asserts all candidates excluded and exact diagnostics; R20/R21/R23 assert payload fallback, with R17 covering exclusion-before-top-K.                      |

Browser companion nodes: [fallback smoke](../apps/web/e2e/fallback.fixture.smoke.spec.ts), `cold start remains an accessible exact fallback across browsers`; [hybrid smoke](../apps/web/e2e/hybrid.fixture.smoke.spec.ts), `the project-authored synthetic fixture gives functional hybrid evidence without a quality claim`. [Playwright](../apps/web/playwright.config.ts) selects all specs for Chromium and only `*.smoke.spec.ts` for Firefox/WebKit. [Fallback helper](../apps/web/e2e/fallback-fixture-helpers.ts) compares exact Stage 4 reference fields and cautious copy. No dedicated browser is planned for the other pure policy/server-state reasons because the explicit lower-layer tests cover them; 9H must still record actual selection and unexpected skips.

## Frozen five-baseline comparison scope

Owner **9D**, mapped to S5-AC-31 and M03. **VERIFIED** in the [five-variant table](evidence/stage-5-phase-9d-diagnostic.md) and [9D record](evidence/stage-5-phase-9d.json). The original 9A frozen requirements below are preserved; eight synthetic scenarios now exercise them.

- Use one small project-authored scenario set with hand-derived expected values; record catalog/fixture fingerprints, model/policy identity and query context without user identities.
- Compare **popularity, content, feedback, collaborative and hybrid**. For each variant explicitly state its candidate universe, source/dislike exclusions, unsupported behavior, tie-break key and top-K. Reuse current policy functions and retain variant-specific semantics; do not silently force identical universes.
- Retain game slug, candidate origin/support, applicable raw components, fixed-point weights/contributions, played adjustment, final units and rank. An unavailable component is explicitly absent/unsupported, not an invented score.
- Include collaborative-only admission, missing edge under active request-wide weights, supported/cold/mixed/empty/tied cases, exclusion before top-K, one played factor and neutral wishlist. Existing content zero-content eligibility stays unchanged.
- Run twice on equivalent canonical input and compare semantic arrays, identities and ordered diagnostics. Record differences with exact component arithmetic. No Precision/Recall/NDCG, tuning, superiority, engagement or real-user claim.

## Known gaps and boundaries

Public contribution grant/re-consent/withdrawal routes and UI are absent, and no actual user cohort has approved authority. This blocks the applicable production acceptance clauses (S5-AC-03/05/14/42); synthetic private lifecycle checks cannot discharge them. Default-off and request-only checks can be verified independently. A future explicit fixture-only release-scope decision must identify exactly which clauses remain blocked; no unexplained N/A or implicit release approval is allowed.

Current final dependency/license/security/privacy evidence (9J), diagnostic coverage/gap disposition (9I), clean combined replay (9K) and final docs reconciliation (9L) remain missing. The five-baseline table (9D) is now verified. Existing tests are assertion routes, not exhaustive-coverage or current-pass claims. 9B has closed snapshot/provenance gaps with focused runtime evidence. 9C has closed its pure ML gaps and 9D its hybrid/functional comparison scope; 9E–9L own their remaining work and are unstarted.
