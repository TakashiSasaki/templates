# Composition schemas

These JSON Schema Draft 2020-12 documents define the PR1 composition data model.

- `component.schema.json` — reusable artifact, capability, or lifecycle component descriptors.
- `recipe.schema.json` — consumer-facing artifact recipes.
- `composition-config.schema.json` — unresolved consumer intent.
- `composition-lock.schema.json` — immutable-source-bound resolved state.

JSON Schema validates document shape. Repository tests additionally enforce semantic invariants that span fields or documents, such as disjoint selections, unique materialized destinations, and lock ownership references.

The schemas define data contracts only. They do not implement dependency resolution, materialization, update behavior, or a public composer CLI.
