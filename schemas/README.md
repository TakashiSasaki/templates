# Composition schemas

The JSON Schema Draft 2020-12 contracts define the composition source and resolved-state model.

- `component.schema.json` — artifact/capability/lifecycle descriptors, materials, dependencies/conflicts, optional `contract_registrations`, and bounded generated-material handler IDs.
- `recipe.schema.json` — consumer-facing artifact recipes.
- `composition-config.schema.json` — unresolved consumer intent.
- `composition-lock.schema.json` — immutable-source-bound resolved managed state, including normalized consumer intent.
- `composition-transaction.schema.json` — deterministic interrupted-update/upgrade recovery metadata and mutation preconditions.
- `catalog.schema.json` — closed production component/recipe inventory.

A contract registration names one component-owned contract document/schema, stable migration slug, current document schema version, complete version history, and purpose. Registration metadata is source-time composition input; it is not copied into a consumer as an independent authority. `lifecycle.contract-evolution` deterministically renders the consumer `contracts/manifest.json` from the resolved registration set.

JSON Schema validates document shape. Repository tests and `scripts/compose.py` additionally enforce cross-document semantics such as safe paths, disjoint selections, dependency closure, portable destination ownership, registration uniqueness/ownership, deterministic generation, source tracking, resolved-owner references, materialized validation, and transaction action consistency.

The Composer supports initial `inspect`, `plan`, `apply`, and `validate` behavior plus explicit read-only `update` planning and crash-recoverable `update` apply. Update mutation is represented by `.template-composition/transaction.json`: it binds the exact old/new lock state and ordered create/replace/remove actions. Recovery accepts only each action's recorded old digest or its already-applied new state, then validates the new managed state before deleting the transaction marker.

`upgrade` remains the explicit later layer for consumer-intent or component-version compatibility changes; it reuses the same transaction contract rather than introducing a second mutation protocol.
