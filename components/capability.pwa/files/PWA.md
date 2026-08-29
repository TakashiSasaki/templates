# Progressive Web App decision record

`capability.pwa` is the opt-in Composition capability for an installable Web application whose browser-visible behavior remains understandable during network loss and application updates.

This capability defines product semantics, not an implementation recipe. It does not choose a frontend framework, a service-worker library, a cache algorithm, a package manager, or a deployment platform.

## What the three contracts own

- `contracts/pwa-manifest.json` owns Web App Manifest intent, launch/scope binding, installability prerequisites, and cross-platform application-icon intent.
- `contracts/pwa-offline.json` owns network-loss behavior, cacheable data classifications, and freshness semantics.
- `contracts/pwa-update.json` owns caller-visible update activation and unsaved-state behavior.

The generated Composition `contracts/manifest.json` is a registry of Composition contracts. It is **not** the Web App Manifest.

## Installability and standards

Planning/product PWA intent declares a Web App Manifest path, a standard manifest link requirement, and a secure-context requirement. The launch target is expressed through `startRouteId`, so canonical path authority remains in the Webapp route contract rather than being duplicated as an unrelated string.

Browser install-promotion details vary by engine and can change over time. Keep those details in browser support/evidence rather than freezing a current Chromium, Safari, or operating-system heuristic into the Composition schema.

A service worker is not treated as the definition of installability itself. This repository nevertheless requires selected PWA products to be **offline-capable** because the product contract deliberately guarantees an intentional, non-broken network-loss experience.

Standards/background references:

- Web App Manifest: https://www.w3.org/TR/appmanifest/
- MDN, Making PWAs installable: https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable
- MDN, manifest icons: https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest/Reference/icons

## Application icons and favicon are different concerns

The ordinary browser favicon belongs to `contracts/browser-identity.json` and uses the standard `rel="icon"` relationship. PWA application icons belong here because they participate in installed-application identity and platform presentation.

Prefer SVG application artwork when it is compatible with the intended experience: a scalable vector source can avoid unnecessary duplicated raster sources and remains resolution-independent. `vectorIconPolicy` records that preference. When SVG is genuinely unsuitable, record a non-blank `vectorIconException` rather than silently abandoning the preference.

SVG alone is not assumed to produce equivalent results on every browser/OS surface. `platformCompatibility` therefore also declares product-chosen raster sizes and adaptive/icon compatibility intent. The contract does **not** freeze one vendor's current size checklist as a permanent Web standard.

For Android-like installed presentation, declare the raster sizes the product supports and whether a maskable manifest icon is required. For iOS home-screen presentation, declare a raster `apple-touch-icon` compatibility asset. WebKit documents that `apple-touch-icon` can take precedence over Web App Manifest icons on Apple platforms, so treating it as an explicit compatibility bridge makes the product identity intentional rather than accidental.

WebKit background reference: https://webkit.org/blog/12445/new-webkit-features-in-safari-15-4/

The cross-platform target is **equivalent product identity and understandable product states**, not pixel-identical browser or operating-system chrome.

## Cache implementation is deliberately not prescribed

Do not put `network-first`, `cache-first`, `stale-while-revalidate`, or a particular service-worker library into the Composition contract. `cacheStrategy` is fixed to `implementation-defined`.

Composition instead requires the externally meaningful invariants:

1. Network loss must not turn a controlled route into a broken or unexplained screen. A controlled navigation fallback and a global `networkUnavailableStateId` make the cause explicit.
2. When online, cached data must be revalidated against the authoritative source **before it is displayed as current**. The contract expresses this as `onlineFreshnessPolicy: "revalidate-before-display"`.
3. During that online revalidation interval, a global `revalidatingStateId` gives the application an intentional visible state instead of silently showing possibly stale data.
4. When offline, cached information may be useful, but the application cannot claim it is current when freshness cannot be established. `offlineFreshnessPolicy: "indicate-unverified"` plus `freshnessUnknownStateId` makes that uncertainty visible.
5. Cacheable data classifications must be a subset of the owning Webapp surface's declared `dataClassifications`; the PWA contract does not invent a second security/data-classification authority.

These rules allow implementations to choose the cache mechanics that fit their workload while preserving the same caller-visible correctness properties.

## Mutations while offline

A product may reject mutations while offline, declare mutations not applicable, or queue them until connectivity returns. When it queues work, pending and failure states are required so background synchronization does not become invisible product state.

## Update lifecycle

Installed Web applications can keep executing older resources after a new deployment. The update contract therefore records activation behavior and unsaved-change policy independently of the service-worker implementation.

If update activation is user-confirmed, the application declares an update-available state. Applying/failure states, when declared, are global product states. Immediate activation cannot simultaneously claim that activation is blocked by unsaved work.

## Evidence boundary

JSON contracts describe intended semantics; they do not prove the browser actually implements them. Product evidence must later cover the actual manifest link and served manifest, secure deployment context, icon availability/presentation, offline navigation behavior, network-loss explanation, freshness indications, and update behavior.

Do not fabricate icon files, service workers, or browser evidence merely to make a template scaffold look complete.
