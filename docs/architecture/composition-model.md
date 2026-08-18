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
- materialized destinations with an ownership mode.

`managed` and `seed` materials also declare a source path. `generated` materials deliberately have no source path because their bytes are derived from the resolved composition.

A material source path is relative to that component's source root. A destination path is relative to the consumer repository root in schema version 1.

The descriptor does not contain executable install, update, or post-install hooks.

Dependencies and conflicts operate on component identities, not filenames. Artifact components may select or constrain reusable capability/lifecycle components. In the opposite direction, `capability.*` and `lifecycle.*` descriptors must not require or conflict with `artifact.*` IDs; a supposedly generic component that names a concrete artifact authority belongs in the artifact layer instead.

Catalog-level validation must eventually reject:

- missing dependencies;
- dependency cycles;
- self-dependencies;
- a component that both requires and conflicts with the same component;
- duplicate component IDs;
- generic capability/lifecycle descriptors that depend on or conflict with artifact components; and
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

The artifact component is selected only by the recipe in schema version 1. Consumer include/exclude declarations cannot substitute a different `artifact.*` component.

Detailed resolver semantics for required/default/optional membership are intentionally deferred until the component catalog and resolver exist. At minimum, the future resolver must reject any attempt to exclude a recipe-required component or a transitive dependency.

## Consumer composition intent

A consumer configuration records user intent separately from resolution.

It declares:

- one recipe ID;
- capability or lifecycle components explicitly included;
- capability or lifecycle components explicitly excluded; and
- optional component-scoped parameters.

The include and exclude sets must be disjoint.

The configuration does not enumerate the final dependency closure and cannot replace the recipe's artifact component. Dependency closure belongs to the lock.

A parameter key names the component whose parameter namespace it targets. Schema validation checks the component-ID shape only; the future resolver must reject parameters for components that are not present in the resolved selection.

PR1 defines the data model but does not commit to a particular YAML or JSON CLI serialization. JSON examples are used because JSON is directly schema-validatable and can represent the same data model.

Schema version 1 models one artifact recipe materialized at the consumer repository root. Nested multiple artifact instances may be added later, but PR1 does not encode that future feature.

## Resolved composition lock

A lock records the deterministic result of resolution.

It binds the result to:

- source repository `TakashiSasaki/templates`;
- a lowercase full 40-hex Git commit revision;
- the selected recipe;
- the SHA-256 of the exact validated consumer-configuration file bytes;
- the resolved component set, containing exactly one `artifact.*` entry and serialized in ascending lexical order by component ID, with exact component versions and descriptor-byte digests; and
- the non-empty materialized file inventory, serialized in ascending lexical order by destination, with ownership modes and materialized byte digests.

Every resolved component owns at least one entry in the final lock file inventory. This follows the schema-version-1 component contract, in which every component descriptor declares at least one material. A future schema version may relax both sides together if metadata-only components become necessary.

The configuration digest is intentionally a byte-identity binding in schema version 1. A semantically equivalent rewrite with different bytes has a different digest. Any later move to semantic canonicalization requires an explicit versioned contract change.

A lock contains no generation timestamp or other intentionally nondeterministic field.

The canonical schema-version-1 lock path is `.template-composition/lock.json`. The lock itself is composer metadata, not component material, and is excluded from its own `files` inventory. Component descriptors and lock file inventories must not claim that reserved destination, any case variant of it, any parent path that would have to be a file, or any descendant that would require `lock.json` itself to be a directory. Other files below `.template-composition/`, such as a generated `registry.json`, remain available to components; the directory as a whole is not reserved.

A future catalog/resolver validator must also prove that the lock's recipe exists, that its required artifact is the lock's single resolved artifact, that required/default/explicit selections and dependency closure are satisfied, that every recorded component version/digest corresponds to the immutable source revision, and that every lock file destination/ownership pair agrees with the authoritative material declaration in its owning component descriptor. Those cross-document checks are intentionally not fabricated in PR1 because no production catalog or resolver exists yet.

A future composer must fail closed when the lock is malformed, uses the all-zero Git object ID, references an unsupported source identity, or cannot be reconciled with the consumer repository.

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

The bytes are derived deterministically from the resolved composition and therefore have a destination but no source file in the component descriptor.

Typical examples are aggregate registries or other closed inventories assembled from selected component metadata.

Generated bytes may be recreated by the composer when the existing generated file has not been locally modified.

## Destination ownership invariant

A materialized destination path has at most one component owner.

Composition is not a general-purpose text merge engine. Two components must not append to, patch, or partially own the same file.

When information from multiple components must be aggregated, each component supplies separate authoritative metadata and one designated component owns the resulting `generated` destination.

Destination comparison is portable rather than native-filesystem-specific. ASCII case variants such as `README.md` and `readme.md` are considered the same destination, and a file path cannot simultaneously be a parent path of another materialized file such as `contracts` and `contracts/mcp.json`. These rules prevent compositions that work on one filesystem but collide on a case-insensitive or ordinary hierarchical consumer filesystem.

This rule avoids order-dependent file patches and makes composition results auditable.

## Safe paths

Component source and destination paths are relative POSIX-style paths.

The schema rejects:

- absolute paths;
- Windows drive-prefixed paths;
- `.` and `..` path segments;
- repeated or trailing separators;
- backslashes;
- path segments beginning with `-`; and
- `.git` administration path segments in any ASCII case variant.

The Windows-drive lookahead is intentionally redundant with the portable character allowlist. Keeping the explicit check documents the cross-platform threat being rejected even if the allowlist is later broadened.

The current schema intentionally restricts component-controlled materialization paths to a portable ASCII path subset. Case-insensitive destination collision checks and case-folded Git-administration checks are additionally enforced by semantic validation. This restriction can be broadened later only with equivalent cross-platform safety guarantees.

## Determinism

The target composer must satisfy:

```text
(source revision, validated configuration bytes) -> resolved composition
(resolved composition, component bytes)          -> materialized managed/generated bytes
```

For the same immutable source revision and the same validated configuration bytes, resolution order, component metadata, and managed/generated output bytes must be stable.

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

Positive examples under `examples/` are executable schema fixtures only. They are not production catalog entries and do not assert that the named components already exist.

Repository tests also enforce cross-field invariants that JSON Schema does not express conveniently, including pairwise-disjoint selections, generic/artifact dependency boundaries, exactly one resolved artifact, lexically ordered/unique resolved component IDs, resolved-component material coverage, portable collision-free destination ownership, reserved lock-path exclusion, and lock references to resolved component owners.

The semantic checks in PR1 are an executable specification for the future materialized validator. Consumer-time independence requires that those checks, or an equivalent generated validation contract, be available inside the consumer repository; validating the JSON Schema alone is not sufficient for all composition invariants.

## Explicit PR1 non-goals

PR1 does not:

- migrate a file from `webapp` or `skill`;
- define completed `artifact.webapp-core` or `artifact.skill-core` components;
- define production Webapp or Skill recipes;
- implement dependency resolution;
- implement file materialization;
- implement update or conflict handling;
- generate consumer registries;
- validate recipe/component closure against a production catalog that does not yet exist;
- change Site publication catalogs or navigation;
- adopt composition into consumer repositories; or
- retire any legacy branch.

Those changes require later independently reviewable pull requests.
