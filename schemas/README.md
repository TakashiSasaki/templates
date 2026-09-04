# Composition schemas

The JSON Schema Draft 2020-12 contracts define the composition source, resolved-state, and immutable installer-publication model.

- `component.schema.json` — foundation/artifact/capability/lifecycle descriptors, materials, dependencies/conflicts, optional `contract_registrations`, and bounded generated-material handler IDs.
- `recipe.schema.json` — consumer-facing artifact recipes. Recipes select one artifact and may expose capability/lifecycle choices; foundation components are resolved transitively rather than selected directly by consumers.
- `composition-config.schema.json` — unresolved consumer intent.
- `composition-playground-projection.schema.json` — the compact Composition-owned Playground v1 projection: production recipe case tables, canonical outcome inventory, provider-generated provenance reason bits and dependency edges, contracts, materials, and empty-target initial-plan summaries.
- `composition-lock.schema.json` — immutable-source-bound resolved managed state, including normalized consumer intent.
- `composition-transaction.schema.json` — deterministic interrupted-update/upgrade recovery metadata and mutation preconditions.
- `catalog.schema.json` — closed production component/recipe inventory.
- `composition-skill-installer-release.schema.json` — stable release metadata that separates the immutable remote-installer revision, installed skill-source revision, and Composition toolchain revision.

The Playground projection is generated only from canonical Composition resolution/planning APIs. `generated/composition-playground-v1.json.gz` is a deterministic gzip transport for that canonical JSON and is published at `playground/composition-playground-v1.json.gz`.

Playground provenance has three deliberately separate identities:

1. `projection_id` plus `schema_version` identify the projection contract and payload family.
2. The gzip payload's `source.revision` is the **semantic source revision**: the exact Composition revision whose canonical Composer semantics produced the projected cases, provenance, contracts, materials, ownership, and empty-target plan summaries.
3. The **publication/provider revision** is the exact Composition checkout selected by Site and recorded by Site in `/build-provenance.json`. It identifies the provider revision that supplied the published gzip asset and may be a publication-only descendant of `source.revision`.

The semantic source revision and publication/provider revision therefore are not required to be equal. Publication CI is the authoritative place that validates their relationship: regenerating the asset through `build_projection(source_revision=...)` requires the embedded semantic revision to be an ancestor of the current provider checkout and rejects the publication if any Playground semantic path changed between those revisions. A browser consumer must not attempt to reproduce Git ancestry validation or reject a valid publication-only descendant merely because the two SHAs differ. The transport does not embed its own provider commit SHA, so no self-referential final-commit identity is introduced.

A contract registration names one component-owned contract document/schema, stable migration slug, current document schema version, complete version history, and purpose. Registration metadata is source-time composition input; it is not copied into a consumer as an independent authority. `lifecycle.contract-evolution` deterministically renders the consumer `contracts/manifest.json` from the resolved registration set.

JSON Schema validates document shape. Repository tests and `scripts/compose.py` additionally enforce cross-document semantics such as safe paths, component-role/id agreement, foundation direct-selection restrictions, disjoint selections, dependency closure, portable destination ownership, registration uniqueness/ownership, deterministic generation, source tracking, resolved-owner references, materialized validation, and transaction action consistency. Installer-publication verification additionally checks the referenced immutable Git history and the `toolchain -> skill source -> installer -> publication` ancestry chain; those properties cannot be established by JSON Schema alone.

Destination schemas enforce provider ownership as well as Composer-internal metadata reservation. Composition materials, lock inventories, and transaction actions may not claim `.agent-policy.yml`, `.agent-policy.lock`, or `.agent-policy/**`; those are foreign Policy-owned paths. This is a path-ownership constraint only: Composition does not parse Policy schemas, locks, profiles, or runtime state.

The Composer supports initial `inspect`, `plan`, `apply`, and `validate` behavior plus explicit managed-state `update` and `upgrade` modes. Both managed modes are read-only at `plan` time and use `.template-composition/transaction.json` for crash-recoverable `apply` mutation. The transaction binds exact old/new lock state and ordered create/replace/remove actions. Recovery accepts only each action's recorded old digest or its already-applied new state, then validates the new managed state before deleting the transaction marker.

`update` reconstructs intent from lock v2 and rejects a new `--config`; component-version changes require upgrade. `upgrade` requires an explicit new configuration for a new transaction and may change recipe/include/exclude/parameters and component versions. It still does not infer file-owner or ownership-mode migrations, and it rejects descriptor-byte drift that occurs without a component-version change.

New seed material is a `create` action because no consumer-owned file exists yet. Once first materialization succeeds, seed ownership transfers to the consumer: common seed bytes are preserved, their original provenance digest is carried forward, and removed seed files are left as ordinary consumer-owned extras.
