# Composition model

## Decision

The `composition` branch is the future single source authority for reusable application-template material that is currently split between the unrelated `webapp` and `skill` histories.

This branch does not make Web applications and Agent Skills the same artifact. It separates three concerns:

1. **artifact semantics** — what kind of artifact is being developed, such as a Web application or Agent Skill;
2. **capabilities** — reusable optional behavior such as runtime, CLI, MCP, MCP Apps, browser exposure, or a headless service; and
3. **lifecycle contracts** — reusable contract-evolution, implementation-evidence, release-evidence, and release-bundle behavior.

`webapp` and `skill` therefore become recipes over one component catalog rather than independent monolithic downstream templates.

PR1 establishes this model and the machine-readable schemas only. Physical migration of legacy content is deliberately later work.

## Replacement for direct copyability

The retired architectural target is:

```text
monolithic template/
        |
        | byte-for-byte copy
        v
consumer repository
```

The replacement target is:

```text
recipe + consumer intent + immutable source revision
                    |
                    | resolve
                    v
             component closure
                    |
                    | materialize
                    v
          consumer repository + lock
```

The important invariant retained from the old copyable model is not that a source subtree itself is directly copyable. The retained invariant is:

> After materialization, the consumer repository is self-contained and can be validated without access to the composition source checkout.

This is **source-time composition, consumer-time independence**.

## Authority classes

Component IDs have exactly one of three prefixes:

- `artifact.*` — artifact-specific semantics;
- `capability.*` — reusable application capabilities; or
- `lifecycle.*` — reusable product-lifecycle contracts.

The prefix must agree with the component descriptor's `kind`.

Initial intended authorities are:

```text
artifact.webapp-core
artifact.skill-core

capability.runtime
capability.cli
capability.mcp
capability.mcp-apps
capability.web-interface
capability.service

lifecycle.contract-evolution
lifecycle.implementation-evidence
lifecycle.release-evidence
lifecycle.release-bundle
```

These names are architectural targets, not a declaration that PR1 already contains those component implementations.

## Component descriptor

A component descriptor declares:

- stable component `id`;
- component `kind`;
- integer component `version`;
- human-readable summary;
- required component IDs;
- conflicting component IDs; and
- materialized files with source, destination, and ownership mode.

The descriptor does not contain executable install, update, or post-install hooks.

Dependencies and conflicts operate on component identities, not filenames.

Catalog-level validation must eventually reject:

- missing dependencies;
- dependency cycles;
- self-dependencies;
- a component that both requires and conflicts with the same component;
- duplicate component IDs; and
- incompatible selected components.

PR1 validates the descriptor shape and the cross-field invariants that can be established without a populated component catalog.

## Recipe

A recipe is a consumer-facing starting selection, not an implementation authority.

A recipe declares:

- one required artifact component;
- additional required capability or lifecycle components;
- default capability or lifecycle components; and
- optional capability or lifecycle components.

A recipe never owns copies of generic capability or lifecycle contracts. Both `webapp` and `skill` recipes may select the same `capability.mcp` authority.

The required, default, and optional component sets must be pairwise disjoint.

## Consumer composition intent

A consumer configuration records user intent separately from resolution.

It declares:

- one recipe ID;
- components explicitly included;
- components explicitly excluded; and
- optional component-scoped parameters.

The include and exclude sets must be disjoint.

The configuration does not enumerate the final dependency closure. That is the lock's responsibility.

PR1 defines the data model but does not commit to a particular YAML or JSON CLI serialization. JSON examples are used because JSON is directly schema-validatable and can represent the same data model.

## Resolved composition lock

A lock records the deterministic result of resolution.

It binds the result to:

- the exact source repository;
- a lowercase full 40-hex Git commit revision;
- the selected recipe;
- the SHA-256 of the consumer configuration;
- the resolved ordered component set, including descriptor digests; and
- the materialized file inventory, ownership modes, and materialized byte digests.

A lock contains no generation timestamp or other intentionally nondeterministic field.

The lock itself is generated state and is excluded from its own file-digest inventory.

A future composer must fail closed when the lock is malformed, references an unsupported source identity, or cannot be reconciled with the consumer repository.

## File ownership

Every materialized file has exactly one ownership mode.

### `managed`

The composition source remains authoritative for the materialized bytes.

Typical examples are reusable schemas and validators.

A future update may replace the file only when its current bytes still match the digest recorded by the existing lock. Local modification must cause a refusal rather than a silent overwrite.

### `seed`

The composer supplies initial bytes once and then transfers content ownership to the consumer.

Typical examples are product-specific contract instances that the consumer is expected to edit.

A future update must not overwrite an existing seeded destination merely because the source seed changed.

### `generated`

The bytes are derived deterministically from the resolved composition.

Typical examples are aggregate registries or other closed inventories assembled from selected component metadata.

Generated bytes may be recreated by the composer when the existing generated file has not been locally modified.

## Destination ownership invariant

A materialized destination path has at most one component owner.

Composition is not a general-purpose text merge engine. Two components must not append to, patch, or partially own the same file.

When information from multiple components must be aggregated, each component supplies separate authoritative metadata and the composer creates one `generated` aggregate owned by a single designated generating authority.

This rule avoids order-dependent file patches and makes composition results auditable.

## Safe paths

Component source and destination paths are relative POSIX-style paths.

The schema rejects:

- absolute paths;
- Windows drive-prefixed paths;
- `.` and `..` path segments;
- repeated separators;
- backslashes; and
- `.git` administration paths.

The current schema intentionally restricts component-controlled materialization paths to a portable ASCII path subset. This restriction can be broadened later only with equivalent cross-platform safety guarantees.

## Determinism

The target composer must satisfy:

```text
(source revision, validated configuration) -> resolved composition
(resolved composition, component bytes)    -> materialized managed/generated bytes
```

For the same immutable source revision and the same configuration, resolution order, component metadata, and managed/generated output bytes must be stable.

A composer must not consult mutable branches, ambient repository state, wall-clock time, random values, network-discovered defaults, or arbitrary executable hooks when deriving those bytes.

Consumer-owned `seed` files are intentionally outside byte-for-byte update determinism after ownership transfer.

## Security and execution boundary

Composition is declarative.

Component descriptors must not define arbitrary shell commands, executables, package-manager commands, or lifecycle hooks.

The future composer may:

1. inspect repository state;
2. validate configuration;
3. resolve dependencies and conflicts;
4. construct a plan;
5. materialize declared source bytes;
6. create deterministic generated files;
7. write the lock; and
8. run bounded composition-structure validation.

Product build, test, deployment, migration, runtime, or package-install commands remain consumer responsibilities unless a later reviewed contract introduces a narrowly specified mechanism.

## Planned operation model

The intended public lifecycle is:

```text
inspect -> plan -> apply -> validate
```

An eventual `update` operation is expected but is not part of PR1 or the initial composer MVP.

New and existing repositories use the same state inspection model rather than separate copy/install mechanisms.

## Branch topology

The intended end state is:

```text
site          integrated documentation and GitHub Pages deployment
policy        application-type-independent agent/repository policy
composition   artifact recipes, shared components, lifecycle contracts, composer
```

The existing `webapp` and `skill` branches remain authoritative during the migration. They are not modified by PR1.

After their content has been migrated, validated through composition fixtures, published from an immutable `composition` revision, and cut over in `site`, they can be retired as source authorities.

Source unification does not collapse the public documentation taxonomy. Site may continue to expose separate Web application and Skill sections while also exposing shared capabilities and lifecycle documentation.

## PR1 schemas

PR1 defines four JSON Schema Draft 2020-12 contracts:

- `schemas/component.schema.json`;
- `schemas/recipe.schema.json`;
- `schemas/composition-config.schema.json`; and
- `schemas/composition-lock.schema.json`.

Positive examples under `examples/` are executable schema fixtures.

Repository tests also enforce cross-field invariants that JSON Schema does not express conveniently, including pairwise-disjoint selections, unique destination ownership, and lock references to resolved component owners.

## Explicit PR1 non-goals

PR1 does not:

- migrate a file from `webapp` or `skill`;
- define completed `artifact.webapp-core` or `artifact.skill-core` components;
- define production Webapp or Skill recipes;
- implement dependency resolution;
- implement file materialization;
- implement update or conflict handling;
- generate consumer registries;
- change Site publication catalogs or navigation;
- adopt composition into consumer repositories; or
- retire any legacy branch.

Those changes require later independently reviewable pull requests.
