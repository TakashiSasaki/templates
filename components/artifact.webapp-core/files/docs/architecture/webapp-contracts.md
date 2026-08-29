# Webapp contract families

`artifact.webapp-core` owns five browser-specific contract families: `browser_identity`, `surfaces`, `routes`, `ui_states`, and `viewports`.

These families are framework-neutral but not artifact-neutral. They define observable browser experience semantics and therefore remain with the Web application artifact rather than moving into generic runtime or lifecycle components.

The component retains the current Webapp source contract versions and their registered breaking-change histories. Browser identity starts at v1. Surfaces are at v2 with their v1→v2 migration; routes are at v3 with v1→v2 and v2→v3 migrations; UI states remain at v2 with their v1→v2 migration. The composition contract manifest itself starts at a new bootstrap version because its authority model changed from a monolithic static file to deterministic generation from component registrations.

Browser identity v1 declares the ordinary browser favicon as a standards-based `icon` relationship, a primary image asset, and optional compatibility fallbacks. The seed prefers SVG (`image/svg+xml`, `sizes: ["any"]`) because scalable vector artwork is usually compact and resolution-independent, but the schema deliberately permits other `image/*` media types and concrete pixel sizes. This contract concerns browser identity only: it does not define PWA installability, a Web App Manifest, Home Screen/application icons, offline behavior, or update behavior.

Surfaces v2 uses `surfaceDependencies` for references from one declared browser-facing surface to other surface IDs in the same surfaces contract. These dependencies describe relationships among application surfaces. They are not package dependencies, runtime requirements, backend-service dependencies, operating-system processes, or process startup ordering. Validation rejects unknown surface IDs, self-dependencies, and cycles. See `docs/migrations/surfaces-v1-to-v2.md` when migrating an older seed contract.

Routes v3 makes access-failure targets explicit. A `render-state` behavior names the route-scoped access state to render, while a `redirect` behavior names the semantic destination route. URL shape, query-parameter names, cookies, sessions, framework callbacks, and other transport details remain product-owned implementation concerns.

Implementation evidence is generic, while `artifact.webapp-core` derives the Webapp-owned target inventory. Current products must cover the established behavior families (`surfaces`, `routes`, `ui_states`, and `viewports`) plus the fixed `browser_identity/proof-family/browser-identity` target. The browser-identity record is evidence of the emitted browser identity, not a restatement of `contracts/browser-identity.json`: executable proof must observe the standard favicon link and the declared asset rather than treating the contract declaration itself as implementation proof.

PWA installability, application-icon, offline/freshness, and update evidence are owned separately by `capability.pwa`. Selecting that capability adds its own proof families without moving PWA semantics into the Webapp core contract families.

## Browser-sensitive proof strength

Coverage alone is not sufficient for claims that are observable only through browser behavior. In product mode, the `browser_identity/proof-family/browser-identity` target, each `routes` target, and each `viewports` contract target whose `itemKind` is `viewport` or `input-capability` must include at least one positive and at least one negative proof declared as either `end-to-end-test` or `accessibility-test`.

A browser-level proof kind is valid for a Webapp record only when its referenced authoritative command declares `browser` execution capability. For browser-sensitive targets, at least one positive and one negative browser-level proof must be backed by such a command. Relabeling an HTTP-only or server-side test as `end-to-end-test` does not satisfy this rule.

For these targets, `unit-test`, `integration-test`, `migration-test`, `inspection`, or `other` evidence may supplement browser-level proof, but cannot be the only proof. An HTTP-only integration test therefore cannot by itself verify favicon linkage and asset retrieval, route-entry focus, responsive layout, keyboard/input behavior, zoom/scrolling interaction, or other browser-observed claims.

Planning mode applies the same proof-strength intent before records exist: every expected Webapp target needs a planning requirement, and requirements targeting browser-sensitive items must declare at least one browser-level `requiredPositiveProofKinds` value.

The proof kind remains a semantic declaration by the product. `end-to-end-test` used to satisfy this Webapp rule means a proof that exercises the supported browser interface in a browser runtime. `accessibility-test` likewise means an accessibility proof executed against the relevant browser-facing behavior. `scripts/validate_webapp_evidence.py` checks the target/proof-kind relationship and browser command capability; executable tests remain responsible for proving that the command actually observes the claimed browser behavior.

This strength rule is intentionally Webapp-specific. The generic `lifecycle.implementation-evidence` schema remains artifact-neutral, while `scripts/webapp_evidence_targets.py` and `scripts/validate_webapp_evidence.py` own the additional target inventory and semantic floor for browser-sensitive Webapp evidence.
