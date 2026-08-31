# Routes schema version 1 to 2

Routes schema version 2 adds a required `accessFailures` object to every canonical route. The object declares the observable presentation behavior when authentication or authorization prevents the requested route from continuing.

## Compatibility impact

Version 1 route documents are invalid against the version 2 schema because `accessFailures` is required. Consumers that deserialize, generate, validate, or render routes must support both required conditions before the repository switches its route contract to version 2.

The transition changes implementation obligations as well as structure. A protected route must explicitly render an access state or redirect; public and inapplicable conditions must explicitly say so. Deploying the document update before implementations understand those behaviors can produce missing access handling or inconsistent UI-state evidence.

## Behavior values

Each condition accepts one of three values:

- `render-state`: keep the route presentation boundary and render the corresponding route-scoped UI state;
- `redirect`: leave the current route presentation through a redirect;
- `not-applicable`: the condition cannot occur under the route and surface access declarations.

The `unauthenticated` condition corresponds to the `unauthorized` UI state when rendered. The `forbidden` condition corresponds to the `forbidden` UI state when rendered.

## Applicability rules

- A route with `authentication: required` must set `unauthenticated` to `render-state` or `redirect`.
- A route with `authentication: none` or `optional` must set `unauthenticated` to `not-applicable`.
- A route owned by a surface with role authorization must set `forbidden` to `render-state` or `redirect`.
- A route owned by a surface with public or authenticated authorization must set `forbidden` to `not-applicable`.
- `render-state` requires the corresponding UI state identifier in the route's `states` collection.
- `redirect` and `not-applicable` prohibit that condition's UI state identifier in the route's `states` collection.

`authenticationReturn` remains a separate declaration. It describes whether a successful authentication flow returns to the original route; it does not select the initial access-failure behavior or the redirect destination.

## Identifier mappings

No route, surface, or UI-state identifier is renamed by this transition. Existing route IDs and paths remain stable.

The new condition-to-state mappings are:

- `accessFailures.unauthenticated: render-state` maps to the existing route-scoped `unauthorized` UI-state identifier;
- `accessFailures.forbidden: render-state` maps to the existing route-scoped `forbidden` UI-state identifier;
- `redirect` and `not-applicable` map to no route state and require removal of the corresponding state reference.

Redirect destinations, identity-provider identifiers, and authorization-recovery identifiers remain product-owned and must be recorded in implementation documentation rather than added implicitly to this contract migration.

## Migration procedure

1. Set `contracts/routes.json` `schemaVersion` to `2`.
2. Set the `routes` entry's `documentSchemaVersion` in `contracts/manifest.json` to `2` and append the breaking version-history entry that registers this migration.
3. Add `accessFailures.unauthenticated` and `accessFailures.forbidden` to every route.
4. Select each behavior from the route authentication declaration and the owning surface authorization mode.
5. Add or remove `unauthorized` and `forbidden` route state references according to the selected behavior.
6. Record redirect destinations, identity-provider integration, and authorization recovery flows in product-owned implementation documentation.
7. Synchronize schema, example document, validators, tests, implementation evidence, and release documentation.
8. Run both current-contract validator entry points, both evolution-validator entry points when retained, and the complete test suite.

## Implementation and evidence

Before completion, implementation evidence must show:

- each required-authentication route rejects or redirects an unauthenticated request according to its declaration;
- each role-authorized route rejects or redirects a forbidden request according to its declaration;
- each `render-state` route deterministically renders and announces the mapped route-scoped state;
- each `redirect` route uses the documented destination and preserves or discards return context intentionally;
- each `not-applicable` condition is unreachable under the route and owning-surface access declarations;
- client-side route names are not treated as trusted authorization enforcement;
- positive, negative, direct-navigation, deep-link, and recovery tests run through the product's authoritative commands.

The evidence matrix must identify the route declaration, trusted enforcement boundary, presentation implementation, test or fixture, expected result, and release gate.

## Deployment sequencing

1. Add implementation support for all selected access-failure behaviors and corresponding tests while the deployed contract remains version 1.
2. Deploy trusted authentication and authorization enforcement, rendered states, redirect handling, and telemetry capable of observing both old and new consumers.
3. Update every contract consumer, generator, validator, and evidence mapping to understand version 2.
4. Commit the schema, route document, manifest history, migration, validators, tests, and guidance as one reviewed change.
5. Run CI and pre-production tests, then deploy the contract-aware product revision before or atomically with publishing the version 2 route document.
6. Monitor access failures, redirect loops, missing states, and authorization denials before removing temporary version 1 compatibility code.

Do not publish version 2 declarations to consumers that still assume the version 1 shape.

## Rollback

Preserve the last version 1 route document, schema, manifest entry, implementation revision, and evidence baseline until version 2 rollout is verified.

To roll back before consumers depend on version 2:

1. restore the version 1 route schema and route document together;
2. restore the manifest route version and history to the version 1-compatible baseline;
3. redeploy the last implementation that understands the version 1 route shape;
4. retain trusted access enforcement even if the explicit presentation declarations are removed;
5. run the version 1 validators and complete product tests.

Once consumers or releases depend on `accessFailures`, prefer a forward-fix or coordinated consumer rollback. Do not downgrade only the contract document while leaving version 2 validators or consumers active, and do not remove trusted authorization behavior merely because its version 2 presentation declaration is rolled back.

This is an intentional breaking contract change.
