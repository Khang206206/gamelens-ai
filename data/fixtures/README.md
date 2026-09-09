# Project-authored fixtures

This directory is reserved for small, deterministic, visibly synthetic data
owned by GameLens. External dataset excerpts, real user identifiers, copied
reviews, and generated snapshots do not belong here.

`interactions/collaborative-interactions.json` is the versioned
`stage-5-collaborative-interactions-v1` fixture. It contains 12 synthetic
profiles, 36 expected positive edges over 6 catalog games, explicit negative/
absent-label examples, and cold-start cases. Its label policy is
`gamelens-collaborative-labels/1.0.0`.

The strict loader accepts it only when `ENVIRONMENT=test` and
`COLLABORATIVE_ALLOW_TEST_FIXTURE=true` are both set. The ordinary development
and production configuration rejects fixture access. It reads at most 1,000,000
bytes and rejects duplicate or unrecognized root, profile, exclusion,
cold-start, and expectation keys, non-finite constants, and JSON type aliases.
Golden interaction and fixture-contract fingerprints plus exact canonical
exclusion/support/pair expectations make label or exclusion drift fail closed.
Run the aggregate-only functional audit from the repository root:

```powershell
make collaborative-fixture-audit
```

The audit command writes no row-level snapshot or artifact. Its canonical report
contains no synthetic profile key and records that live-training eligibility is
false. The implemented Phase 2 builder consumes the same guarded fixture to
build and validate a separate aggregate-only artifact:

```powershell
make collaborative-build
make collaborative-validate
```

That bundle contains item-level support and neighborhoods, never profiles or
profile keys, and is accepted only under the same test-only gate. Phases 3–4 use
the production loader to verify canonical source selection, exact CSR traversal,
collaborative scoring, exact-row materialization, hybrid union, and fallback.
Phase 5 loads it only in the guarded test application to exercise component
readiness and saved-request orchestration. Phase 6 uses the resulting typed
decision to verify synchronized hybrid response/event projection. The fixture
cannot receive live registry status or authorize development/production serving.

Fixture results demonstrate functional behavior and reproducibility only. They
are not evidence of recommendation quality or representative user behavior.

## Disposable PostgreSQL cohort

Phase 8 also uses a separate project-authored database cohort from
[the guarded scenario helper](../../apps/api/tests/fixtures/collaborative_lifecycle.py).
The JSON fixture is never inserted or relabelled as live. The helper creates
synthetic sessions and separate contribution-consent rows only after validating
both configured and connected test database identity, exact test/reset opt-in,
an allowlisted host and a database ending `_test`. Eligibility uses captured
database time, including explicit expired, revoked, outdated, negative and
pruned examples. Repeated complete setup is bounded/idempotent; partial state
fails closed. Public personalization consent alone never grants contribution.

The actual extractor/build command produces `source_kind=live` over these
synthetic PostgreSQL rows. The standalone live-source builds retain 12
contributors; lifecycle scenarios add a privately linked browser contributor
and retain 13. Registry lineage stays in PostgreSQL; bundles and retained run
records contain only item aggregates, hashes and counts. Tokens and cohort
mappings stay in disposable private test storage and are not exported. Fresh
project-local teardown removes test state; no development users or artifacts
are mounted. This is functional lifecycle evidence, not permission to train on
production users or evidence of recommendation quality.

See the [Phase 8 record](../../docs/stage-5-phase-8-docker-fixtures-plan.md) and
[infra commands](../../infra/README.md) for fixture versus live-source execution.
