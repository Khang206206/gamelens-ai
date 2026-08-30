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
and production configuration rejects fixture access. It reads at most
1,000,000 bytes and rejects duplicate or unrecognized root, profile, exclusion,
cold-start, and expectation keys, non-finite constants, and JSON type aliases.
Golden interaction and fixture-contract fingerprints plus exact canonical
exclusion/support/pair expectations make label or
exclusion drift fail closed. Run the aggregate-only functional audit from the repository root:

```powershell
make collaborative-fixture-audit
```

The audit command writes no row-level snapshot or artifact. Its canonical
report contains no synthetic profile key and records that live-training
eligibility is false. Phase 2 may consume the same guarded fixture to build and
validate a separate aggregate-only artifact:

```powershell
make collaborative-build
make collaborative-validate
```

That bundle contains item-level support and neighborhoods, never profiles or
profile keys, and is accepted only under the same test-only gate. Phases 3–4 use
the production loader to verify canonical source selection, exact CSR traversal,
collaborative scoring, exact-row materialization, hybrid union, and fallback.
Phase 5 may load it only in the guarded test application to exercise component
readiness and internal saved-request orchestration. It cannot receive live
registry status or authorize development/production serving, and the public
response/event remains Stage 4 until Phase 6.

Fixture results demonstrate functional behavior and reproducibility only. They
are not evidence of recommendation quality or representative user behavior.
