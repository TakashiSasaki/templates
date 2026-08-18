# Webapp contract families

`artifact.webapp-core` owns four browser-specific contract families: `surfaces`, `routes`, `ui_states`, and `viewports`.

These families are framework-neutral but not artifact-neutral. They define observable browser experience semantics and therefore remain with the Web application artifact rather than moving into generic runtime or lifecycle components.

The component retains the current Webapp source contract versions, including the registered v1→v2 histories for routes and UI states. The composition contract manifest itself starts at a new bootstrap version because its authority model changed from a monolithic static file to deterministic generation from component registrations.

Implementation evidence is generic. Webapp-specific evidence coverage is imposed by `scripts/validate_webapp_evidence.py`, which derives required targets from the four domain contracts plus their registered transitions.
