# Contract evolution lifecycle

`lifecycle.contract-evolution` owns the generic closed contract registry and evolution validation mechanism.

The materialized `contracts/manifest.json` is generated deterministically from the `contract_registrations` metadata of the resolved component set. No artifact or capability may partially edit or append to the manifest.

The generated manifest records active contract IDs, document/schema paths, current schema versions, version histories, migration slugs, and purposes. The manifest bootstrap format is versioned independently from registered domain contracts.

Validation establishes exact Composition-owned contract/document/schema inventory closure, unique identities and paths, JSON Schema validity and document/schema agreement, contiguous version histories, deterministic migration paths, and a closed Composition-owned migration-artifact inventory. In a managed consumer, the validated Composition lock defines that inventory. Unlisted consumer-owned files in `contracts/`, `schemas/`, or `docs/migrations/` remain outside Composition ownership and validation; their own product validators remain responsible. Missing registered files and unregistered Composition-owned files still fail. Standalone validation without a lock retains whole-directory closure; normal consumers use the full Composition validation entrypoint, which validates the lock before this registered validator.

`contracts/manifest.json` is generated material. Consumer edits are not authority; the composition lock and generated-file digest govern update safety.
