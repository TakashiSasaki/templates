# Composition source

This orphan branch is the source authority for reusable artifact, capability, and lifecycle components in `TakashiSasaki/templates`.

Consumer repositories are produced from artifact recipes plus explicit consumer intent. The composer resolves a deterministic component closure, materializes source and generated files, writes a lock, and leaves the consumer repository self-contained.

## Migration state

PR1 established the composition data model, safe-path/file-ownership rules, resolved-lock contract, and semantic validation boundaries.

PR2 established the first production catalog, migrated Agent Skill semantics into `artifact.skill-core`, and extracted runtime/CLI/MCP/MCP Apps/browser/service behavior into reusable `capability.*` authorities.

PR3 added the Web application artifact and reusable lifecycle chain:

- `artifact.webapp-core` — browser surfaces, canonical routes, visible UI states, viewports/input capabilities, and Web-specific coverage validation;
- `lifecycle.contract-evolution` — generated closed contract registry, schema binding, version histories, and migrations;
- `lifecycle.implementation-evidence` — artifact-neutral implementation boundaries, proofs, commands, and release gates;
- `lifecycle.release-evidence` — exact-revision execution provenance/results/decision; and
- `lifecycle.release-bundle` — deterministic digest-closed release handoff.

PR4 adds the first deterministic composer/resolver MVP and universal consumer composition-state validation. Its public operation model is:

```text
inspect -> plan -> apply -> validate
```

`update` is deliberately not implemented in the MVP. A repository containing an existing composition lock is treated as managed state and update is refused rather than inferred.

The legacy `webapp` source snapshot used by PR3 is `fa269e1310a37ad46f3644ed4f46954a815380ec`. Its browser-domain contract bytes and their current domain version histories are preserved. The legacy branch history is not merged into `composition`.

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

## Authority boundaries

Artifact semantics and reusable application/lifecycle concerns remain separate. Generic capability/lifecycle descriptors must not depend on artifact authorities. Artifact components may require reusable lifecycle/capability components when those contracts are intrinsic to that artifact recipe.

The production catalog is closed and validated for dependency existence/acyclicity, source inventory, registration ownership, deterministic generated material input, portable destination ownership, and materialized Skill/Webapp validation.

## Deferred work

Update/upgrade semantics for an existing composition lock, publication catalog cutover, Site integration, and retirement of the legacy `skill` / `webapp` source authorities remain later independently reviewable work.

See:

- [`docs/architecture/composition-model.md`](docs/architecture/composition-model.md)
- [`docs/architecture/catalog.md`](docs/architecture/catalog.md)
- [`docs/architecture/generated-contract-manifest.md`](docs/architecture/generated-contract-manifest.md)
- [`docs/architecture/composer-mvp.md`](docs/architecture/composer-mvp.md)
- [`docs/migrations/pr2-skill-capabilities.md`](docs/migrations/pr2-skill-capabilities.md)
- [`docs/migrations/pr3-webapp-lifecycle.md`](docs/migrations/pr3-webapp-lifecycle.md)
- [`catalog/README.md`](catalog/README.md)
