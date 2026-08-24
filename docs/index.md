# Composition documentation index

## Start here

- [Choosing a recipe and components](../catalog/README.md) — decide between `skill` and `webapp`, then select only the application capabilities or lifecycle behavior the product actually needs.
- [Using Composition](consumer-guide.md) — task-oriented create, inspect, update, upgrade, recovery, ownership, and conflict workflows for consumer repositories.
- [Webapp product walkthrough](guides/webapp-product-walkthrough.md) — end-to-end example from capability selection and initial materialization through consumer implementation, product evidence, validation, Policy adoption, and later update/upgrade.
- [Producing a product release](release-guide.md) — product evidence, fixed executable argv, exact candidate revision, transactional release production, rollback, and recovery.
- [Composer reference](reference/composer.md) — exact CLI modes/options, inspect states, plan fields, ownership semantics, recovery rules, and managed lifecycle diagnostics.
- [Composition overview](../README.md) — current authority, lifecycle summary, safety model, and documentation entry points.

## Composition architecture

- [Composition model](architecture/composition-model.md) — artifact, capability, lifecycle, ownership, intent, and lock semantics.
- [Composer MVP](architecture/composer-mvp.md) — resolver precedence, plan/apply safety, trust boundaries, managed reconciliation, and recovery protocol.
- [Production catalog architecture](architecture/catalog.md) — closed component and recipe inventory.
- [Generated contract manifest](architecture/generated-contract-manifest.md) — deterministic generated contract registry architecture.

## Publication boundary

- [Publication boundary](publication-catalog.md) — what this provider exposes to the integrated documentation site and why.

## Agent Skill artifact

- [Skill documentation index](../components/artifact.skill-core/files/docs/) — Skill-specific profiles, architecture, and responsibility map.
- [Skill contract scaffold](../components/artifact.skill-core/files/SKILL.md) — trigger, workflow, resources, routing, output, validation, and safety contract.

## Reusable application capabilities

- [Implementation runtime decision record](../components/capability.runtime/files/RUNTIME.md) — implementation ecosystem, commands, dependencies, environment, distribution, and deployment choices.
- [Choosing an implementation runtime](../components/capability.runtime/files/docs/runtime-selection.md) — criteria for selecting an implementation ecosystem and dependency workflow.
- [Packaged CLI interface](../components/capability.cli/files/CLI_INTERFACE.md) — caller-visible CLI behavior.
- [MCP interface](../components/capability.mcp/files/MCP_INTERFACE.md) — MCP protocol, transports, client roles, and semantic equivalence.
- [MCP transport guidance](../components/capability.mcp/files/docs/mcp-transports.md) — stdio and Streamable HTTP guidance.
- [MCP Apps extension](../components/capability.mcp-apps/files/MCP_APPS.md) — Host/View bridge, resources, sandbox, and fallback contract.
- [MCP Apps guidance](../components/capability.mcp-apps/files/docs/mcp-apps.md) — implementation guidance for MCP Apps.
- [Standalone browser interface](../components/capability.web-interface/files/WEB_INTERFACE.md) — browser-facing routing, security, health, and failure semantics.
- [Headless service interface](../components/capability.service/files/SERVICE_INTERFACE.md) — non-browser service behavior, health, security, and lifecycle.

## Web application artifact

- [Web application documentation index](../components/artifact.webapp-core/files/docs/) — Web-specific contracts and validation.
- [Web application template contract](../components/artifact.webapp-core/files/TEMPLATE.md) — framework-neutral browser product obligations.

## Reusable lifecycle contracts

- [Composition state](../components/lifecycle.composition-state/files/docs/architecture/composition-state.md) — self-contained resolved-state and material-ownership validation.
- [Contract evolution](../components/lifecycle.contract-evolution/files/docs/architecture/contract-evolution.md) — closed contract registry, schema binding, version histories, and migrations.
- [Implementation evidence](../components/lifecycle.implementation-evidence/files/docs/architecture/implementation-evidence.md) — implementation boundaries, proofs, commands, and release gates.
- [Release evidence](../components/lifecycle.release-evidence/files/docs/architecture/release-evidence.md) — revision-bound execution provenance and release decisions.
- [Release bundle](../components/lifecycle.release-bundle/files/docs/architecture/release-bundle.md) — deterministic digest-closed handoff.

## Historical provenance

- [Composition authority migration](migrations/composition-authority-migration.md) — consolidated chronology of the authority cutover, provider migration, branch retirement, and immutable PR provenance. Stage-specific implementation notes are retained only for repository maintenance and are not reader publication pages.

## Machine-readable authorities

- [Production catalog guide](../catalog/README.md) — catalog closure rules, path conventions, and consumer recipe/component selection guidance.
- [Composition schema guide](../schemas/README.md) — component, recipe, configuration, lock, transaction, and catalog schema responsibilities.
