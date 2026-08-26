# implementation-evidence v1 → v2

Version 2 makes the explicit product-requirement ledger mandatory in product mode.

## Breaking changes

- `schemaVersion` is `2`.
- `requirements` is required at the document root.
- template mode uses `"requirements": []`.
- product mode requires at least one requirement.
- requirement IDs have their own stable identifier syntax and may use forms such as `REQ-SEVERITY-BROWSER-FILTER`.

Existing proof-strength and deferred-evidence semantics are unchanged. A `deferred` proof remains structurally representable but blocks release readiness.

## Migration

For template mode, set `schemaVersion` to `2` and add an empty `requirements` array.

For product mode:

1. enumerate every explicit product requirement once in `requirements`;
2. give each requirement a stable ID and description;
3. link it to one or more existing implementation-evidence records with `recordIds`;
4. ensure those records retain the existing proof → command → release-gate traceability;
5. run registered-contract validation and implementation-evidence validation.

Composition does not interpret the requirement description. The ledger makes explicit intent machine-visible; artifact-specific validators still decide whether a proof kind is strong enough for a particular target.
