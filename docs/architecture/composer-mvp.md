# Composer MVP

## Scope

PR4 implements the first deterministic source-time composer for the production component catalog.

The public lifecycle is:

```text
inspect -> plan -> apply -> validate
```

`update` is deliberately not implemented. A target containing `.template-composition/lock.json` is already managed and `plan` / `apply` fail with `UPDATE_NOT_SUPPORTED` rather than guessing merge behavior.

## Source authority

The composer runs from a clean `composition` source checkout. It binds every successful plan/apply to the exact full Git commit returned by `git rev-parse HEAD` and refuses tracked source modifications.

The production catalog is loaded closed: catalog IDs must exactly match `components/` and `recipes/`, descriptors/recipes must validate against their schemas, dependencies must exist and be acyclic, and generic capability/lifecycle components must not depend on artifact authorities.

## Resolution

For schema version 1, one production recipe determines the artifact and selectable component surface.

Resolution starts from:

```text
artifact
+ recipe.required_components
+ recipe.default_components not explicitly excluded
+ configuration.components.include
```

Then all `requires` dependencies are added transitively.

The resolver fails closed when:

- include/exclude overlap;
- an included or excluded component is not exposed by the recipe;
- a recipe-required component is excluded;
- an excluded component reappears as a transitive dependency;
- the resolved closure contains a declared conflict; or
- a parameter namespace names a component absent from the resolved closure.

Parameters remain opaque component-scoped intent in this MVP. No current material generator consumes a parameter value. The exact configuration bytes are nevertheless bound by SHA-256 in the lock, so later parameter semantics cannot silently reinterpret an older lock without a versioned contract change.

## Generated materials

A generated material names a bounded declarative `generator` ID; descriptors never contain executable hooks.

The initial allowlist contains only:

```text
contract-manifest-v1
```

It collects `contract_registrations` from the resolved closure, rejects duplicate identities/paths, sorts by contract ID, and emits deterministic UTF-8 JSON.

Unknown generator IDs fail before target writes.

## Plan

`plan` is read-only. It computes every copied/generated material byte before classifying the target.

Each destination is classified as:

- `create` — destination is absent and safe;
- `adopt-identical` — an unmanaged existing regular file has exactly the planned bytes; or
- conflict — any unsafe or ambiguous condition.

Conflicts include:

- different existing bytes;
- symbolic links;
- file/directory prefix collisions;
- portable case-insensitive collisions;
- a target root that is a symbolic link; and
- an existing composition lock.

An identical unmanaged file may be adopted because the resulting lock can truthfully bind its exact bytes. Different existing files are never overwritten during initial composition.

## Apply and crash boundary

`apply` recomputes the plan. All ordinary conflicts are detected before writes.

Created files are written to a temporary file in the destination directory and installed with a no-overwrite hard-link operation. If another actor creates the destination after planning, apply fails rather than replacing it.

Directories may be created incrementally. The operation is therefore not described as a full filesystem transaction.

The lock is written **last**. If the process stops before that point, the repository remains unmanaged. A later run may adopt any already-created files only when their bytes exactly match the new plan; partial or different bytes become conflicts.

## Lock

The schema-version-1 lock contains no timestamp or random value. It binds:

- canonical source repository identity;
- exact nonzero 40-hex source revision;
- selected recipe;
- SHA-256 of the exact configuration file bytes;
- lexically ordered resolved component IDs, versions, and exact descriptor-byte SHA-256 values; and
- lexically ordered materialized destinations, owners, ownership modes, and exact materialized-byte SHA-256 values.

The lock is composer metadata and is excluded from its own file inventory.

## Consumer-time independence

Every artifact requires `lifecycle.composition-state` transitively. It materializes a stdlib-only validator and the lock schema under `.template-composition/`.

The consumer validator does not read the source catalog. It checks the recorded resolved state, portable/symlink boundaries, and current material files:

- `managed` — must exist and still match the lock digest;
- `generated` — must exist and still match the lock digest;
- `seed` — must exist, but digest drift is allowed after ownership transfer.

Extra consumer-owned files are allowed.

The source-side `inspect` / `validate` commands must not execute untrusted code from the consumer repository. They use source-authoritative validation logic to inspect target bytes. Direct invocation of the materialized validator is the consumer-side self-contained path.

## Deferred update semantics

A later update PR must separately define at least:

- source-revision change rules;
- component add/remove resolution;
- managed/generated replacement only when current bytes match the old lock;
- seed preservation;
- removed managed-file handling;
- generated-file regeneration;
- source/config/descriptor reconciliation; and
- recovery when an update is interrupted.

None of those behaviors are inferred by the MVP.
