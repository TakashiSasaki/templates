# Composition source

This orphan branch is the source authority for reusable artifact, capability, and lifecycle components in `TakashiSasaki/templates`.

Consumer repositories are produced from artifact recipes plus explicit consumer intent. The composer resolves a deterministic component closure, materializes source and generated files, writes a lock, and leaves the consumer repository self-contained.

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

`update` is deliberately not implemented in the MVP. A repository containing an existing composition lock is treated as managed state and update is refused rather than inferred.

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

Consumer-time validation requires `managed` and `generated` files to match their lock digests. `seed` files must remain present but may change after ownership transfer.

## Composer MVP

Run the source-side composer with:

```sh
python scripts/compose.py inspect --target /path/to/repository
python scripts/compose.py plan --config composition.json --target /path/to/repository
python scripts/compose.py apply --config composition.json --target /path/to/repository
python scripts/compose.py validate --target /path/to/repository
```

The source checkout must be clean for tracked files. Every catalog, descriptor, recipe, schema, validator, and copied material actually consumed by composition must be a regular Git-tracked source authority under the exact revision written to the lock.

Initial composition never overwrites different existing bytes. Identical unmanaged files may be adopted. Portable case collisions, file/directory conflicts, symbolic-link boundaries, unsupported generated-material handlers, dependency conflicts, and invalid include/exclude selections fail closed.

The lock is written last. An interrupted initial apply before that point leaves an unmanaged repository; a later apply may adopt only exact previously materialized bytes.

See [`docs/architecture/composer-mvp.md`](docs/architecture/composer-mvp.md) for the detailed resolver, trust, and crash-boundary contract.

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

## Deferred work

Update/upgrade semantics for a repository with an existing composition lock remain future Composition work. They are not required to complete the branch-authority migration or to retire the legacy `skill` / `webapp` branch refs.

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
