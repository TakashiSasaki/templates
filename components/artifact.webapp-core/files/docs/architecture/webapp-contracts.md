# Webapp contract families

`artifact.webapp-core` owns four browser-specific contract families: `surfaces`, `routes`, `ui_states`, and `viewports`.

These families are framework-neutral but not artifact-neutral. They define observable browser experience semantics and therefore remain with the Web application artifact rather than moving into generic runtime or lifecycle components.

The component retains the current Webapp source contract versions and their registered breaking-change histories. Routes are at v3 with v1→v2 and v2→v3 migrations; UI states remain at v2 with their v1→v2 migration. The composition contract manifest itself starts at a new bootstrap version because its authority model changed from a monolithic static file to deterministic generation from component registrations.

Routes v3 makes access-failure targets explicit. A `render-state` behavior names the route-scoped access state to render, while a `redirect` behavior names the semantic destination route. URL shape, query-parameter names, cookies, sessions, framework callbacks, and other transport details remain product-owned implementation concerns.

Implementation evidence is generic. Webapp-specific evidence coverage is imposed by `scripts/validate_webapp_evidence.py`, which derives required targets from the four domain contracts plus their registered transitions.
