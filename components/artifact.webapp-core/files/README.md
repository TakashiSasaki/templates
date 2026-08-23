# Web application composition recipe

This repository is a framework-neutral Web application contract scaffold produced by the `webapp` composition recipe.

`artifact.webapp-core` owns browser-specific semantics: surfaces, canonical routes, visible UI states, responsive viewports/input capabilities, and their cross-contract validation. Generic contract evolution, implementation evidence, release evidence, and release-bundle behavior come from reusable `lifecycle.*` components.

The scaffold intentionally does not choose a frontend framework, rendering model, package manager, backend, persistence layer, authentication provider, deployment platform, browser matrix, or observability vendor.

## Contracts

- `contracts/surfaces.json` — browser-facing surface boundaries and audiences.
- `contracts/routes.json` — canonical navigation plus access-failure behavior and semantic state/route targets.
- `contracts/ui-states.json` — reusable visible states and recovery/focus behavior.
- `contracts/viewports.json` — responsive lower bounds and input capabilities.
- `contracts/manifest.json` — generated closed registry from resolved component metadata.
- lifecycle contracts appear because Webapp requires the release-lifecycle chain.

## Optional application capabilities

The Webapp recipe may additionally select runtime, CLI, MCP, MCP Apps, standalone operational Web exposure, or headless service capabilities. None is required merely because the artifact is browser-facing; a static/CDN Web application remains valid without an application runtime component.

## Validation

Install `.template-composition/requirements-validation.lock`, then run the Webapp and lifecycle validators. The supplied GitHub Actions workflow performs the complete template-mode validation sequence.
