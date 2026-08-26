# implementation-evidence v1 → v2

Version 2 adds explicit product-requirement traceability to the existing implementation-evidence graph.

## What changed

- `schemaVersion` is now `2`.
- The root document has a required `requirements` array.
- Every product requirement has a stable `id` and a human-readable `description`.
- Every product-mode evidence record has a non-empty `requirementIds` array.
- Product requirements that are not referenced by any evidence record are invalid.
- Template mode remains intentionally empty and therefore uses `"requirements": []`.

The validator does not interpret requirement descriptions. It only verifies that the explicit requirement identities are connected to existing implementation-evidence records and therefore to their verified boundaries, proofs, authoritative commands, and release gates.

## Migration

For template mode, add `"requirements": []` and change `schemaVersion` to `2`.

For product mode:

1. enumerate every explicit product requirement once in `requirements`;
2. assign each requirement a stable ID;
3. add `requirementIds` to every evidence record;
4. link each requirement to at least one evidence record whose target and proofs actually establish that requirement;
5. run registered contract validation and implementation-evidence semantic validation.

Do not create a parallel requirement ledger carrying the same release semantics. The v2 `requirements` array is the explicit-intent entry point for the existing implementation-evidence graph.
