# Routes v2 to v3 migration

Routes schema v3 makes every access-failure destination explicit.

Version 2 represented `accessFailures.unauthenticated` and `accessFailures.forbidden` as behavior strings:

```json
{
  "unauthenticated": "render-state",
  "forbidden": "redirect"
}
```

That was sufficient to state *how* access failed, but not *where* a rendered or redirected failure was handled. In particular, two implementations could both satisfy `"unauthenticated": "redirect"` while sending the user to different routes. The route contract also could not state which concrete UI state implemented a rendered failure.

Version 3 replaces each behavior string with a discriminated object:

```json
{
  "unauthenticated": {
    "behavior": "redirect",
    "routeId": "sign-in"
  },
  "forbidden": {
    "behavior": "render-state",
    "stateId": "forbidden"
  }
}
```

The three forms are:

- `{"behavior":"render-state","stateId":"..."}` — names the route-scoped access UI state;
- `{"behavior":"redirect","routeId":"..."}` — names the canonical redirect destination route;
- `{"behavior":"not-applicable"}` — declares that the failure condition does not apply.

The cross-contract validator requires render-state targets to exist, have `scope: route` and `category: access`, and be declared in the owning route's `states`. Redirect targets must name an existing different route. An unauthenticated redirect target must not itself require authentication, preventing an immediate authentication redirect loop.

Version 3 no longer infers an access-failure target from a conventional state identifier merely because that state appears in the route's `states` inventory. The explicit `stateId` is the binding authority for a `render-state` condition. A route may therefore support other route-scoped access states without implicitly assigning them to `unauthenticated` or `forbidden`; `redirect` and `not-applicable` likewise do not acquire a state target from the inventory.

`authenticationReturn` remains the provider-neutral contract for post-authentication return behavior. Routes v3 intentionally does not prescribe a query parameter name, cookie, session field, framework callback, or other transport for carrying that return state. For example, an implementation may use `/sign-in?returnTo=/app`, while the contract only needs to say that the access failure redirects to route `sign-in` and that the protected route has `authenticationReturn: same-route`.

This is a breaking schema change. Convert every v2 behavior string to the corresponding v3 object and increment `schemaVersion` from `2` to `3`.
