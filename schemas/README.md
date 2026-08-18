# Composition schemas

These JSON Schema Draft 2020-12 documents define the PR1 composition data model.

- `component.schema.json` — reusable artifact, capability, or lifecycle component descriptors.
- `recipe.schema.json` — consumer-facing artifact recipes.
- `composition-config.schema.json` — unresolved consumer intent.
- `composition-lock.schema.json` — immutable-source-bound resolved state.

JSON Schema validates document shape and directly expressible cardinality/identity constraints. Repository tests additionally enforce semantic invariants that span fields or documents, such as disjoint selections, portable destination ownership, lexical ordering, and resolved-owner references.

The semantic checks in PR1 are executable specification for the future composer and consumer validator. A materialized consumer must receive a validator, or an equivalent generated validation contract, that enforces the applicable semantic invariants without reading the `composition` source checkout. JSON Schema validation alone is not the complete future consumer-validation contract.

The schemas define data contracts only. They do not implement dependency resolution, materialization, update behavior, or a public composer CLI.

The documents under `../examples/` are executable fixtures, not production catalog entries.
