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
profile keys, and is accepted only under the same test-only gate. Phase 3 uses
the production-loaded temporary bundle to verify canonical source selection,
exact CSR traversal, collaborative scoring, and exact-row content/affinity
handoff without adding identity or making the fixture serveable.

Fixture results demonstrate functional behavior and reproducibility only. They
are not evidence of recommendation quality or representative user behavior.
