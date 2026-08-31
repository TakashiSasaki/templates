# Progressive Web App decision record

`capability.pwa` is the opt-in Composition capability for an installable Web product whose browser-visible behavior remains understandable during network loss and product updates. It can be composed with a Website or a Web application; selecting it does not change artifact identity.

This capability defines product semantics, not an implementation recipe. It does not choose a frontend framework, a service-worker library, a cache algorithm, a package manager, or a deployment platform.

## What the three contracts own

- `contracts/pwa-manifest.json` owns Web App Manifest intent, launch/scope binding, installability prerequisites, and cross-platform installed-icon intent.
- `contracts/pwa-offline.json` owns controlled shared Web routes, route-scoped offline read behavior, caller-visible network-loss/freshness obligations, and mutation behavior.
- `contracts/pwa-update.json` owns observable update detection, activation, unsaved-work handling, and caller-visible update presentation obligations.

The generated Composition `contracts/manifest.json` is a registry of Composition contracts. It is **not** the Web App Manifest.

## Shared Web authority, not Webapp authority

PWA launch and controlled-navigation semantics reference `foundation.web` route IDs. Canonical paths, aliases, deep-link expectations, and accessibility remain owned by the shared Web foundation. The PWA capability does not require `application-routes.json`, `surfaces.json`, or `ui-states.json`, and it does not invent substitutes for those artifact-specific vocabularies.

A Website can therefore opt into PWA behavior without becoming a Web application. A Web application uses the same PWA contracts while retaining its own surface, authentication, access-failure, and UI-state semantics separately.

## Installability and application icons

Planning/product PWA intent declares a Web App Manifest path, standard manifest-link requirement, secure-context requirement, and `startRouteId`. Browser install-promotion details vary by engine and belong in browser support/evidence rather than the durable contract.

The ordinary browser favicon belongs to `contracts/browser-identity.json`. PWA application icons belong here because they participate in installed-product identity and platform presentation. Prefer SVG source artwork when compatible, while explicitly declaring raster and platform compatibility intent where the product requires it.

## Offline behavior and freshness

A selected PWA product is deliberately offline-capable. `controlledRouteIds` names the shared Web routes for which the product promises an intentional network-loss experience, and `routePolicies` declares whether each route presents network unavailability or may display cached content when available.

The capability deliberately does not prescribe `network-first`, `cache-first`, `stale-while-revalidate`, or a service-worker library. `cacheStrategy` remains `implementation-defined`.

When cached content is shown offline, the product must not claim it is current when freshness cannot be established. `offlineFreshnessPolicy: "indicate-unverified"` and `freshnessUnknownPresentation: "required-visible"` make that obligation explicit. When online, cached information must be revalidated before being presented as current; `revalidatingPresentation` makes the interval observable.

These presentation obligations are intentionally artifact-neutral. A Webapp may realize them through its UI-state contract; a Website may realize them through document/browser presentation. The PWA contract verifies the observable obligation rather than taking ownership of either artifact's internal vocabulary.

## Mutations while offline

A product may declare mutations not applicable, reject them while offline, or queue them until connectivity returns. Queued work requires visible pending and failure presentations so background synchronization does not become invisible product state.

## Update lifecycle

Installed Web products can keep executing older resources after deployment. `updateDetection: "observable"` requires the product to make update detection evidentiary rather than implicit. User-confirmed activation requires a visible update-available presentation. Applying and failure presentations may also be required by the product. Immediate activation cannot simultaneously claim that activation is blocked by unsaved work.

## Evidence boundary

JSON contracts describe intended semantics; they do not prove browser behavior. Product evidence must cover the actual manifest link and served manifest, secure deployment context, icon availability/presentation, offline navigation, network-loss explanation, freshness indication/revalidation, and update behavior. The PWA evidence target families remain capability-owned and browser-backed.

Do not fabricate icon files, service workers, states, or browser evidence merely to make a template scaffold look complete.
