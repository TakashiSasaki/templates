# Composition source

This orphan branch is the source authority for reusable artifact, capability, and lifecycle components in `TakashiSasaki/templates`.

Consumer repositories are produced from artifact recipes plus explicit consumer intent. The target composer resolves a deterministic component closure, materializes source and generated files, writes a lock, and leaves the consumer repository self-contained.

## Migration state

PR1 established the composition data model, safe-path/file-ownership rules, resolved-lock contract, and semantic validation boundaries.

PR2 established the first production catalog, migrated Agent Skill semantics into `artifact.skill-core`, and extracted runtime/CLI/MCP/MCP Apps/browser/service behavior into reusable `capability.*` authorities.

PR3 adds the Web application artifact and reusable lifecycle chain:

- `artifact.webapp-core` — browser surfaces, canonical routes, visible UI states, viewports/input capabilities, and Web-specific coverage validation;
- `lifecycle.contract-evolution` — generated closed contract registry, schema binding, version histories, and migrations;
- `lifecycle.implementation-evidence` — artifact-neutral implementation boundaries, proofs, commands, and release gates;
- `lifecycle.release-evidence` — exact-revision execution provenance/results/decision; and
- `lifecycle.release-bundle` — deterministic digest-closed release handoff.

The legacy `webapp` source snapshot used by PR3 is `fa269e1310a37ad46f3644ed4f46954a815380ec`. Its browser-domain contract bytes and their current domain version histories are preserved. The legacy branch history is not merged into `composition`.

## Generated contract manifest

`contracts/manifest.json` is no longer a monolithic artifact-owned source file. `component.json` may declare `contract_registrations`; `lifecycle.contract-evolution` is the unique owner of the generated manifest destination. A deterministic composer renders the manifest from the resolved registration set.

This avoids giving Webapp ownership of lifecycle registrations and allows the same lifecycle components to be selected by the Skill recipe.

## Recipes

`recipes/skill.json` selects `artifact.skill-core`. Application capabilities and lifecycle components are opt-in.

`recipes/webapp.json` selects `artifact.webapp-core`. The artifact requires the complete lifecycle chain transitively through `lifecycle.release-bundle`. Runtime/CLI/MCP/MCP Apps/operational Web exposure/headless service capabilities remain optional; a static/CDN Web application therefore does not acquire an application runtime merely because it is browser-facing.

## Authority boundaries

Artifact semantics and reusable application/lifecycle concerns remain separate. Generic capability/lifecycle descriptors must not depend on artifact authorities. Artifact components may require reusable lifecycle/capability components when those contracts are intrinsic to that artifact recipe.

The production catalog is closed and validated for dependency existence/acyclicity, source inventory, registration ownership, deterministic generated manifest input, portable destination ownership, and materialized Skill/Webapp validation.

## Deferred work

The general resolver/composer, production lock generation, apply/update behavior, publication catalog cutover, Site integration, and retirement of the legacy `skill` / `webapp` source authorities remain later independently reviewable work.

See:

- [`docs/architecture/composition-model.md`](docs/architecture/composition-model.md)
- [`docs/architecture/catalog.md`](docs/architecture/catalog.md)
- [`docs/architecture/generated-contract-manifest.md`](docs/architecture/generated-contract-manifest.md)
- [`docs/migrations/pr2-skill-capabilities.md`](docs/migrations/pr2-skill-capabilities.md)
- [`docs/migrations/pr3-webapp-lifecycle.md`](docs/migrations/pr3-webapp-lifecycle.md)
- [`catalog/README.md`](catalog/README.md)
