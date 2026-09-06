# implementation-evidence v1 to v2

Version 2 makes the product requirement ledger mandatory.

## Breaking changes

- `schemaVersion` changes from `1` to `2`.
- `requirements` is now a required top-level field in every document.
- template mode must use `"requirements": []`.
- product mode must provide at least one requirement row.
- requirement IDs may use the existing lowercase identifier style or an uppercase hyphenated stable ID such as `REQ-SEVERITY-BROWSER-FILTER`.

The existing `requiredPositiveProofKinds` field, proof statuses (`verified` / `deferred`), proof kinds, record structure, command references, and release-gate semantics are unchanged.

## Migration

For a template document, add `requirements: []` and change `schemaVersion` to `2`.

For a product document:

1. change `schemaVersion` to `2`;
2. enumerate the explicit product requirements that are intended to justify completion;
3. give each requirement a stable ID, description, and one or more `recordIds`;
4. for caller-visible behavior, declare `requiredPositiveProofKinds` when a minimum proof execution class is required;
5. rerun registered-contract validation, implementation-evidence validation, artifact-specific evidence validation, and release-readiness validation.

Do not add a synthetic catch-all requirement merely to satisfy the schema. The purpose of v2 is to prevent product completion from being claimed when the explicit product intent has never been made machine-visible.
