# UI states schema version 1 to 2

UI states schema version 2 adds a required `scope` property to every state declaration. The change distinguishes states owned by a canonical route from states owned by the application shell, router, or another top-level presentation boundary.

## Scope values

- `route`: the state is part of one or more canonical routes. At least one route must list the state identifier in its `states` collection.
- `global`: the state is not owned by a canonical route. Routes must not list the state identifier in their `states` collections.

Multiple canonical routes may reference the same route-scoped state.

## Migration procedure

1. Set `contracts/ui-states.json` `schemaVersion` to `2`.
2. Set the `ui_states` entry's `documentSchemaVersion` in `contracts/manifest.json` to `2`.
3. Add `scope` to every state.
4. Use `route` for states rendered within canonical route ownership and confirm that each is referenced by at least one route.
5. Use `global` for application-shell, router-level, or top-level error-boundary states and remove those identifiers from every route declaration.
6. Run both validator entry points and the complete test suite.

The template example classifies `loading`, `empty`, `populated`, `partial`, `recoverable-error`, `offline`, `unauthorized`, and `forbidden` as route-scoped. It classifies `fatal-error`, `retrying`, and `not-found` as global. Generated repositories must choose scopes according to their own observable ownership boundaries rather than copying those classifications without review.

Version 1 documents are not valid against the version 2 schema because `scope` is required. This is an intentional breaking contract change.
