# UI states schema version 1 to 2

UI states schema version 2 adds a required `scope` property to every state declaration. The change distinguishes states owned by a canonical route from states owned by the application shell, router, or another top-level presentation boundary.

## Compatibility impact

Version 1 UI-state documents are invalid against the version 2 schema because `scope` is required. Route contracts and presentation implementations must agree with each classification before the repository switches the document to version 2.

The transition changes ownership semantics, not only document shape. A state classified as `route` must be reachable through at least one canonical route. A state classified as `global` must be removed from every route declaration and implemented through an application-level owner. Incorrect sequencing can leave a route referring to a global state or leave a route-scoped state without any owning route.

## Scope values

- `route`: the state is part of one or more canonical routes. At least one route must list the state identifier in its `states` collection.
- `global`: the state is not owned by a canonical route. Routes must not list the state identifier in their `states` collections.

Multiple canonical routes may reference the same route-scoped state.

## Identifier mappings

No UI-state identifier is renamed by this transition. Every version 1 state ID maps to the same version 2 state ID plus one explicit ownership classification.

For the template example:

- `loading`, `empty`, `populated`, `partial`, `recoverable-error`, `offline`, `retrying`, `unauthorized`, and `forbidden` retain their identifiers and map to `scope: route`;
- `fatal-error` and `not-found` retain their identifiers and map to `scope: global`.

Generated repositories must derive mappings from their actual observable ownership boundaries. A product that renders `not-found` inside canonical route ownership may classify it as `route`; it must then add the corresponding route reference and evidence rather than copy the example mapping mechanically.

## Migration procedure

1. Set `contracts/ui-states.json` `schemaVersion` to `2`.
2. Set the `ui_states` entry's `documentSchemaVersion` in `contracts/manifest.json` to `2` and append the breaking version-history entry that registers this migration.
3. Add `scope` to every state.
4. Use `route` for states rendered within canonical route ownership and confirm that each is referenced by at least one route.
5. Use `global` for application-shell, router-level, or top-level error-boundary states and remove those identifiers from every route declaration.
6. Synchronize the UI-state schema, example document, routes, validators, tests, implementation evidence, and release documentation.
7. Run both current-contract validator entry points, both evolution-validator entry points when retained, and the complete test suite.

The template example routes list `retrying` because it is the visible transition after a recoverable operation is retried. Generated repositories must choose scopes according to their own observable ownership boundaries rather than copying those classifications without review.

## Implementation and evidence

Before completion, implementation evidence must show:

- every route-scoped state is rendered through at least one declared canonical route;
- every global state is rendered through a documented application-shell, router, or top-level error owner;
- no route lists a global state;
- route transitions, focus handling, announcements, and recovery actions remain correct after classification;
- direct navigation and route changes do not bypass global ownership or orphan route-scoped states;
- positive and negative tests exercise both valid ownership and rejected cross-contract combinations.

The evidence matrix must identify each state, scope, implementation owner, route references when applicable, test or fixture, expected observable result, and authoritative command.

## Deployment sequencing

1. Inventory current rendering ownership and route references while the deployed contract remains version 1.
2. Add application-level owners for states that will become global and route-level owners for states that will become route-scoped.
3. Update route declarations and implementation tests so the proposed version 2 document already has consistent owners.
4. Update every consumer, generator, validator, and evidence mapping to understand `scope`.
5. Commit the schema, UI-state document, routes, manifest history, migration, validators, tests, and guidance as one reviewed change.
6. Run CI and pre-production tests, then deploy the scope-aware implementation before or atomically with publishing the version 2 UI-state document.
7. Monitor missing-state rendering, incorrect error-boundary ownership, focus regressions, and route/global recovery behavior before removing temporary version 1 compatibility code.

Do not publish version 2 classifications while active consumers still infer ownership solely from route references.

## Rollback

Preserve the last version 1 UI-state document, schema, manifest entry, route declarations, implementation revision, and evidence baseline until rollout is verified.

To roll back before consumers depend on version 2:

1. restore the version 1 UI-state schema and document together;
2. restore the manifest UI-state version and history to the version 1-compatible baseline;
3. restore route declarations only when doing so does not remove required presentation behavior;
4. redeploy the last implementation that understands the version 1 shape;
5. run the version 1 validators and complete product tests.

Once consumers or releases depend on explicit scope, prefer a forward-fix or coordinated consumer rollback. Do not downgrade only the document while leaving scope-aware route validation active, and do not delete application-level error handling merely because the explicit global classification is rolled back.

This is an intentional breaking contract change.
