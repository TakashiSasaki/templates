# Responsibility boundaries

The Webapp artifact owns browser experience semantics: surfaces/audiences, canonical navigation, access-failure presentation, visible states, focus/announcement behavior, viewports, input capabilities, and Web-specific cross-contract/evidence coverage.

Reusable lifecycle components own contract registration/evolution, implementation-evidence mechanics, revision-bound release evidence, and digest-closed release handoff.

Reusable application capabilities own runtime, CLI, MCP, MCP Apps, standalone operational browser exposure, and headless-service contracts when selected.

The concrete product owns implementation technology, commands, providers, backend/persistence, authentication implementation, deployment, browser support matrix, observability, tests, release approval, and deployment verification.

## Implementation-evidence target ownership

The Webapp artifact validator is authoritative only for Webapp-owned target families (`routes`, `surfaces`, `ui_states`, and `viewports`). It requires complete coverage and rejects unknown targets inside those families. Evidence records for contracts owned by separately selected capabilities remain visible in the shared implementation-evidence graph but are validated by the generic lifecycle validator and the owning capability validator; Webapp validation must not reject them merely because they are outside the Webapp target inventory.
