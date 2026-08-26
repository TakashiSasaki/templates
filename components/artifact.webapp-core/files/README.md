# Web application composition recipe

This repository is a framework-neutral Web application contract scaffold produced by the `webapp` composition recipe.

## New to Composition? Start with the worked example

If you are creating your first Web application with this repository, do not start by reverse-engineering the contracts below. Follow the [Webapp product walkthrough](https://templates.moukaeritai.work/composition/use/webapp-product-walkthrough/) from a separate product repository. It starts with prerequisites and Composition installation, creates `composition.json`, walks through `inspect -> plan -> apply -> validate`, explains exactly which generated files you may edit, and then continues into product implementation and evidence.

The first milestone in that walkthrough is a **valid Composition scaffold**, not a completed Web application. Product implementation and product verification remain consumer responsibilities.

The evidence scaffold is a projection, not an authority. Its per-target and requirement statuses are `[verified]`, `[missing]`, or `[deferred]`; edit and validate the consumer-owned `contracts/implementation-evidence.json` to make evidence authoritative.

## What the Webapp recipe defines

`artifact.webapp-core` owns browser-specific semantics: surfaces, canonical routes, visible UI states, responsive viewports/input capabilities, and their cross-contract validation. Generic contract evolution and implementation evidence are part of the Webapp baseline through reusable `lifecycle.*` components. Release execution, release evidence, and release-bundle behavior are added only when the consumer explicitly selects `lifecycle.release-bundle`.

The scaffold intentionally does not choose a frontend framework, rendering model, package manager, backend, persistence layer, authentication provider, deployment platform, browser matrix, or observability vendor.

## Contracts

- `contracts/surfaces.json` — browser-facing surface boundaries and audiences.
- `contracts/routes.json` — canonical navigation plus access-failure behavior and semantic state/route targets.
- `contracts/ui-states.json` — reusable visible states and recovery/focus behavior.
- `contracts/viewports.json` — responsive lower bounds and input capabilities.
- `contracts/implementation-evidence.json` — baseline mapping from Webapp contract targets to implementation/proof evidence.
- `contracts/manifest.json` — generated closed registry from resolved component metadata.
- release execution/evidence/bundle contracts appear only when `lifecycle.release-bundle` is selected.

## Optional capabilities and release lifecycle

The Webapp recipe may additionally select runtime, CLI, MCP, MCP Apps, standalone operational Web exposure, or headless service capabilities. None is required merely because the artifact is browser-facing; a static/CDN Web application remains valid without an application runtime component.

Select `lifecycle.release-bundle` when the repository needs the Composition-managed release workflow. Its dependency closure adds release execution and revision-bound release evidence while reusing the baseline implementation-evidence and contract-evolution components.

## Validation

Run `python scripts/scaffold_webapp_evidence.py` to refresh the non-canonical worklist, then run `python .template-composition/validate.py .`. The validator automatically provisions and reuses an isolated validation runtime from the exact dependency set carried by the managed Composition validation registry; no manual validation-environment installation is required. Validation is selected from the resolved component set in the Composition lock: a minimal or runtime-backed Webapp does not run release validators, while a release-ready Webapp that selects `lifecycle.release-bundle` does.
