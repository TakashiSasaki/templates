# Composition schemas

These JSON Schema Draft 2020-12 documents define the composition data model.

- `component.schema.json` — reusable artifact, capability, or lifecycle component descriptors.
- `recipe.schema.json` — consumer-facing artifact recipes.
- `composition-config.schema.json` — unresolved consumer intent.
- `composition-lock.schema.json` — immutable-source-bound resolved state.
- `catalog.schema.json` — closed production component/recipe inventory.

JSON Schema validates document shape and directly expressible cardinality/identity constraints. Repository tests additionally enforce semantic invariants that span fields or documents, such as disjoint selections, portable destination ownership, lexical ordering, resolved-owner references, catalog closure, dependency existence/cycles, and recipe-to-component references.

PR1's semantic checks are executable specification for the future composer and consumer validator. A materialized consumer must receive a validator, or an equivalent generated validation contract, that enforces applicable semantic invariants without reading the `composition` source checkout. JSON Schema validation alone is not the complete consumer-validation contract.

PR2 adds the first production catalog under `../catalog/` and validates real component source inventories and the Skill recipe. It still does not implement general dependency resolution, materialization, update behavior, or a public composer CLI.

Documents under `../examples/` remain schema fixtures rather than production catalog entries.
