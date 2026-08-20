# Composition source

This orphan branch is the source authority for reusable artifact, capability, and lifecycle components in `TakashiSasaki/templates`.

Consumer repositories are produced from artifact recipes plus explicit consumer intent. The composer resolves a deterministic component closure, materializes source and generated files, writes a lock, and leaves the consumer repository self-contained.

## Use Composition

If you are using Composition to create or maintain a concrete Agent Skill or Web application repository, start with [Using Composition](docs/consumer-guide.md). It provides the task-oriented `initial` / `update` / `upgrade` / recovery workflow, file-editing rules, and conflict handling without requiring the architecture documents.

For exact CLI options, inspect states, plan fields, ownership semantics, and diagnostic codes, use the [Composer reference](docs/reference/composer.md). The architecture documents remain the deeper design and maintainer reference.

## Migration state

PR1 established the composition data model, safe-path/file-ownership rules, resolved-lock contract, and semantic validation boundaries.

PR2 established the first production catalog, migrated Agent Skill semantics into `artifact.skill-core`, and extracted runtime/CLI/MCP/MCP Apps/browser/service behavior into reusable `capability.*` authorities.

PR3 added the Web application artifact and reusable lifecycle chain:

- `artifact.webapp-core` — browser surfaces, canonical routes, visible states, viewports/input capabilities, and Web-specific coverage validation;
- `lifecycle.contract-evolution` — generated closed contract registry, schema binding, version histories, and migrations;
- `lifecycle.implementation-evidence` — artifact-neutral implementation boundaries, proofs, commands, and release gates;
- `lifecycle.release-evidence` — exact-revision execution provenance/results/decision; and
- `lifecycle.release-bundle` — deterministic digest-closed release handoff.

PR4 added the first deterministic composer/resolver MVP and universal consumer composition-state validation. Its public operation model is:

```text
inspect -> plan -> apply -> validate
```

The initial MVP deliberately refused an existing composition lock rather than guessing update behavior.

PR5 established the composition-owned publication boundary: a schema-version-3 documentation catalog, provider-owned guided index, composition glossary, explicit machine-readable assets, and stdlib-only provider-local publication validation.

Site PR #270 completed the publication cutover to the post-composition authority model. The Site now locks one reviewed `composition` revision for Skill/Webapp artifact semantics, reusable capabilities, lifecycle contracts, recipes, schemas, composer documentation, and related publication assets. The legacy `skill` and `webapp` branches are no longer source authorities or Site publication inputs.

The final legacy branch heads retained for historical provenance are:

- `skill`: `b8b735dbe525ca76316fec445cdce43db02a955e`;
- `webapp`: `fa269e1310a37ad46f3644ed4f46954a815380ec`.

The browser-domain contract bytes and their current domain version histories imported from the legacy Webapp source are preserved in Composition. Legacy branch history is not merged into `composition`.

## Generated contract manifest

`contracts/manifest.json` is no longer a monolithic artifact-owned source file. `component.json` may declare `contract_registrations`; `lifecycle.contract-evolution` is the unique owner of the generated manifest destination. The composer renders the manifest deterministically from the resolved registration set through the allowlisted `contract-manifest-v1` generator.

This avoids giving Webapp ownership of lifecycle registrations and allows the same lifecycle components to be selected by the Skill recipe.

## Recipes and consumer state

`recipes/skill.json` selects `artifact.skill-core`. Application capabilities and product lifecycle components are opt-in.

`recipes/webapp.json` selects `artifact.webapp-core`. The artifact requires the complete release lifecycle transitively through `lifecycle.release-bundle`. Runtime/CLI/MCP/MCP Apps/operational Web exposure/headless service capabilities remain optional; a static/CDN Web application therefore does not acquire an application runtime merely because it is browser-facing.

Every artifact requires `lifecycle.composition-state`. It materializes a stdlib-only validator and lock schema under `.template-composition/`. The actual `.template-composition/lock.json` remains reserved composer metadata.

Consumer-time validation requires `managed` and `generated` files to match their lock digests. `seed` files must remain present while they are part of the active composition, but their bytes may change after ownership transfer.

## Lock v2 and managed-state operations

Composition lock schema version 2 stores a normalized consumer-intent snapshot rather than only a digest of the original configuration. The lock records:

- canonical source identity and exact source revision;
- normalized `intent` (`recipe`, include/exclude selection, and parameters);
- `recipe_sha256` for the exact recipe bytes used during resolution;
- `configuration_sha256` for the exact most recently supplied configuration bytes;
- resolved component versions and descriptor digests; and
- materialized file ownership and byte digests.

Lock v1 is intentionally not supported. The repository is pre-production, so the contract is corrected directly instead of carrying a legacy migration path.

Managed state has two distinct forward operations:

- `update` preserves the normalized lock intent while reconciling to the current descendant Composition source revision;
- `upgrade` accepts an explicit new consumer configuration and may change recipe/include/exclude/parameters and component versions.

`update` never accepts a replacement `--config`; changing intent is therefore impossible by accident. A component-version change is an upgrade boundary. A descriptor-byte change without a component-version change is rejected by both operations as a source invariant violation.

Explicit `upgrade` is not a general-purpose migration or merge engine. If the same destination changes component owner or ownership mode, upgrade refuses the transition instead of guessing how to transfer or merge content.

Composer-owned recovery metadata is reserved at `.template-composition/transaction.json` and `.template-composition/staging/**`. Components cannot claim those paths. `transaction.json` is the durable roll-forward marker; `staging/**` remains reserved for future storage strategies.

## Composer

Initial composition remains the default mode:

```sh
python scripts/compose.py inspect --target /path/to/repository
python scripts/compose.py plan --config composition.json --target /path/to/repository
python scripts/compose.py apply --config composition.json --target /path/to/repository
python scripts/compose.py validate --target /path/to/repository
```

The equivalent explicit initial commands are:

```sh
python scripts/compose.py plan --mode initial --config composition.json --target /path/to/repository
python scripts/compose.py apply --mode initial --config composition.json --target /path/to/repository
```

For an existing managed consumer, inspect the full read-only update plan before applying it:

```sh
python scripts/compose.py plan --mode update --target /path/to/repository
python scripts/compose.py apply --mode update --target /path/to/repository
```

For an explicit compatibility-boundary change, supply the new consumer intent to both planning and the start of apply:

```sh
python scripts/compose.py plan --mode upgrade --config composition.json --target /path/to/repository
python scripts/compose.py apply --mode upgrade --config composition.json --target /path/to/repository
```

If an update or upgrade is interrupted after the transaction marker is written, rerun the same `apply --mode ...` operation. Recovery uses the existing transaction and requires the exact source revision recorded by it. Upgrade recovery does not take `--config`; the normalized target intent and new lock are already bound by the transaction.

The source checkout must be clean for tracked files. Every catalog, descriptor, recipe, schema, validator, and copied material actually consumed by composition must be a regular Git-tracked source authority under the exact revision written to the lock.

Initial composition never overwrites different existing bytes. Identical unmanaged files may be adopted. Portable case collisions, file/directory conflicts, symbolic-link boundaries, unsupported generated-material handlers, dependency conflicts, invalid include/exclude selections, and pre-existing composer transaction metadata fail closed.

The initial-composition lock is written last. An interrupted initial apply before that point leaves an unmanaged repository; a later initial apply may adopt only exact previously materialized bytes.

Managed update/upgrade mutation writes a deterministic transaction marker before changing managed state. Every managed/generated replacement or removal is guarded by the old lock digest. Retry accepts only the old state or the already-applied new state; any third byte state stops without being overwritten. The new lock is installed only after file actions, validated while the marker remains, and the marker is removed last.

See [`docs/architecture/composer-mvp.md`](docs/architecture/composer-mvp.md) for the detailed resolver, lock-v2, ownership, reconciliation, and recovery contract.

## Publication boundary

`docs/publication-catalog.json` is the authoritative allowlist for integrated publication. `docs/index.md` is the provider-owned guided-navigation root and `docs/glossary.yml` is the composition terminology authority. Machine-readable descriptors, recipes, schemas, and contract/schema seeds are published only through explicit asset declarations.

Run provider-local validation with:

```sh
python scripts/validate_publication.py
```

Skill and Webapp remain distinct artifact semantics inside the `composition` provider. They are no longer independent canonical template publications. Site may present task-oriented Skill and Webapp groups, but it must lock and attribute their source to the exact reviewed `composition` revision.

See [`docs/publication-catalog.md`](docs/publication-catalog.md) and [`docs/index.md`](docs/index.md).

## Authority boundaries

Artifact semantics and reusable application/lifecycle concerns remain separate. Generic capability/lifecycle descriptors must not depend on artifact authorities. Artifact components may require reusable lifecycle/capability components when those contracts are intrinsic to that artifact recipe.

The production catalog is closed and validated for dependency existence/acyclicity, source inventory, registration ownership, deterministic generated material input, portable destination ownership, and materialized Skill/Webapp validation.

### Policy coexistence

Coding-agent operating policy is a separate `policy` authority. Composition does not interpret Policy profiles, `.agent-policy.yml`, `.agent-policy.lock`, or `.agent-policy/**`, and Composer never invokes the `agent-policy` CLI. Policy adoption is therefore not represented by `capability.agent-policy` or any other production Composition component.

The Policy-owned paths `.agent-policy.yml`, `.agent-policy.lock`, and `.agent-policy/**` are foreign reserved destinations for Composition. Component descriptors, resolved locks, managed transactions, and the self-contained consumer validator reject attempts to claim them. Existing Policy metadata that is unrelated to a Composition material destination is left unchanged by initial, update, upgrade, validation, and recovery behavior.

Ordinary repository paths are not made globally exclusive by this rule. In particular, the Skill artifact materializes `AGENTS.md` as `seed`; after initial materialization it is consumer-owned and Composition update/upgrade preserves later consumer or Policy-adoption edits. Conversely, if a Policy-managed repository already contains a different `AGENTS.md`, Composition initial fails closed rather than inferring a reverse ownership transfer.

The canonical cross-authority rules are maintained by Site in the [Policy–Composition coexistence contract](https://templates.moukaeritai.work/coexistence/). This branch defines only Composition's provider-local enforcement and does not duplicate Policy semantics or create a shared lock, transaction, or management plane.

## Managed-state safety rules

Composition is not a general-purpose merge engine.

- `managed` / `generated` may be replaced or removed only when current bytes match the old lock digest.
- `seed` becomes consumer-owned after first materialization and is never overwritten by update or upgrade.
- a newly selected seed may be created only when its destination is absent and safe; after creation it becomes consumer-owned.
- removed seed files remain as consumer-owned extra files and disappear from the new lock.
- generated output is recomputed deterministically from the resolved composition.
- file-owner and ownership-mode transitions are never inferred, including during explicit upgrade.
- component version changes require explicit upgrade.
- descriptor-byte changes without a component-version change are rejected as a source invariant violation.
- every update/upgrade has a complete read-only plan before filesystem mutation.
- interrupted managed-state mutation is recovered by deterministic roll-forward without discarding unexpected consumer changes.

See:

- [`docs/index.md`](docs/index.md)
- [`docs/publication-catalog.md`](docs/publication-catalog.md)
- [`docs/architecture/composition-model.md`](docs/architecture/composition-model.md)
- [`docs/architecture/catalog.md`](docs/architecture/catalog.md)
- [`docs/architecture/generated-contract-manifest.md`](docs/architecture/generated-contract-manifest.md)
- [`docs/architecture/composer-mvp.md`](docs/architecture/composer-mvp.md)
- [`docs/migrations/pr2-skill-capabilities.md`](docs/migrations/pr2-skill-capabilities.md)
- [`docs/migrations/pr3-webapp-lifecycle.md`](docs/migrations/pr3-webapp-lifecycle.md)
- [`catalog/README.md`](catalog/README.md)
