# Responsibility boundaries

The Webapp artifact owns browser experience semantics: browser identity/favicon declaration, surfaces/audiences, canonical navigation, access-failure presentation, visible states, focus/announcement behavior, viewports, input capabilities, and Web-specific cross-contract/evidence coverage.

Reusable lifecycle components own contract registration/evolution, implementation-evidence mechanics, revision-bound release evidence, and digest-closed release handoff.

Reusable application capabilities own runtime, CLI, MCP, MCP Apps, standalone operational browser exposure, headless-service contracts, and PWA semantics when selected.

The concrete product owns implementation technology, commands, providers, backend/persistence, authentication implementation, deployment, browser support matrix, observability, tests, release approval, and deployment verification.

## Implementation-evidence target ownership

The Webapp artifact evidence validator is authoritative for its current required target inventory: the fixed `browser_identity/proof-family/browser-identity` target plus the declared `routes`, `surfaces`, `ui_states`, and `viewports` items. It requires complete current-target coverage and rejects unknown Webapp-owned targets. Browser-sensitive Webapp targets additionally require browser-level proof strength; the browser-identity declaration itself is not executable favicon proof.

Evidence records for contracts owned by separately selected capabilities remain visible in the shared implementation-evidence graph but are validated by the generic lifecycle validator and the owning capability validator. In particular, `capability.pwa` owns its installability, application-icon, offline/freshness, and update proof families when selected. Webapp validation must not reject those capability-owned records merely because they are outside the Webapp-owned evidence inventory.
