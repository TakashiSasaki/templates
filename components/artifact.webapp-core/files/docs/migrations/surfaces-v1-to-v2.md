# Surfaces contract v1 to v2

Surfaces contract v2 renames the per-surface `startupDependencies` member to `surfaceDependencies`.

The old name was ambiguous: it could be read as package, process, runtime, or service startup requirements. The field has always represented references to other surface IDs declared in the same `contracts/surfaces.json` document. The validator checks those references for unknown surfaces, self-dependencies, and dependency cycles.

## Required migration

For every object in `surfaces`:

1. rename `startupDependencies` to `surfaceDependencies`;
2. preserve the array values unchanged; and
3. change the document-level `schemaVersion` from `1` to `2`.

Do not retain both member names. Contract v2 accepts only `surfaceDependencies`.

Example:

```json
{
  "id": "application",
  "surfaceDependencies": ["public"]
}
```

The values are surface IDs. They do not declare JavaScript packages, Python packages, backend services, operating-system processes, runtime installation requirements, or process startup ordering.

Because this is a breaking contract change, managed repositories using `artifact.webapp-core` v4 must use an explicit Composition `upgrade` to cross the component-version boundary to v5. Consumer-owned `contracts/surfaces.json` is a seed and is not overwritten by Composition; migrate that contract deliberately before expecting validation against the v2 managed schema to pass.
