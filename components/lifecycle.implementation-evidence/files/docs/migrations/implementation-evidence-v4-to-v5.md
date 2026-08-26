# implementation-evidence v4 to v5

v5 makes pre-coding planning requirements target-aware.

This closes a planning gap in v4: a requirement could declare a strong proof kind before coding, but the machine-readable planning state did not say whether that requirement was intended for a browser route, CLI entrypoint, service operation, MCP operation, MCP App View, contract transition, or another registered target. Target-specific validators therefore could not validate proof strength until product records were created.

## Migration

1. Change `schemaVersion` from `4` to `5`.
2. Keep a `template` document otherwise unchanged; its requirement ledger remains empty.
3. For every `planning` requirement, add non-empty `targets` using the same canonical target objects used by implementation records. Keep `recordIds: []`.
4. Existing `product` requirements do not need a new `targets` field. Their linked implementation records remain the canonical product target mapping.
5. A product requirement may retain the planning `targets`. If it does, v5 requires that target set to match the targets of its linked `recordIds` exactly.

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

Preserve the stable requirement ID when moving from planning to product. Retaining `targets` is recommended when the product wants an explicit consistency check between planned intent and linked records, but the validator cannot reconstruct historical intent after both fields have been edited; version-control review remains the authority for the planning-to-product change itself.

For an existing v4 product document, migration is therefore deterministic: update `schemaVersion` to `5` and leave the requirement/record graph otherwise unchanged. If you choose to add product `targets`, derive them from the linked record targets and review them as product intent rather than treating the mechanical derivation as independent proof.

v5 remains strict about release readiness: only product mode with fully verified required evidence can become release-ready.
