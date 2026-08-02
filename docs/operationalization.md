# Operationalize a generated repository

This guide describes how to turn the framework-neutral Webapp template into one product repository with explicit implementation and operational ownership. It complements [TEMPLATE.md](../TEMPLATE.md) and does not select a framework, package manager, backend, authentication provider, browser matrix, or deployment platform.

The template contracts describe externally observable behavior. The generated repository must provide the concrete implementation and evidence that the implementation satisfies those declarations.

## 1. Freeze the template baseline

Start from one known `webapp` revision and record that revision in the generated repository's setup notes or change log. Copy the template-owned contracts, schemas, validator, tests, and validation instructions as one coherent baseline.

Do not combine the unrelated `webapp` and `policy` histories merely to share files. Do not copy framework starters, deployment workflows, or coding-agent policy from an unrelated branch as if they were part of this template.

Before customization, choose and provision the contract-validation path before invoking it.

If the generated repository retains the shipped Python validator:

- retain `requirements-dev.lock` (or an intentionally updated equivalent lock) for the validator dependencies;
- create a separate isolated validator environment from that lock;
- run both validator entry points and the template test suite with that environment's interpreter;
- keep this environment separate from the product environment and follow the repository's documented clean-environment procedure.

The product lockfile does not provision the shipped validator, and globally installed Python packages are not an acceptable substitute for the reviewed validator environment.

If the generated repository replaces the shipped validator with an equivalent verified integration, record that integration's isolated dependencies, command, and evidence instead. Do not invoke the shipped Python entry points in that validation path.

## 2. Select one product toolchain

Make the product choices that the template intentionally leaves open:

- one application framework or browser-platform-only implementation;
- one package manager and authoritative lockfile;
- one client-side, server-side, or hybrid rendering model;
- one backend and API topology;
- one authentication and authorization design;
- one persistence model;
- one deployment target;
- one observability approach;
- one supported browser matrix;
- one offline and installability scope.

Record the authoritative build, test, lint, and deployment commands. Remove competing manifests, lockfiles, framework starters, and deployment configurations rather than retaining them as unresolved alternatives.

The template-maintainer Python environment validates the template contracts. It is not automatically the product runtime. A product may retain, replace, or separately invoke the validator, but the contract semantics and failure evidence must remain explicit.

## 3. Customize the contract set

Replace the example declarations in `contracts/` with product-specific values while preserving the manifest as the inventory source of truth.

For each change:

1. Keep every retained document and schema registered in `contracts/manifest.json`.
2. Keep the document `$schema` and `schemaVersion` consistent with the manifest.
3. Declare every externally observable application surface and canonical route.
4. Keep route-to-surface and route-to-UI-state references valid.
5. Define aliases and canonical paths without collisions.
6. Describe authentication return behavior and deep-link expectations for protected routes.
7. Declare loading, empty, partial, error, offline, and access states that users can observe.
8. Declare viewport lower bounds and input capabilities independently.
9. Update schema versions and migration notes when the meaning of an existing contract changes.

A new contract family belongs in this set only when its semantics are framework-neutral, externally observable, product-repository declarations can be authoritative, and local cross-file validation can reject its failure cases. Otherwise, keep the concern product-owned and document it in the generated repository.

## 4. Connect implementation to contracts

Map each contract declaration to the implementation boundary that is responsible for it. The mapping can be a table, test fixture metadata, or another repository-local document, but it must be reviewable.

At minimum, the implementation must make evidence available for:

| Contract concern | Product evidence |
| --- | --- |
| Surfaces | rendered entry points, audience checks, trusted authentication and authorization enforcement, data-classification handling, and dependency behavior |
| Routes | canonical navigation, aliases or redirects, browser history, deep links, authentication return, document titles, and focus targets |
| UI states | deterministic rendering and recovery actions for each declared state |
| Viewports | responsive behavior at declared lower bounds and supported input capabilities, including zoom and orientation requirements |

Route names and directory names are not authorization. Enforce access decisions in trusted server or application boundaries, and test that an authenticated principal cannot cross an authorization boundary by changing a path, identifier, or client-side state.

## 5. Build implementation evidence

Add product-owned tests that exercise the real implementation path. A useful evidence matrix maps each declaration to:

- the implementation entry point;
- the test or fixture that exercises it;
- the expected observable result;
- the failure or recovery behavior;
- the command that runs the evidence.

Include positive and negative cases. Examples include unauthenticated access to a public surface, denied access to a protected surface, direct navigation to a deep link, an authentication return to the original route, every declared UI state, alias collision prevention, keyboard navigation, zoom, narrow and wide layouts, offline or partial failure, and recovery actions.

The template validator proves that the declarations are structurally and cross-contract valid. It does not prove that product code actually implements them; that proof remains in the generated repository's tests.

## 6. Integrate validation into CI

Run validation from a clean, documented environment and keep the commands reproducible:

1. create the product's isolated environment;
2. install the product lockfile without undeclared dependency inputs;
3. if the shipped validator is retained, run both supported entry points from its isolated environment; otherwise run the product repository's equivalent verified validation command and preserve the semantic and failure-case evidence mapping;
4. run product unit, integration, accessibility, and end-to-end tests;
5. run lint, type, build, and security checks selected by the product toolchain;
6. publish diagnostics and evidence without exposing secrets.

Keep template contract validation separate from product runtime startup and deployment. A product test may start the real application, but a validator-only job should not silently depend on a local developer process, an undeclared service, or production credentials.

## 7. Define release and deployment ownership

The generated repository owns deployment configuration, environment management, migrations, rollback, observability, and release approval. Before treating it as operational, document:

- how the deployed revision is identified;
- which contract and schema versions it serves;
- how backward-incompatible changes are migrated;
- how health and readiness differ from user-facing error states;
- how secrets, logs, and diagnostics are redacted;
- how rollback preserves or restores contract compatibility;
- which evidence gates release.

The Webapp template does not enable a deployment target or choose a production topology. Those decisions must be explicit in the generated repository and validated by its own workflow.

## Completion checklist

A generated repository is ready for independent product review when:

- one product toolchain and one authoritative lockfile are selected;
- example contracts have been replaced or explicitly retained as product declarations;
- the closed manifest, schemas, and document metadata agree;
- all canonical surfaces, routes, states, viewports, and input capabilities are declared;
- trusted authentication and authorization enforcement is tested;
- implementation evidence covers the declared behavior and failure paths;
- if the shipped validator is retained, both supported entry points and product tests pass in CI; otherwise the equivalent verified validation command and product tests pass with preserved contract semantics and failure evidence;
- build, deployment, migration, rollback, observability, and release ownership are documented;
- template-only guidance and unused alternatives have been removed.
