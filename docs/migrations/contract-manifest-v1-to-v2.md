# Contract manifest schema version 1 to 2

Contract manifest schema version 2 adds explicit version history for the manifest itself and for every registered domain contract. The history makes schema evolution reviewable and gives the validator a closed inventory of required migration artifacts. It also introduces stable migration slugs and retired-contract tombstones so historical migrations survive document moves and contract-family retirement.

## Version history entries

Every history starts with:

```json
{
  "version": 1,
  "changeType": "initial"
}
```

Every later version adds one transition entry:

```json
{
  "version": 2,
  "changeType": "additive",
  "migration": "docs/migrations/example-v1-to-v2.md"
}
```

`changeType` is `additive` when every previously valid document remains valid and existing declarations preserve their meaning. It is `breaking` when a previously valid document may become invalid, a required migration is introduced, an existing declaration changes meaning, or a stable identifier is renamed or removed.

A prose clarification, test refactor, validator implementation change, or documentation correction that does not alter accepted contract instances or their meaning does not increment a contract document's `schemaVersion`.

## Stable migration slugs

Every active and retired contract has one `migrationSlug`. Migration filenames are derived from this stable value, not from the current contract document path. A later document or schema move must preserve the existing slug so earlier history entries and migration filenames remain unchanged.

## Retired contract tombstones

Top-level `retiredContracts` preserves the identity, final live document and schema paths, migration slug, complete history, last live document version, retirement version, and purpose of a removed non-core contract family. The live document and schema files are removed from the active inventory; the tombstone and retirement migration remain.

The retirement version is exactly one greater than the last live document schema version. Its final history entry is classified as `breaking` and explains removal, consumer migration, deployment sequencing, and rollback.

## Migration procedure

1. Set `contracts/manifest.json` `schemaVersion` to `2`.
2. Add top-level `versionHistory` for the manifest, including this breaking transition.
3. Add `versionHistory` and a stable `migrationSlug` to every active contract entry.
4. Add top-level `retiredContracts`; use an empty array when no family has been retired.
5. Record version 1 as `initial`.
6. Record every later version as `additive` or `breaking` and register its deterministic migration path.
7. Ensure the final active-contract history version equals `documentSchemaVersion`.
8. When retiring a non-core family, remove its live files and active entry only after adding its tombstone and breaking retirement migration.
9. Keep every registered migration under `docs/migrations/` and remove every unregistered artifact from that directory, regardless of filename extension.
10. Run both current-contract validator entry points, both evolution-validator entry points, and the complete test suite.

The validator requires histories to be contiguous from version 1, requires one migration document for every later version, rejects missing, unreadable, visually empty, non-regular, or symbolic-link migration documents, and rejects any artifact under `docs/migrations/` that is not registered by the manifest. It preserves historical filenames through `migrationSlug` and retains removed-family histories through `retiredContracts`.

## Rollback

Before rollout, preserve the complete version 1 manifest, its bootstrap schema, validation workflow, and the deployed revision that consumes them. A rollback to version 1 is safe only while no retained generated repository, automation, or release process depends on version 2 histories, migration slugs, retired-contract tombstones, or the evolution-validator commands.

To roll back:

1. restore the version 1 `contracts/manifest.json` and `schemas/contract-manifest.schema.json` together;
2. remove the version 2-only top-level and per-contract evolution fields from the restored manifest;
3. restore the version 1 validation workflow and remove the evolution-validator CI steps;
4. retain domain migration documents that are still required by domain contract versions, even though the version 1 bootstrap manifest cannot inventory them;
5. run the version 1 validator entry points and complete version 1 test suite;
6. redeploy the last revision whose consumers are known to understand the version 1 bootstrap format.

Do not partially downgrade only the manifest or only its schema. If any consumer already relies on version 2 evolution metadata, use a forward-fix or a coordinated consumer rollback rather than deleting history and tombstones from the active release.

Version 1 manifests are not valid against the version 2 manifest schema because version histories, migration slugs, and `retiredContracts` are required. This is an intentional breaking bootstrap-metadata change.
