# Contract manifest schema version 1 to 2

Contract manifest schema version 2 adds explicit version history for the manifest itself and for every registered domain contract. The history makes schema evolution reviewable and gives the validator a closed inventory of required migration documents.

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

## Migration procedure

1. Set `contracts/manifest.json` `schemaVersion` to `2`.
2. Add top-level `versionHistory` for the manifest, including this breaking transition.
3. Add `versionHistory` to every contract entry.
4. Record version 1 as `initial`.
5. Record every later version as `additive` or `breaking` and register its deterministic migration path.
6. Ensure the final history version equals `documentSchemaVersion` for each contract.
7. Keep every registered migration under `docs/migrations/` and remove unregistered migration documents.
8. Run both validator entry points and the complete test suite.

The validator requires histories to be contiguous from version 1, requires one migration document for every later version, rejects missing or symbolic-link migration documents, and rejects migration documents not registered by the manifest.

Version 1 manifests are not valid against the version 2 manifest schema because version histories are required. This is an intentional breaking bootstrap-metadata change.
