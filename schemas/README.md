# Composition schemas

The JSON Schema Draft 2020-12 contracts define the composition source and resolved-state model.

- `component.schema.json` — artifact/capability/lifecycle descriptors, materials, dependencies/conflicts, and optional `contract_registrations` metadata.
- `recipe.schema.json` — consumer-facing artifact recipes.
- `composition-config.schema.json` — unresolved consumer intent.
- `composition-lock.schema.json` — immutable-source-bound resolved state.
- `catalog.schema.json` — closed production component/recipe inventory.

A contract registration names one component-owned contract document/schema, stable migration slug, current document schema version, complete version history, and purpose. Registration metadata is source-time composition input; it is not copied into a consumer as an independent authority. `lifecycle.contract-evolution` deterministically renders the consumer `contracts/manifest.json` from the resolved registration set.

JSON Schema validates document shape. Repository tests additionally enforce cross-document semantics such as safe paths, disjoint selections, dependency closure, portable destination ownership, registration uniqueness/ownership, deterministic generation, resolved-owner references, and materialized validation.

The general composer/resolver/update implementation remains separate from these schemas.
