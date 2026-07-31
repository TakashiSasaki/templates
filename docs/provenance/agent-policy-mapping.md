# Mapping from agent-policy to the webapp template

`TakashiSasaki/agent-policy` remains the authority for reusable coding-agent policy. This template does not fork those policy texts. It supplies repository artifacts that make applicable rules concrete and testable.

## Responsibility boundary

| Concern | Authority |
|---|---|
| Rule identifiers, severity, profile membership, rendering, lock generation, adoption, and toolchain pinning | `TakashiSasaki/agent-policy` |
| Product-specific surfaces, routes, roles, data classifications, viewports, browser requirements, and operational commands | Repository created from this template |
| Reference schemas, validation entry points, tests, CI structure, and customization guidance | `TakashiSasaki/templates:webapp` |

## Web-application profile mapping

| `agent-policy` rule | Foundation artifact | What remains product-specific |
|---|---|---|
| `interfaces.define-surface-boundaries` | `contracts/surfaces.json`, `schemas/surfaces.schema.json` | Actual audiences, authorization roles, sensitivity, and trusted enforcement |
| `interfaces.isolate-surface-dependencies` | Surface identifiers and dependency declarations in `contracts/surfaces.json` | Framework entry points, bundles, initialization, and failure isolation tests |
| `interfaces.make-navigation-intentional` | `contracts/routes.json`, `schemas/routes.schema.json` | Canonical paths, aliases, redirects, deep links, and authentication return behavior |
| `interfaces.model-user-visible-states` | `contracts/ui-states.json`, `schemas/ui-states.schema.json` | Product terminology, recovery actions, partial-data rules, and UI implementation |
| `interfaces.preserve-accessible-interaction` | Required accessibility expectations in route and state contracts | Semantic implementation, keyboard behavior, focus restoration, and automated/manual tests |
| `interfaces.separate-diagnostics` | Surface purpose and audience declarations | Concrete status, developer, and administrative endpoints and their access controls |
| `interfaces.keep-surface-contracts-synchronized` | A single validation entry point and CI | Implementation, deployment, documentation, and migration synchronization |
| `interfaces.adapt-layout-to-content` | `contracts/viewports.json`, `schemas/viewports.schema.json` | Product layout breakpoints, content constraints, device capabilities, and visual tests |

## Core and security profiles

The later `agent-policy` integration should select `core`, `security-baseline`, and `web-application`. The repository-specific policy must define authoritative verification commands, generated-file ownership, destructive-action boundaries, secret handling, input validation, and compatibility requirements.

A `.agent-policy.yml`, generated `AGENTS.md`, and `.agent-policy.lock` are intentionally deferred until the project-policy text and executable verification command are stable enough to generate and check together. Handwritten approximations of generated files must not be committed.
