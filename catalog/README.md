# Production composition catalog

`catalog.json` is the closed inventory of production component and recipe authorities available from this `composition` revision.

## Path convention

Every catalog component ID resolves to:

```text
components/<component-id>/component.json
```

Every recipe ID resolves to:

```text
recipes/<recipe-id>.json
```

Catalog arrays are unique and serialized in lexical order. Repository validation requires the catalog to exactly match the component and recipe authorities physically present under those roots.

## Closure rules

Production catalog validation establishes that:

- every descriptor and recipe validates against its schema;
- descriptor identity matches its directory;
- every declared copied material exists and every source file below a component's `files/` root is declared exactly once;
- every dependency/conflict reference names a catalog component;
- the dependency graph is acyclic;
- generic capability/lifecycle components do not depend on artifact-specific authorities;
- every recipe references one catalog artifact and only catalog capability/lifecycle components;
- recipe selection classes are disjoint; and
- tested recipe closures have portable, single-owner materialized destinations.

The future resolver will apply consumer include/exclude intent and generate a full composition lock. The catalog itself is source authority, not consumer material and not an execution-hook registry.
