# PWA offline contract v1 to v2

Version 2 removes Webapp-specific surface, data-classification, and UI-state references from the PWA capability so the same capability can be composed with either a Website or a Web application.

Recompose pre-production consumers from the current recipe revision, then express offline behavior using shared Web route IDs and PWA-owned observable obligations:

| v1 field | v2 representation |
| --- | --- |
| `surfacePolicies[]` | `routePolicies[]` keyed by shared `routeId`; each entry must also choose `offlineReadBehavior` as described below |
| `networkUnavailableStateId` | `networkUnavailablePresentation: "required-visible"` |
| `freshnessUnknownStateId` | `freshnessUnknownPresentation: "required-visible"` |
| `revalidatingStateId` | `revalidatingPresentation: "required-visible"` |
| `pendingStateId` | `pendingMutationPresentation: "required-visible"` when `mutationBehavior` is `queue-until-online` |
| `failureStateId` | `failedMutationPresentation: "required-visible"` when `mutationBehavior` is `queue-until-online` |

## Choose `offlineReadBehavior` for every controlled route

There is no mechanical one-to-one rename from a v1 `surfacePolicy` to a v2 `routePolicy`. Version 1 expressed cacheability through artifact-owned surfaces and data classifications; version 2 deliberately removes those artifact-private identifiers. Migration therefore requires an explicit route-level product decision for **every** `controlledRouteIds` entry.

For each controlled shared Web route:

1. Identify the v1 surface(s) reached by that route and the content the product intentionally made available during network loss.
2. If the product contract promises that previously obtained content for that route may be displayed while offline, set:

   ```json
   {
     "routeId": "example-route",
     "offlineReadBehavior": "cached-content-when-available"
   }
   ```

   A non-empty v1 `cacheableDataClassifications` list can be evidence for this choice only when those classifications actually represented content reachable through that route and the product intended that content to remain readable offline. Do not copy the classification identifiers into v2; they remain artifact-specific historical information.
3. If the route must **not** display cached product content during network loss, including a v1 surface whose `cacheableDataClassifications` was empty or whose classified data was not intended to satisfy that route offline, set:

   ```json
   {
     "routeId": "example-route",
     "offlineReadBehavior": "network-unavailable-presentation"
   }
   ```
4. If several v1 surfaces map to one shared route and their old cacheability choices disagree, do not guess. Decide the supported route-level offline behavior explicitly, update the product implementation accordingly, and capture new planning/product evidence for the v2 behavior.

The v2 evidence inventory follows these route choices. `offline-cached-content` and `freshness-unverified` proof families are required only when at least one route uses `cached-content-when-available`; a network-only product must not manufacture positive cached-content evidence.

## Queued mutation migration

`mutationBehavior` keeps the same three values. When it is `queue-until-online`, v2 requires both `pendingMutationPresentation` and `failedMutationPresentation` with value `"required-visible"`. Those caller-visible pending/failure obligations also require implementation-evidence proof families; preserving only the old state IDs is not sufficient.

When `mutationBehavior` is `not-applicable` or `reject-when-offline`, do not carry `pendingStateId` or `failureStateId` forward as v2 presentation fields.

`controlledRouteIds`, navigation fallback, service-worker scope, implementation-defined cache strategy, and freshness policies remain PWA authority. Artifact-specific surfaces, data classifications, and UI-state identifiers remain with their owning artifact and are not duplicated into the capability.
