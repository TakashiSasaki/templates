# Composition documentation index

## Start here

- [Choose Website or Web application](guides/website-webapp-selection.md) — Browser-facing product? Classify the artifact from product identity and caller-visible behavior, not static/dynamic rendering, hosting, runtime, or PWA technology.
- [Website product walkthrough](guides/website-product-walkthrough.md) — Creating your first content/document-oriented Website? Follow Project Docs from a separate repository through `website` selection, `inspect -> plan -> apply -> validate`, Website contracts, planning/product evidence, implementation, and browser proof.
- [Webapp product walkthrough](guides/webapp-product-walkthrough.md) — Creating your first Web application? Start here. Follow one zero-to-one Task Ledger path from a separate product repository through installation, `composition.json`, `inspect -> plan -> apply -> validate`, ownership, implementation, product tests, evidence, optional Policy, and later update/upgrade.
- [Composition concepts for first-time readers](guides/composition-concepts.md) — Optional mental-model guide for repository-specific uses of recipe, artifact, component, contract, material, and lock. You do not need to read it before following a first-use walkthrough.
- [Evaluating Composition](evaluation-guide.md) — canonical independent clean-room evaluator entry point: follow the formal protocol, use the scorecard guide, validate the machine-readable scorecard against its schema, and preserve transcript chronology.
- [Using Composition](consumer-guide.md) — task-oriented create, inspect, update, upgrade, recovery, ownership, and conflict workflows for consumer repositories. Human terminal users may add `--format human` to `inspect`, `plan`, `apply`, or `validate` for concise next-action guidance; automation should continue to use the default JSON output.
- [Choosing a recipe and components](../catalog/README.md) — choose `skill`, `website`, or `webapp`, then select only the capabilities or lifecycle behavior the product actually needs.
- [Producing a product release](release-guide.md) — product evidence, fixed executable argv, exact candidate revision, transactional release production, rollback, and recovery.
- [Composer reference](reference/composer.md) — exact CLI modes/options, inspect states, plan fields, ownership semantics, recovery rules, and managed lifecycle diagnostics.
- [Composition overview](../README.md) — current authority, lifecycle summary, safety model, and documentation entry points.

## Composition architecture

- [Composition model](architecture/composition-model.md) — foundation, artifact, capability, lifecycle, ownership, intent, and lock semantics.
- [Composer architecture](architecture/composer-mvp.md) — resolver precedence, plan/apply safety, trust boundaries, managed reconciliation, and recovery protocol.
- [Production catalog architecture](architecture/catalog.md) — closed component and recipe inventory.
- [Generated contract manifest](architecture/generated-contract-manifest.md) — deterministic generated contract registry architecture.

## Publication boundary

- [Publication boundary](publication-catalog.md) — what this provider exposes to the integrated documentation site and why.

## Agent Skill artifact

- [Skill documentation index](../components/artifact.skill-core/files/docs/) — Skill-specific profiles, architecture, and responsibility map.
- [Skill contract scaffold](../components/artifact.skill-core/files/SKILL.md) — trigger, workflow, resources, routing, output, validation, and safety contract.

## Shared Web foundation

- [Website or Web application decision guide](guides/website-webapp-selection.md) — artifact selection and the boundary between shared Web semantics and artifact-specific semantics.
- [Web URL and path design guidance](../components/foundation.web/files/docs/url-path-design-guidance.md) — advisory naming, persistence, hierarchy, query/fragment, and implementation-independence guidance that does not change route conformance.
- [Shared browser identity contract](../components/foundation.web/files/contracts/browser-identity.json) — product-neutral browser identity.
- [Shared routes contract](../components/foundation.web/files/contracts/routes.json) — generalized canonical paths, aliases, deep-link expectations, and navigation accessibility.
- [Shared viewports contract](../components/foundation.web/files/contracts/viewports.json) — responsive viewport and input-capability expectations.

## Website artifact

- [Website product walkthrough](guides/website-product-walkthrough.md) — canonical first-use path for a concrete content/document-oriented Website.
- [Website component descriptor](../components/artifact.website-core/component.json) — Website artifact dependencies, contracts, validators, and materials.
- [Website structure contract](../components/artifact.website-core/files/contracts/site-structure.json) — page inventory, hierarchy, home page, primary navigation, and shared-route bindings.
- [Website document metadata contract](../components/artifact.website-core/files/contracts/document-metadata.json) — titles, descriptions, language, canonical-path policy, indexability, and social-preview intent.
- [Website discovery contract](../components/artifact.website-core/files/contracts/site-discovery.json) — canonical origin, robots, sitemap, and feed discovery semantics.

## Web application artifact

- [Webapp product walkthrough](guides/webapp-product-walkthrough.md) — canonical first-use path for a concrete Web application.
- [Web application documentation index](../components/artifact.webapp-core/files/docs/) — application-specific contracts and validation on top of the shared Web foundation.
- [Web application template contract](../components/artifact.webapp-core/files/TEMPLATE.md) — framework-neutral browser application obligations.

## Reusable application capabilities

- [Implementation runtime decision record](../components/capability.runtime/files/RUNTIME.md) — implementation ecosystem, commands, dependencies, environment, distribution, and deployment choices.
- [Choosing an implementation runtime](../components/capability.runtime/files/docs/runtime-selection.md) — criteria for selecting an implementation ecosystem and dependency workflow.
- [Progressive Web App capability](../components/capability.pwa/files/PWA.md) — artifact-neutral installability, offline/freshness, application identity, and update behavior for Website or Webapp products.
- [Packaged CLI interface](../components/capability.cli/files/CLI_INTERFACE.md) — caller-visible CLI behavior.
- [MCP interface](../components/capability.mcp/files/MCP_INTERFACE.md) — MCP protocol, transports, client roles, and semantic equivalence.
- [MCP transport guidance](../components/capability.mcp/files/docs/mcp-transports.md) — stdio and Streamable HTTP guidance.
- [MCP Apps extension](../components/capability.mcp-apps/files/MCP_APPS.md) — Host/View bridge, resources, sandbox, and fallback contract.
- [MCP Apps guidance](../components/capability.mcp-apps/files/docs/mcp-apps.md) — implementation guidance for MCP Apps.
- [Standalone browser interface](../components/capability.web-interface/files/WEB_INTERFACE.md) — browser-facing routing, security, health, and failure semantics.
- [Headless service interface](../components/capability.service/files/SERVICE_INTERFACE.md) — non-browser service behavior, health, security, and lifecycle.

## Reusable lifecycle contracts

- [Composition state](../components/lifecycle.composition-state/files/docs/architecture/composition-state.md) — self-contained resolved-state and material-ownership validation.
- [Contract evolution](../components/lifecycle.contract-evolution/files/docs/architecture/contract-evolution.md) — closed contract registry, schema binding, version histories, and migrations.
- [Implementation evidence](../components/lifecycle.implementation-evidence/files/docs/architecture/implementation-evidence.md) — implementation boundaries, proofs, commands, and release gates.
- [Release evidence](../components/lifecycle.release-evidence/files/docs/architecture/release-evidence.md) — revision-bound execution provenance and release decisions.
- [Release bundle](../components/lifecycle.release-bundle/files/docs/architecture/release-bundle.md) — deterministic digest-closed handoff.

## Historical provenance

- [Composition authority migration](migrations/composition-authority-migration.md) — consolidated chronology of the authority cutover, provider migration, branch retirement, and immutable PR provenance. Stage-specific implementation notes are retained only for repository maintenance and are not reader publication pages.

## Machine-readable authorities

- [Production catalog guide](../catalog/README.md) — catalog closure rules, path conventions, consumer recipe/component selection guidance.
- [Composition schema guide](../schemas/README.md) — component, recipe, configuration, lock, transaction, and catalog schema responsibilities.
