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

Checkpoint creation is transactional. The writer first runs canonical selected-component validation and preserves that pre-write result as the historical proof that the state was already valid. It then writes the snapshot and ledger entry and runs canonical validation again. If the appended checkpoint is invalid, both the new ledger entry and snapshot are rolled back rather than leaving a partial or orphaned checkpoint.

## Machine action command authority

The checkpoint component owns `.template-composition/lifecycle-checkpoint-actions.json`, a managed registry of canonical argument-vector templates for planning and product checkpoint creation. Its schema is materialized as `.template-composition/lifecycle-checkpoint-actions.schema.json`. This registry is the machine-facing command authority for checkpoint creation; another lifecycle component must not reconstruct `checkpoint.py` command syntax independently.

The public machine actions invoke the provider-owned `.template-composition/run_action.py` dispatcher. Internal `checkpoint.py` paths, phase options, `--from` ordering, and working-directory semantics are therefore provider implementation details rather than caller reconstruction obligations. The registry separates caller-owned placeholders such as `{python}` and `{checkpoint_id}` from provider-owned bindings. `{python}` means one executable path for a supported CPython 3.11 through 3.14 interpreter and occupies exactly one argv token; no interpreter flags are caller inputs. For the product transition, `{latest_checkpoint_id}` remains bound to `latest-checkpoint-id`, allowing the lifecycle projection to resolve the exact current planning checkpoint before execution while leaving the caller to choose only the new checkpoint ID and supported interpreter executable.

The managed registry schema fixes each complete public argv with `const`. Consumers replace only whole-token entries listed in `caller_inputs`, execute the resulting argv from the materialized repository root, and do not add, remove, reorder, or inject interpreter options. Commands remain argument vectors rather than shell strings, so no shell quoting contract is introduced. Provider-owned bindings are not caller inputs.

Checkpoint machine results are JSON. Successful or failed dispatcher results identify `.template-composition/lifecycle-checkpoint-action-result.schema.json` through a mandatory `$schema` field, so a caller does not infer result shape from prose or the final filesystem. The wrapper preserves the provider return code as structured data and keeps a failed checkpoint attempt distinct from a successfully created checkpoint. The direct `checkpoint.py` examples above remain human-oriented entrypoints; coding agents following `next_action_command` should execute the registry-derived dispatcher argv instead of reconstructing those examples.

The registry is a closed managed contract for runtime metadata: unknown action names, a non-canonical schema reference, undeclared placeholders, provider bindings that are not consumed by the selected argv, or argv drift from the exact dispatcher shape are rejected rather than ignored. This prevents a syntactically plausible but semantically ambiguous registry from becoming executable lifecycle guidance.

`lifecycle.composition-state` may project one of these command templates after ordinary selected-component validation succeeds. It does not own the templates and must fail closed if the managed registry cannot be interpreted. Checkpoint ordering, parentage, validation, transactionality, and ID acceptance continue to be enforced by `checkpoint.py` and the checkpoint validator.

## Snapshot authority

Each ledger entry points to `artifacts/lifecycle/NNN-<id>/manifest.json`. The manifest lists SHA-256 hashes for the historical `contracts/manifest.json`, each non-checkpoint registered contract document, all registered contract schemas including the lifecycle-checkpoint schema, and available Composition validation authority files. The lifecycle checkpoint ledger itself is not copied into its own snapshot because that would create a self-referential hash cycle. `validation.json` preserves the successful canonical selected-component validation result and is itself hash-bound by the snapshot manifest. The ledger stores the snapshot-manifest hash.

Chronology is defined by the contiguous sequence number, parent edge, phase alternation, and content hashes. `recordedAt` is diagnostic metadata only; validators never use wall-clock ordering as authority. An optional `--source-revision` records a VCS revision as an external anchor, but Composition does not require Git and does not infer ancestry from that value.

The validator derives each historical snapshot's required file set from the snapshotted contract manifest, not from today's registry. Later Composition upgrades therefore do not retroactively invalidate old checkpoints. Managed schema/runtime changes are preserved historically but are not treated as consumer specification drift; current drift checks apply to consumer-owned contract documents.

## What is machine-checkable

The selected-component validator fails closed when product mode has no validated planning checkpoint; a checkpoint manifest, snapshotted contract/schema, or validation result is modified without updating its bound hash; snapshot structure or canonical validation binding is malformed; checkpoint sequence, parent, phase, or change classification is inconsistent; a product transition removes or adds a requirement absent from its planning checkpoint; a requirement's description, stable contract target IDs, or required proof kinds change between planning and product; or a checkpointed current planning/product contract state drifts.

Planning snapshots do not require implementation locators, commands, release gates, or implementation boundaries. Those remain product-only implementation-evidence fields.

## Limits and external anchors

A local hash chain is tamper-evident relative to the current ledger, but it is not a trusted timestamp service. A party able to rewrite the entire ledger, every snapshot, and every hash can manufacture an internally consistent alternate history. Composition can therefore guarantee that the present product state is bound to a preserved validated planning snapshot, but it cannot prove physical real-world coding chronology against a malicious wholesale history rewrite without an external append-only/VCS/signature anchor.

Composition also does not hash the entire product source tree by default. Product implementation locators remain evidence boundaries, and an optional external source revision may be recorded. Requiring a universal source-tree hash would incorrectly make Composition depend on a particular VCS/worktree model and would duplicate product-owned release revision authority.

## Migration

Existing template/planning consumers may upgrade and create their next planning checkpoint normally. An already implemented product with no historical checkpoint is deliberately not grandfathered as if pre-coding validation had occurred: once the checkpoint authority is selected, product validation without a planning checkpoint fails.

For an existing product that must upgrade to this authority, prepare the *next intended change* as planning under the previous Composition authority first: move the relevant capability contracts and implementation evidence into their supported planning forms, validate that planning state, then upgrade Composition. After the new authority is materialized, validate again and create the first planning checkpoint before changing product implementation. This migration preserves the claim that the first checkpoint was created from a planning state; it does not manufacture historical proof for work that predates the checkpoint authority.

If historical proof is required for an older product, use an external VCS/attestation record rather than retroactively manufacturing a Composition checkpoint.
