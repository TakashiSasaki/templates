# Composition source

This orphan branch is the source authority for reusable artifact, capability, and lifecycle components in `TakashiSasaki/templates`.

Consumer repositories are not created by copying a monolithic `template/` directory. The composition model resolves an artifact recipe plus explicit consumer intent into a deterministic component set, materializes that set, writes resolved state, and leaves the consumer repository self-contained.

## Migration state

PR1 established the architecture and machine-readable contracts for component descriptors, recipes, consumer intent, resolved locks, file ownership, deterministic composition, and semantic validation boundaries.

PR2 introduces the first production catalog and migrates Agent Skill application capabilities out of the legacy monolithic `skill/template/` authority.

The production Skill composition now separates:

- `artifact.skill-core` — Skill trigger/workflow/resource semantics and Skill-specific validation;
- `capability.runtime` — runtime, commands, dependency, distribution, environment, and deployment authority;
- `capability.cli` — packaged CLI behavior;
- `capability.mcp` — MCP protocol and transport behavior;
- `capability.mcp-apps` — MCP Apps extension behavior;
- `capability.web-interface` — standalone browser-facing interface behavior; and
- `capability.service` — independently reachable headless-service behavior.

`recipes/skill.json` selects `artifact.skill-core` and exposes the six generic application capabilities as optional composition choices. Capability dependencies are resolved independently of Skill semantics.

## Skill profile model

The composition-era Skill profile namespace contains only Skill-specific resource patterns:

- `instruction-only`;
- `knowledge-augmented`;
- `asset-driven`;
- `script-assisted`.

The former `packaged-cli`, `mcp-enabled`, `browser-interface`, and `headless-service` tags are intentionally retired rather than preserved for compatibility. Their responsibilities are composition capabilities.

`INTERFACES.md` is also retired in the new Skill artifact: preferred agent route and fallback policy belong in `SKILL.md`, while generic interface behavior and semantic-equivalence requirements belong to capability contracts.

## Production catalog

`catalog/catalog.json` is the closed production inventory. Catalog validation proves that component and recipe paths match that inventory, descriptor sources are closed, dependencies exist and are acyclic, recipe references are valid, and the complete Skill-capability selection has portable single-owner destinations.

The composer/resolver is not implemented yet. PR2 validates the authoritative source graph and materialized Skill projection without introducing installation/update behavior.

## Migration boundary

The legacy `skill` and `webapp` branches remain untouched during this PR. PR2 records the Skill source snapshot it was derived from, but does not connect branch histories.

Webapp artifact semantics and reusable lifecycle contracts remain for the next migration stage. Composer implementation, publication, Site integration, and final legacy-authority retirement are later independently reviewable changes.

See:

- [`docs/architecture/composition-model.md`](docs/architecture/composition-model.md)
- [`docs/architecture/catalog.md`](docs/architecture/catalog.md)
- [`docs/migrations/pr2-skill-capabilities.md`](docs/migrations/pr2-skill-capabilities.md)
- [`catalog/README.md`](catalog/README.md)
