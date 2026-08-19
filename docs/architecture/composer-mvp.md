# Composer MVP and managed-state contract

## Scope

The deterministic Composer uses the public lifecycle:

```text
inspect -> plan -> apply -> validate
```

The initial-composition behavior remains fail-closed for a target that already contains `.template-composition/lock.json`. Managed-state update and upgrade are separate operations; they are not inferred by initial composition.

This document also defines the lock-schema-v2 foundation required by update/upgrade. The read-only reconciliation planner and mutation/recovery protocol are implemented in subsequent independently reviewable changes.

## Source authority

The Composer runs from a clean `composition` source checkout. It binds every successful plan/apply to the exact full Git commit returned by `git rev-parse HEAD` and refuses tracked source modifications.

The production catalog is loaded closed: catalog IDs must exactly match `components/` and `recipes/`, descriptors/recipes must validate against their schemas, dependencies must exist and be acyclic, and generic capability/lifecycle components must not depend on artifact authorities.

## Resolution and consumer intent

One production recipe determines the artifact and selectable component surface. Resolution starts from:

```text
artifact
+ recipe.required_components
+ recipe.default_components not explicitly excluded
+ configuration.components.include
```

Then all `requires` dependencies are added transitively.

The resolver fails closed for include/exclude overlap, unexposed selections, exclusion of required/transitive dependencies, active conflicts, or parameters targeting components absent from the resolved closure.

The consumer configuration remains schema version 1. Lock schema version 2 stores a normalized semantic snapshot of that configuration as `intent`:

```json
{
  "recipe": "skill",
  "components": {
    "include": [],
    "exclude": []
  },
  "parameters": {}
}
```

Normalization sorts include/exclude component IDs lexically and recursively sorts object keys inside parameters while preserving array order. The snapshot, rather than mutable ambient configuration, is the authority used by a future `update` operation.

`configuration_sha256` is retained as provenance for the exact bytes of the most recent explicitly supplied configuration. A future update that preserves intent carries that digest forward; an explicit upgrade with a new configuration replaces it.

## Generated materials

A generated material names a bounded declarative `generator` ID; descriptors never contain executable hooks. The initial allowlist contains only `contract-manifest-v1`.

It collects `contract_registrations` from the resolved closure, rejects duplicate identities/paths, sorts by contract ID, and emits deterministic UTF-8 JSON. Unknown generator IDs fail before target writes.

## Initial plan and apply

Initial `plan` is read-only. It computes every copied/generated material byte before classifying the target as `create`, `adopt-identical`, or conflict.

Initial composition never overwrites different existing bytes. Identical unmanaged files may be adopted because the resulting lock can truthfully bind their exact bytes. Portable case collisions, file/directory conflicts, symbolic-link boundaries, unsupported generated-material handlers, dependency conflicts, and existing managed-state metadata fail closed.

Created files are written to a temporary file in the destination directory and installed with a no-overwrite hard-link operation. The lock is written last. If the process stops before that point, the repository remains unmanaged and a later initial apply may adopt only exact previously materialized bytes.

## Lock schema version 2

The canonical lock path remains `.template-composition/lock.json`. Schema version 2 contains no timestamp, random value, branch name, or network-derived value. It binds:

- canonical source repository identity;
- exact nonzero lowercase 40-hex source revision;
- normalized consumer `intent` (`recipe`, include/exclude selection, and parameters);
- SHA-256 of the exact recipe bytes used for resolution (`recipe_sha256`);
- SHA-256 of the exact most recently supplied configuration bytes (`configuration_sha256`);
- lexically ordered resolved component IDs, positive integer versions, and exact descriptor-byte SHA-256 values; and
- lexically ordered materialized destinations, owners, ownership modes, and materialized-byte SHA-256 values.

The former top-level `recipe` field is removed because `intent.recipe` is the canonical consumer selection. Lock schema v1 is intentionally not accepted; this repository is pre-production and no backward-compatibility migration is required.

The recipe digest closes a v1 audit gap: recipe bytes participate in resolution and therefore must be identifiable from the lock just as component descriptor bytes are.

For `seed` materials, the recorded digest identifies the bytes initially supplied by Composition. Consumer-time validation permits later digest drift because content ownership has transferred to the consumer.

## Reserved managed-state metadata

Component material must not claim paths that collide, case-insensitively or structurally, with Composer-owned metadata:

```text
.template-composition/lock.json
.template-composition/transaction.json
.template-composition/staging/**
```

`transaction.json` and `staging/**` are reserved for the managed-state recovery protocol. Reserving them in the lock-v2 contract before update mutation exists prevents a later component from acquiring ambiguous ownership of transaction state.

Other files below `.template-composition/`, including the self-contained validator and schemas materialized by `lifecycle.composition-state`, remain valid component destinations.

## Consumer-time independence

Every artifact requires `lifecycle.composition-state` transitively. It materializes a stdlib-only validator and lock schema under `.template-composition/`.

The consumer validator does not read the source catalog. It checks lock-v2 shape, source identity, normalized selection constraints, portable/symlink boundaries, and current material files:

- `managed` — must exist and match the lock digest;
- `generated` — must exist and match the lock digest;
- `seed` — must exist, but digest drift is allowed after ownership transfer.

If `.template-composition/transaction.json` exists, the repository is explicitly reported as interrupted managed state rather than valid steady state. Recovery is a source-side Composer operation.

Extra consumer-owned files are allowed.

## Update versus upgrade contract

The managed-state operations are intentionally distinct:

- `update` preserves the normalized lock intent and reconciles it against a descendant Composition source revision;
- `upgrade` is the explicit operation for changing intent, recipe selection, component versions, or another declared compatibility boundary.

Composition is not a general-purpose merge engine. The baseline ownership rules are:

- managed -> managed: replace/delete only when current bytes match the old lock digest;
- generated -> generated: regenerate/delete only when current bytes match the old lock digest;
- seed -> seed: preserve current consumer bytes unconditionally;
- new managed/generated/seed: create only at a safe unoccupied destination;
- removed seed: preserve it as a consumer-owned extra file;
- ownership transitions: never inferred by update and require an explicit upgrade rule or a conflict.

A component version change requires `upgrade`. If a component remains at the same positive integer version but its descriptor digest changes, the source has changed a compatibility-bearing descriptor without changing its version. That is a source invariant violation and is rejected by both update and upgrade. Source material bytes may change without a descriptor change; that is the normal managed/generated update case.

## Determinism and execution boundary

For the same immutable source revision, normalized intent, and valid old managed state, reconciliation order, managed/generated output bytes, and the resulting lock are deterministic. Seed contents after ownership transfer are preserved rather than merged.

The Composer does not consult mutable branches, wall-clock time, random values, network-discovered defaults, arbitrary hooks, consumer code, package managers, or product build/test/deploy commands when deriving composition state.

## Managed-state work decomposition

The managed-state implementation is deliberately split into reviewable layers:

1. lock-v2 and update/upgrade contract;
2. read-only update reconciliation planning;
3. safe update mutation plus interrupted-update recovery; and
4. explicit upgrade semantics using the same reconciliation and recovery engine.

At the lock-v2 stage, `plan`/`apply` still refuse an existing lock with `UPDATE_NOT_SUPPORTED`; later stages replace that temporary refusal only for explicit managed-state modes.
