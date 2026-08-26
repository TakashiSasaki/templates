# implementation-evidence v4 to v5

v5 binds every non-template product requirement directly to the contract target or targets it intends to satisfy.

This closes a planning gap in v4: a requirement could declare a strong proof kind before coding, but the machine-readable planning state did not say whether that requirement was intended for a browser route, CLI entrypoint, service operation, MCP operation, MCP App View, contract transition, or another registered target. Target-specific validators therefore could not validate proof strength until product records were created.

## Migration

1. Change `schemaVersion` from `4` to `5`.
2. Keep a `template` document otherwise unchanged; its requirement ledger remains empty.
3. For every `planning` or `product` requirement, add non-empty `targets` using the same canonical target objects used by implementation records.
4. In `planning` mode, keep `recordIds: []`. Preserve both the requirement ID and its `targets` when moving to product mode.
5. In `product` mode, ensure the set of targets declared by each requirement exactly matches the set of targets implemented by its linked `recordIds`.

Example planning requirement:

```json
{
  "id": "REQ-CLI-FILTER",
  "description": "The packaged CLI filters caller-visible records by severity.",
  "targets": [
    {
      "kind": "contract-item",
      "contractId": "cli_interface",
      "itemKind": "entrypoint",
      "itemId": "records"
    }
  ],
  "recordIds": [],
  "requiredPositiveProofKinds": ["integration-test"]
}
```

When that requirement becomes product evidence, keep the same target object and link the implementation record for that target. Do not replace the planning target with a different target merely because implementation happened elsewhere.

For an existing v4 product document, derive each requirement's initial `targets` from the targets of the records named by that requirement's `recordIds`, then review the result as product intent rather than treating the mechanical derivation as independent proof.

v5 remains strict about release readiness: only product mode with fully verified required evidence can become release-ready.
