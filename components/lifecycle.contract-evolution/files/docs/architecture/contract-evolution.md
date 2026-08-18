# Contract evolution lifecycle

`lifecycle.contract-evolution` owns the generic closed contract registry and evolution validation mechanism.

The materialized `contracts/manifest.json` is generated deterministically from the `contract_registrations` metadata of the resolved component set. No artifact or capability may partially edit or append to the manifest.

The generated manifest records active contract IDs, document/schema paths, current schema versions, version histories, migration slugs, and purposes. The manifest bootstrap format is versioned independently from registered domain contracts.

Validation establishes exact contract/document/schema inventory closure, unique identities and paths, JSON Schema validity and document/schema agreement, contiguous version histories, deterministic migration paths, and a closed migration-artifact inventory.

`contracts/manifest.json` is generated material. Consumer edits are not authority; the composition lock and generated-file digest govern update safety.
