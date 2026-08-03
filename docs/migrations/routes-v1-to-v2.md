# Routes schema version 1 to 2

Routes schema version 2 adds a required `accessFailures` object to every canonical route. The object declares the observable presentation behavior when authentication or authorization prevents the requested route from continuing.

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

## Migration procedure

1. Set `contracts/routes.json` `schemaVersion` to `2`.
2. Set the `routes` entry's `documentSchemaVersion` in `contracts/manifest.json` to `2`.
3. Add `accessFailures.unauthenticated` and `accessFailures.forbidden` to every route.
4. Select each behavior from the route authentication declaration and the owning surface authorization mode.
5. Add or remove `unauthorized` and `forbidden` route state references according to the selected behavior.
6. Record redirect destinations, identity-provider integration, and authorization recovery flows in product-owned implementation documentation.
7. Run both validator entry points and the complete test suite.

Version 1 route documents are not valid against the version 2 schema because `accessFailures` is required. This is an intentional breaking contract change.
