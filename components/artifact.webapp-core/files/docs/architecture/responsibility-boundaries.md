# Responsibility boundaries

The Webapp artifact owns browser experience semantics: browser identity/favicon declaration, surfaces/audiences, canonical navigation, access-failure presentation, visible states, focus/announcement behavior, viewports, input capabilities, and Web-specific cross-contract/evidence coverage.

Reusable lifecycle components own contract registration/evolution, implementation-evidence mechanics, revision-bound release evidence, and digest-closed release handoff.

Reusable application capabilities own runtime, CLI, MCP, MCP Apps, standalone operational browser exposure, and headless-service contracts when selected.

The concrete product owns implementation technology, commands, providers, backend/persistence, authentication implementation, deployment, browser support matrix, observability, tests, release approval, and deployment verification.

## Implementation-evidence target ownership

The current Webapp artifact evidence validator is authoritative for the established behavior target families (`routes`, `surfaces`, `ui_states`, and `viewports`) plus the fixed `browser_identity/proof-family/browser-identity` target. It requires complete coverage and rejects unknown targets inside those families. Browser identity evidence requires browser-backed executable proof of the emitted standard favicon link and declared asset rather than treating the browser-identity contract declaration itself as implementation proof. Evidence records for contracts owned by separately selected capabilities remain visible in the shared implementation-evidence graph but are validated by the generic lifecycle validator and the owning capability validator; Webapp validation must not reject them merely because they are outside the current Webapp evidence target inventory.
