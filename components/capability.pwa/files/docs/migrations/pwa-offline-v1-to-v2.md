# PWA offline contract v1 to v2

Version 2 removes Webapp-specific surface, data-classification, and UI-state references from the PWA capability so the same capability can be composed with either a Website or a Web application.

Recompose pre-production consumers from the current recipe revision, then express offline behavior using shared Web route IDs and PWA-owned observable obligations:

| v1 field | v2 representation |
| --- | --- |
| `surfacePolicies[]` | `routePolicies[]` keyed by shared `routeId` |
| `networkUnavailableStateId` | `networkUnavailablePresentation: "required-visible"` |
| `freshnessUnknownStateId` | `freshnessUnknownPresentation: "required-visible"` |
| `revalidatingStateId` | `revalidatingPresentation: "required-visible"` |
| `pendingStateId` | `pendingMutationPresentation: "required-visible"` when queued mutations are enabled |
| `failureStateId` | `failedMutationPresentation: "required-visible"` when queued mutations are enabled |

`controlledRouteIds`, navigation fallback, service-worker scope, implementation-defined cache strategy, and freshness policies remain PWA authority. Artifact-specific surfaces, data classifications, and UI-state identifiers remain with their owning artifact and are not duplicated into the capability.
