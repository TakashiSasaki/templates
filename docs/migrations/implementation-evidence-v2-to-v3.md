# Implementation evidence v2 to v3 migration

Schema v3 makes proof-strength intent mandatory for every product requirement.

## Breaking change

Each entry in `requirements` must now contain a non-empty `requiredPositiveProofKinds` array.

This closes a fail-open path in v2 where a product could register a requirement and link it to implementation evidence while omitting the machine-readable statement of which proof kinds are strong enough for that requirement.

The existing proof-kind vocabulary is unchanged:

- `inspection`
- `unit-test`
- `integration-test`
- `migration-test`
- `end-to-end-test`
- `accessibility-test`
- `other`

No new execution-class field is introduced. `kind` remains the proof execution/strength classification.

## Product migration

For every existing product requirement:

1. decide which existing proof kinds are sufficient for the caller-visible requirement;
2. add those kinds to `requiredPositiveProofKinds`;
3. do not select a weaker kind merely because that proof is easier to run;
4. ensure at least one linked positive proof has a declared required kind; and
5. keep unavailable required proof `deferred` rather than substituting a weaker proof and claiming readiness.

Typical examples:

- a pure domain calculation may use `unit-test`;
- a packaged CLI invocation normally requires executable process-level proof such as `integration-test`;
- HTTP behavior normally requires proof through the service boundary rather than source inspection;
- browser interaction, focus, keyboard, and viewport behavior normally require `end-to-end-test` and/or `accessibility-test`.

Artifact-specific validators may impose stronger minimum proof requirements. This lifecycle schema does not infer required kinds from requirement prose.

## Template migration

Template mode still has an empty requirement ledger. Change `schemaVersion` from `2` to `3`; no synthetic requirement or proof kind should be added to a template seed.
