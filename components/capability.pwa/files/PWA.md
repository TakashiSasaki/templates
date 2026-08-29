# Progressive Web App capability

This seed records product-owned Progressive Web App decisions. Composition owns the contract schemas and validation; the product owns the deployed manifest, service worker, cache/storage implementation, and UI implementation.

`contracts/pwa-manifest.json` describes Web App Manifest semantics. It is not the deployed Web App Manifest file and it is distinct from Composition's generated `contracts/manifest.json` contract registry.

`contracts/pwa-offline.json` makes offline support explicit. `network-only` is valid and does not imply a service worker. `offline-capable` declares the URL-control scope, routes expected to remain usable, surface data classifications that may be cached, read freshness behavior, and offline mutation behavior. The contract does not prescribe Workbox, Cache API wrappers, IndexedDB libraries, or another implementation technology.

`contracts/pwa-update.json` describes caller-visible update activation and unsaved-state protection. It does not prescribe service-worker source layout or update-check implementation.

Browser-vendor install-promotion heuristics change over time and are not frozen into these contracts. Product browser support and deployment verification remain product-owned. Executable browser/PWA proof is a separate evidence concern; this semantic capability does not fabricate proof merely because the contracts are present.
