# Composition schemas

The JSON Schema Draft 2020-12 contracts define the composition source and resolved-state model.

- `component.schema.json` — artifact/capability/lifecycle descriptors, materials, dependencies/conflicts, optional `contract_registrations`, and bounded generated-material handler IDs.
- `recipe.schema.json` — consumer-facing artifact recipes.
- `composition-config.schema.json` — unresolved consumer intent.
- `composition-lock.schema.json` — immutable-source-bound resolved state.
- `catalog.schema.json` — closed production component/recipe inventory.

A contract registration names one component-owned contract document/schema, stable migration slug, current document schema version, complete version history, and purpose. Registration metadata is source-time composition input; it is not copied into a consumer as an independent authority. `lifecycle.contract-evolution` deterministically renders the consumer `contracts/manifest.json` from the resolved registration set.

JSON Schema validates document shape. Repository tests and `scripts/compose.py` additionally enforce cross-document semantics such as safe paths, disjoint selections, dependency closure, portable destination ownership, registration uniqueness/ownership, deterministic generation, source tracking, resolved-owner references, and materialized validation.

The composer MVP implements initial `inspect`, `plan`, `apply`, and `validate` behavior over these schemas. It deliberately does not implement update semantics for an existing composition lock; that remains a separate versioned behavioral contract rather than an implicit consequence of the data schemas.
