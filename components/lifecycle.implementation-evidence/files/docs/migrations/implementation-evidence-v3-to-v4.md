# implementation-evidence v3 to v4

v4 adds a truthful `planning` state for capturing the stable product requirement ledger before implementation exists.

Migration from an existing v3 document is deterministic:

1. Change `schemaVersion` from `3` to `4`.
2. Keep an existing `template` document otherwise unchanged.
3. Keep an existing `product` document otherwise unchanged.

Use the new `planning` mode only when product requirements are known but implementation records do not yet exist. In planning mode `commands`, `releaseGates`, and `records` are empty; `requirements` is non-empty; every requirement has a stable ID, description, non-empty `requiredPositiveProofKinds`, and an empty `recordIds` array. Preserve those requirement IDs when moving to product mode and connect them to the implemented records instead of replacing them with new IDs.

`planning` is intentionally not release-ready. Release readiness accepts only `product` mode with fully verified required evidence.
