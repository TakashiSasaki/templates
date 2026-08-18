# Composition documentation index

Use this index to inspect the composition source by responsibility rather than by repository path. The production component catalog remains the machine authority; this page is the provider-owned progressive-disclosure path used by humans and guided navigation.

## Start here

- [Composition source overview](../README.md) — current migration state, recipes, composer operations, and authority boundaries.
- [Publication boundary](publication-catalog.md) — what this provider exposes to the integrated documentation site and why.
- [Composition model](architecture/composition-model.md) — artifact, capability, lifecycle, ownership, intent, and lock semantics.
- [Composer MVP](architecture/composer-mvp.md) — resolver precedence, plan/apply safety, trust boundaries, and consumer validation.
- [Production catalog architecture](architecture/catalog.md) — closed component and recipe inventory.

## Agent Skill artifact

- [Skill documentation index](../components/artifact.skill-core/files/docs/) — Skill-specific profiles, architecture, and responsibility map.
- [Skill contract scaffold](../components/artifact.skill-core/files/SKILL.md) — trigger, workflow, resources, routing, output, validation, and safety contract.

## Reusable application capabilities

- [Runtime decision record](../components/capability.runtime/files/RUNTIME.md) — runtime, commands, dependencies, environment, distribution, and deployment.
- [Runtime selection guidance](../components/capability.runtime/files/docs/runtime-selection.md) — criteria for selecting an implementation ecosystem.
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

## Composition migration history

- [Skill capability migration](migrations/pr2-skill-capabilities.md) — separation of Skill semantics from generic application capabilities.
- [Webapp lifecycle migration](migrations/pr3-webapp-lifecycle.md) — separation of Web-specific semantics from reusable lifecycle contracts.

## Machine-readable authorities

- [Production catalog guide](../catalog/README.md) — catalog closure rules and path conventions.
- [Composition schema guide](../schemas/README.md) — component, recipe, configuration, lock, and catalog schema responsibilities.

Machine-readable descriptors, recipes, schemas, seed contracts, and contract schemas are declared as publication assets in `publication-catalog.json`; they are addresses/contracts rather than primary reader navigation.
