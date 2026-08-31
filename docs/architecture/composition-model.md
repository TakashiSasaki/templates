# Composition model

## Decision

The `composition` branch is the canonical source authority for reusable artifact semantics, application capabilities, lifecycle contracts, recipes, schemas, and the deterministic Composer.

Composition separates four component roles:

1. **foundations** — shared mandatory baseline semantics introduced transitively by an artifact;
2. **artifact semantics** — what is being built, such as a Website, Web application, or Agent Skill;
3. **capabilities** — reusable optional behavior such as runtime, CLI, MCP, MCP Apps, browser exposure, or a headless service; and
4. **lifecycle contracts** — reusable machinery for composition state, contract evolution, implementation evidence, release evidence, and release-bundle behavior.

Web applications and Agent Skills remain distinct artifacts. They share reusable authorities through recipes over one component catalog rather than through duplicated monolithic templates.

The legacy `skill` and `webapp` source-authority migration is complete. Managed-state update/upgrade is an independent Composer lifecycle concern.

## Source-time composition, consumer-time independence

The materialization model is:

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

The core invariant is:

> After successful materialization, the consumer repository is self-contained and can validate its steady composition state without access to the Composition source checkout.

Source-side Composer operations are required only when deriving a new state (`initial`, `update`, or `upgrade`) or recovering an interrupted managed-state transaction.

## Authority classes

Component IDs have exactly one component-role prefix:

- `foundation.*` — shared mandatory baseline semantics;
- `artifact.*` — artifact-specific semantics;
- `capability.*` — reusable optional capabilities; or
- `lifecycle.*` — reusable product-lifecycle machinery.

The prefix must agree with descriptor `component_role`. A foundation is introduced only through an artifact dependency; it is not recipe-selectable. Non-artifact descriptors must not require or conflict with concrete `artifact.*` authorities. Artifact components may require foundations, reusable capabilities, or lifecycle components when those contracts are intrinsic to the artifact.

The production catalog is closed. Catalog validation requires component and recipe inventories to match the source tree, dependencies to exist and be acyclic, identities to be unique, generic/artifact boundaries to hold, and selected conflicts to be rejected.

## Component descriptor

A component descriptor declares:

- stable component `id`;
- component `component_role`;
- positive integer component `version`;
- human-readable summary;
- required component IDs;
- conflicting component IDs;
- materialized destinations with ownership modes; and
- optional declarative registrations used by bounded generated-material handlers.

`managed` and `seed` materials declare a source path. `generated` materials have no source path because their bytes are derived deterministically from resolved component metadata.

Descriptors do not contain arbitrary executable install/update/post-install hooks.

The integer component version is an explicit compatibility boundary, not SemVer. A managed `update` may not cross a version change. Explicit `upgrade` may cross a component-version change. If descriptor bytes change while the component version remains unchanged, Composer rejects the source transition as an invariant violation rather than pretending compatibility information is unchanged.

## Recipe and consumer intent

A recipe is a consumer-facing starting selection, not an implementation authority. It declares:

- one artifact component;
- required reusable components;
- default reusable components; and
- optional reusable components.

Required/default/optional sets are pairwise disjoint.

Consumer configuration records unresolved intent separately from the resolved lock:

- recipe ID;
- explicitly included capability/lifecycle IDs;
- explicitly excluded capability/lifecycle IDs; and
- optional component-scoped parameters.

Include/exclude sets are disjoint. Consumers cannot replace the recipe artifact through include/exclude. The resolver rejects exclusions of recipe-required or transitive dependencies and rejects parameters for components absent from the resolved closure.

The normalized intent snapshot stored in lock v2 sorts include/exclude IDs lexically and recursively sorts object keys inside parameters while preserving array order.

## Deterministic resolution

For a validated configuration, the resolver begins with:

```text
recipe artifact
+ recipe required components
+ recipe default components not explicitly excluded
+ explicit includes
```

It then computes the complete transitive `requires` closure and validates exclusions/conflicts.

Generated material uses only bounded allowlisted generator IDs. The current `contract-manifest-v1` generator aggregates declarative contract registrations from the resolved closure and emits deterministic JSON. Component descriptors never provide executable generator code.

The Composer does not consult mutable branches, wall-clock time, random values, network-discovered defaults, arbitrary hooks, consumer code, package managers, or product build/test/deploy commands when deriving Composition state.

## Lock schema version 2

The canonical steady-state metadata path is:

```text
.template-composition/lock.json
```

Lock schema version 2 records:

- canonical source repository identity;
- exact nonzero lowercase 40-hex source commit revision;
- normalized consumer `intent`;
- `recipe_sha256`, binding the exact recipe bytes used for resolution;
- `configuration_sha256`, binding the exact bytes of the most recently explicitly supplied consumer configuration;
- lexically ordered resolved components with positive integer versions and descriptor SHA-256 digests; and
- lexically ordered materialized destinations with owner, ownership mode, and materialized SHA-256 digest.

Lock v1 is intentionally unsupported. The repository is pre-production, so the contract was corrected directly instead of retaining a legacy migration path.

`configuration_sha256` is provenance, while `intent` is the semantic authority needed to reproduce update intent. `update` therefore does not need the original configuration file. `upgrade` consumes a new explicit configuration and replaces both normalized intent and configuration-byte provenance.

The lock contains no timestamp, random value, branch name, or other intentionally nondeterministic state.

## File ownership

Each materialized destination has one component owner and one ownership mode.

### `managed`

Composition remains authoritative for the bytes.

Update/upgrade may replace or remove a managed file only when its current bytes match the old lock digest. A local modification is a conflict and is never overwritten silently.

### `generated`

Bytes are recomputed deterministically from the target resolved composition.

Generated files use the same local-modification guard as managed files: regenerate or remove only when current bytes still match the old lock digest.

### `seed`

Composition supplies bytes only for first materialization of that destination, then content ownership transfers to the consumer.

For a seed already present in the old lock, update/upgrade always preserves current consumer bytes. Source-side seed changes do not overwrite them. The old seed provenance digest is carried into a new lock while the seed remains selected.

A newly selected seed may be created only when its destination is absent and safe. After that create succeeds it is consumer-owned.

A removed seed is never deleted. It disappears from the new lock and remains as an ordinary consumer-owned extra file.

## Destination and ownership invariants

A materialized destination has at most one component owner. Composition does not patch, append to, partially own, or merge a file shared by multiple components.

Portable destination comparison rejects:

- ASCII case collisions such as `README.md` versus `readme.md`;
- file/directory prefix collisions such as `contracts` versus `contracts/mcp.json`;
- absolute or drive-prefixed paths;
- `.` / `..` segments;
- repeated/trailing separators or backslashes;
- segments beginning with `-`; and
- `.git` administration segments in any ASCII case variant.

At an existing destination, a component-owner change or ownership-mode change is not automatically inferred. `update` reports it as upgrade-required; explicit `upgrade` still refuses automatic owner/ownership migration because the configuration does not specify a safe content-transfer policy.

Aggregation across components is implemented by separate declarative metadata plus one designated owner of a deterministic `generated` destination.

## Policy coexistence boundary

Policy is an independent coding-agent operating authority, not a Composition capability. Composition components and recipes therefore do not represent Policy adoption, and Composer does not invoke `agent-policy` or interpret Policy profiles, configuration, lock, runtime, or release state.

Composition enforces only the cross-authority ownership boundary needed to avoid mutation collisions. The following paths are foreign reserved destinations:

```text
.agent-policy.yml
.agent-policy.lock
.agent-policy/**
```

Component descriptors, resolved lock inventories, managed transaction actions, and self-contained consumer validation reject claims on those paths, including portable case variants. This does not make every ordinary repository instruction path Policy-owned. The Skill artifact's `AGENTS.md` remains a Composition `seed`; after initial materialization it is consumer-owned and later Policy adoption may replace its contents without Composition update/upgrade overwriting those bytes.

The reverse transition is intentionally not inferred. If a repository already contains a different Policy-generated `AGENTS.md` before Skill initial composition, the existing destination conflict is preserved and initial composition fails closed until an explicit migration contract exists.

The canonical cross-authority contract is Site-owned and published as the [Policy–Composition coexistence contract](https://templates.moukaeritai.work/coexistence/). Composition's local model records only the invariants it enforces; it does not duplicate Policy semantics or introduce a shared lock, transaction, or umbrella management layer.

## Public operation model

The public lifecycle is:

```text
inspect -> plan -> apply -> validate
```

Managed-state intent is explicit through operation modes:

```text
plan/apply --mode initial
plan/apply --mode update
plan/apply --mode upgrade
```

Omitting `--mode` is equivalent to `initial` for compatibility with the initial Composer CLI.

### Initial

Initial composition consumes an explicit configuration and requires no existing lock. It never overwrites different unmanaged bytes. Identical unmanaged material may be adopted. The lock is written last, making lock creation the transition from unmanaged to managed state.

### Update

`update` preserves `lock.intent` and reconciles it against the current descendant Composition source revision. It rejects a new `--config`.

Component version changes are reported as `COMPONENT_VERSION_UPGRADE_REQUIRED`. Same-version descriptor drift is rejected as a source invariant violation.

### Upgrade

`upgrade` requires an explicit new configuration for a new operation. It may change recipe/include/exclude/parameters and may cross component-version boundaries.

It does not weaken ownership protections: managed/generated local changes still conflict, seed contents remain consumer-owned, and owner/ownership transitions remain unsupported automatic migrations.

Both update and upgrade require the old source revision to exist in the local source history and be an ancestor of, or identical to, the target source revision. Downgrade or unrelated-history reconciliation fails closed.

## Read-only reconciliation

Every update/upgrade builds the complete plan before filesystem mutation.

The plan classifies components as:

```text
added / removed / changed / unchanged
```

and files as:

```text
create / replace / remove / preserve / unchanged / conflict
```

A managed/generated replacement or removal is planned only after current bytes match the old lock digest. A new destination must be empty and structurally safe. A missing old locked material is invalid old state rather than implicit deletion.

The plan includes a deterministic new-lock preview and an explicit conflict list. `plan` is read-only.

For the same immutable source revision, selected intent, and valid old managed state, plan ordering, generated bytes, and lock preview are deterministic.

## Managed-state transaction and recovery

Initial apply can use "lock last" because no old managed state exists. Update/upgrade need a stronger protocol because an old lock already describes the repository.

Composer reserves:

```text
.template-composition/transaction.json
.template-composition/staging/**
```

Components cannot claim these paths. `transaction.json` is the implemented durable marker; `staging/**` remains reserved for possible future storage strategies.

Before the first managed-state file mutation, apply writes a deterministic transaction marker containing:

- operation (`update` or `upgrade`);
- exact target source revision;
- embedded old and new lock objects;
- exact old/new lock-file identities; and
- ordered create/replace/remove actions with digest preconditions.

Mutation follows a deterministic roll-forward state machine:

- create: destination must be absent, or already match the recorded new digest during recovery;
- replace: destination must match the recorded old digest, or already match the recorded new digest;
- remove: destination must match the recorded old digest, or already be absent;
- any third state, symlink, unsafe parent, or non-regular-file state stops without overwriting it.

The new lock is installed only after material actions. New-state validation runs while the transaction marker still exists. The marker is deleted last.

If interrupted, rerunning the matching `apply --mode ...` loads the existing marker instead of planning a different operation. Recovery requires the exact source revision recorded in the transaction and reconstructs deterministic target bytes before continuing.

Upgrade recovery uses the transaction-bound target intent; it does not accept a second `--config`.

This is roll-forward, not rollback. The protocol never needs to restore consumer-owned seed bytes and never guesses how to merge an unexpected local edit.

## Consumer-time validation

`lifecycle.composition-state` materializes a stdlib-only validator and lock schema into the consumer repository.

In steady state the validator checks lock-v2 shape, canonical source identity, deterministic ordering/portable path invariants, and current materials:

- managed/generated files must exist and match lock digests;
- active seed files must exist but may differ from their recorded initial provenance digest; and
- lock inventory must not claim foreign Policy-owned metadata destinations.

If `transaction.json` exists, steady-state validation refuses the repository as interrupted managed state and requires source-side recovery.

Extra consumer-owned files are allowed, including seeds removed from the active composition and independent Policy metadata not listed in the Composition lock.

## Security and execution boundary

Composition remains declarative. It does not execute consumer code or arbitrary component hooks.

The Composer may:

1. inspect repository/composition state;
2. validate configuration and managed metadata;
3. resolve dependencies/conflicts;
4. build a read-only reconciliation plan;
5. materialize declared source bytes;
6. create deterministic generated files;
7. perform digest-guarded filesystem mutation;
8. write lock/transaction metadata; and
9. run bounded composition-structure validation.

Product build, test, deployment, application migration, runtime, package-install, and coding-agent Policy commands remain outside the Composer contract.

## Branch topology

The canonical authority topology is:

```text
site          integrated reader-facing publication, assembly, Pages/PWA
policy        coding-agent policy authority
composition   artifact/capability/lifecycle authorities, recipes, schemas, Composer
```

Legacy `skill` / `webapp` authority migration and retirement are complete. Their history is provenance, not an active Composition update source.

Source unification does not collapse reader-facing taxonomy. Site may continue to expose distinct Web application and Skill task-oriented views while attributing them to one immutable reviewed `composition` revision.
