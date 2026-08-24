# Webapp contract families

`artifact.webapp-core` owns four browser-specific contract families: `surfaces`, `routes`, `ui_states`, and `viewports`.

These families are framework-neutral but not artifact-neutral. They define observable browser experience semantics and therefore remain with the Web application artifact rather than moving into generic runtime or lifecycle components.

The component retains the current Webapp source contract versions and their registered breaking-change histories. Surfaces are at v2 with their v1→v2 migration; routes are at v3 with v1→v2 and v2→v3 migrations; UI states remain at v2 with their v1→v2 migration. The composition contract manifest itself starts at a new bootstrap version because its authority model changed from a monolithic static file to deterministic generation from component registrations.

Surfaces v2 uses `surfaceDependencies` for references from one declared browser-facing surface to other surface IDs in the same surfaces contract. These dependencies describe relationships among application surfaces. They are not package dependencies, runtime requirements, backend-service dependencies, operating-system processes, or process startup ordering. Validation rejects unknown surface IDs, self-dependencies, and cycles. See `docs/migrations/surfaces-v1-to-v2.md` when migrating an older seed contract.

Routes v3 makes access-failure targets explicit. A `render-state` behavior names the route-scoped access state to render, while a `redirect` behavior names the semantic destination route. URL shape, query-parameter names, cookies, sessions, framework callbacks, and other transport details remain product-owned implementation concerns.

Implementation evidence is generic. Webapp-specific evidence coverage is imposed by `scripts/validate_webapp_evidence.py`, which derives required targets from the four domain contracts plus their registered transitions.

## Browser-sensitive proof strength

Coverage alone is not sufficient for claims that are observable only through browser behavior. In product mode, each `viewports` contract target whose `itemKind` is `viewport` or `input-capability` must include at least one positive and at least one negative proof declared as either `end-to-end-test` or `accessibility-test`.

For these targets, `unit-test`, `integration-test`, `migration-test`, `inspection`, or `other` evidence may supplement browser-level proof, but cannot be the only proof. An HTTP-only integration test therefore cannot by itself verify responsive layout, keyboard/input behavior, zoom/scrolling interaction, or other browser-observed viewport claims.

The proof kind remains a semantic declaration by the product. `end-to-end-test` used to satisfy this Webapp rule means a proof that exercises the supported browser interface in a browser runtime; relabeling a server-side or HTTP-only test does not make it valid evidence. `accessibility-test` likewise means an accessibility proof executed against the relevant browser-facing behavior. The validator checks the declared target/proof-kind relationship; it does not inspect or infer the internals of the referenced test implementation.

This strength rule is intentionally Webapp-specific. The generic `lifecycle.implementation-evidence` schema remains artifact-neutral, while `scripts/validate_webapp_evidence.py` owns the additional semantic floor for browser-sensitive Webapp targets.
