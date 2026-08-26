# Lifecycle checkpoints

`lifecycle.lifecycle-checkpoints` adds historical transition evidence to Composition's existing current-state contracts. It does not replace `contracts/implementation-evidence.json`; the requirement ledger and stable target IDs remain authoritative there. A checkpoint records the exact validated contract state that existed at a lifecycle boundary and binds the next product state to that planning baseline.

## Canonical workflow

For an initial implementation, author the capability contracts and `contracts/implementation-evidence.json` in `planning` mode, then run normal Composition validation. After it passes, create the immutable planning checkpoint:

```text
python .template-composition/checkpoint.py planning --id initial-planning
```

Only after that checkpoint exists should product implementation begin. When the contracts and evidence have been completed in `product` mode, normal Composition validation requires the latest planning checkpoint and verifies that requirement IDs, descriptions, contract-item targets, and required proof kinds still match the validated planning baseline. Then close the transition:

```text
python .template-composition/checkpoint.py product --id initial-product --from initial-planning
```

For a later specification change, first put the intended contracts/evidence into their planning forms and validate them. The next planning checkpoint is automatically parented to the previous product checkpoint and is classified as `specification-change`. Product coding follows that checkpoint, not the previous product state.

## Snapshot authority

Each ledger entry points to `artifacts/lifecycle/NNN-<id>/manifest.json`. The manifest lists SHA-256 hashes for the historical `contracts/manifest.json`, every contract document and schema registered by that historical manifest, and available Composition validation authority files. `validation.json` preserves the successful canonical selected-component validation result and is itself hash-bound by the snapshot manifest. The ledger stores the snapshot-manifest hash.

Chronology is defined by the contiguous sequence number, parent edge, phase alternation, and content hashes. `recordedAt` is diagnostic metadata only; validators never use wall-clock ordering as authority. An optional `--source-revision` records a VCS revision as an external anchor, but Composition does not require Git and does not infer ancestry from that value.

The validator derives each historical snapshot's required file set from the snapshotted contract manifest, not from today's registry. Later Composition upgrades therefore do not retroactively invalidate old checkpoints.

## What is machine-checkable

The selected-component validator fails closed when product mode has no validated planning checkpoint; a checkpoint manifest, snapshotted contract/schema, or validation result is modified without updating its bound hash; checkpoint sequence, parent, phase, or change classification is inconsistent; a product transition removes or adds a requirement absent from its planning checkpoint; a requirement's description, stable contract target IDs, or required proof kinds change between planning and product; or a checkpointed current planning/product contract state drifts.

Planning snapshots do not require implementation locators, commands, release gates, or implementation boundaries. Those remain product-only implementation-evidence fields.

## Limits and external anchors

A local hash chain is tamper-evident relative to the current ledger, but it is not a trusted timestamp service. A party able to rewrite the entire ledger, every snapshot, and every hash can manufacture an internally consistent alternate history. Composition can therefore guarantee that the present product state is bound to a preserved validated planning snapshot, but it cannot prove physical real-world coding chronology against a malicious wholesale history rewrite without an external append-only/VCS/signature anchor.

Composition also does not hash the entire product source tree by default. Product implementation locators remain evidence boundaries, and an optional external source revision may be recorded. Requiring a universal source-tree hash would incorrectly make Composition depend on a particular VCS/worktree model and would duplicate product-owned release revision authority.

## Migration

Existing template/planning consumers may upgrade and create their next planning checkpoint normally. An already implemented product with no historical checkpoint is deliberately not grandfathered as if pre-coding validation had occurred: product validation fails. Move the next intended change through planning, validate it, and create a planning checkpoint before further implementation. If historical proof is required for an older product, use an external VCS/attestation record rather than retroactively manufacturing a Composition checkpoint.
