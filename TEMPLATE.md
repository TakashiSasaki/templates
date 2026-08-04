# Template scope and customization contract

## Purpose

This branch defines the repository-level foundation for browser-facing web applications. It starts with contracts that remain useful across frameworks and deployment platforms.

## Included in the foundation

- explicit application-surface classification;
- canonical route and navigation contracts with explicit access-failure presentation behavior;
- user-visible loading, empty, partial, error, offline, and recovery states with explicit route or global ownership scope;
- supported viewport declarations;
- machine-readable implementation-evidence requirements and release-gate references;
- a closed manifest that inventories active contracts, retired-family tombstones, schemas, stable migration slugs, version histories, and migration artifacts;
- JSON Schemas for those contracts;
- local validation, tests, and CI;
- an explicit boundary between reusable template contracts and product-owned implementation decisions.

## Responsibility boundary

This template owns the reusable shape and validation of Web-application design contracts. A repository created from the template owns the concrete product declarations, implementation, deployment, and evidence that the implementation satisfies those declarations.

The pinned Python environment in `requirements-dev.lock` and `.github/workflows/contract-validation.yml` is the branch-maintainer validation toolchain. It verifies the template-owned contracts and tests; it does not select the generated product's framework, runtime, package manager, browser support, or deployment mechanism.

Coding-agent operating rules, source-control procedures, approval workflows, repository governance, and unrelated policy tooling are outside the Webapp template contract. A generated repository may adopt such mechanisms independently, but that adoption is not a prerequisite for using or validating this template.

## Intentionally undecided

The foundation does not select or emulate all possible implementations. A concrete repository created from this template must make one intentional choice for each retained concern:

- application framework or browser-platform-only implementation;
- package manager and lockfile;
- client-side, server-side, or hybrid rendering;
- backend and API topology;
- authentication and authorization provider;
- persistence model;
- deployment target;
- observability platform;
- supported browser matrix;
- offline and installability scope.

Do not retain multiple competing manifests, lockfiles, framework starters, or deployment configurations as placeholders.

## Required customization

Before a generated repository is treated as operational:

1. Replace example names and descriptions in `contracts/` with product-specific values.
2. Declare every externally observable surface and canonical route, and ensure each declared surface is owned by at least one canonical route.
3. Declare unauthenticated and forbidden access-failure behavior for every route, and keep rendered access states consistent with those behaviors.
4. Classify each UI state as `route` or `global`; ensure every route-scoped state is referenced by at least one route and no global state is listed by a route.
5. Keep `contracts/manifest.json` synchronized when adding, moving, retiring, or versioning contract families, and preserve complete contiguous version histories.
6. Assign one stable `migrationSlug` to each family and preserve it across document or schema moves.
7. Classify every transition after version 1 as `additive` or `breaking` and register its deterministic migration artifact.
8. Move a retired non-core family to `retiredContracts`, remove its live files, and preserve its tombstone, stable slug, complete history, breaking retirement migration, deployment implications, and rollback procedure.
9. Preserve stable contract and entity identifiers unless an explicit breaking migration accounts for every reference.
10. Define trusted authorization enforcement independently of route or directory names.
11. Select one implementation toolchain and record authoritative build, test, lint, and deployment commands.
12. Change `contracts/implementation-evidence.json` from `mode: template` to `mode: product` and replace every required boundary, proof, command, and release gate with verified repository-local evidence.
13. Add implementation-level tests that prove the declared contracts and ensure every proof command is executed by a selected release gate.
14. Remove template-only guidance that no longer applies.

The complete generated-repository sequence, including contract customization, implementation evidence, CI integration, and deployment ownership, is described in [`docs/operationalization.md`](docs/operationalization.md).

## Contract-set completeness

`contracts/manifest.json` is the repository-local inventory of domain contracts. Active entries record each contract identifier, document path, schema path, stable migration slug, current document schema version, complete version history, purpose, and migration for every transition after version 1. `retiredContracts` preserves the same historical identity plus the last live document version and the next breaking retirement version without requiring live document or schema files. The manifest also records its own bootstrap-format history.

Validation rejects:

- active contract or schema files that are present but not registered;
- registered active files that are missing or symbolic links;
- duplicate identities, document paths, schema paths, or migration slugs across active and retired entries;
- paths outside the repository-owned contract and schema directories;
- active document `$schema` declarations or `schemaVersion` values that differ from the manifest;
- noncontiguous histories or histories that do not end at the current or retirement version;
- retirement versions that are not exactly one greater than the last live version;
- retirement histories whose final transition is not breaking;
- migration paths that do not match their stable slug and version transition;
- missing, unreadable, visually empty, symbolic-link, non-regular, duplicate, or unregistered migration artifacts, regardless of extension;
- declared surfaces that are not owned by any canonical route;
- access-failure behavior that is inconsistent with route authentication or surface authorization;
- rendered access failures without their corresponding route-scoped UI states;
- redirected or inapplicable access failures that still declare those UI states;
- route-scoped UI states that are not declared by any route;
- global UI states that are declared by a route;
- missing, duplicate, or unknown implementation-evidence targets;
- implementation proofs that reference unknown commands or gates;
- product evidence whose selected release gates do not execute its proof commands; and
- template-mode documents that claim verified implementation locations, product commands, or release gates.

The manifest and its schema are validator bootstrap metadata and are not product-domain contracts. See `docs/architecture/contract-completeness.md` for the current coverage boundary and the criteria for adding another contract family.

## Route-path representation

`contracts/routes.json` records canonical URL pathnames, not arbitrary URLs or framework route-pattern syntax. The foundation accepts `/` or slash-separated, non-empty segments composed only of ASCII URL-unreserved characters: letters, digits, `.`, `_`, `~`, and `-`. A segment may not be exactly `.` or `..`.

Raw whitespace, control characters, non-ASCII characters, percent encoding, query strings, fragments, backslashes, empty segments, and trailing slashes are rejected. Products that require internationalized paths, encoded octets, parameters, query contracts, or fragment contracts must add a normalization model and collision tests before relaxing this conservative representation.

## Route access-failure representation

Every route declares `accessFailures.unauthenticated` and `accessFailures.forbidden`. Each condition uses one of three values:

- `render-state`: retain the route presentation boundary and render the corresponding route-scoped UI state;
- `redirect`: leave the current route presentation through a redirect;
- `not-applicable`: the condition cannot occur under the route and owning-surface access declarations.

Required authentication makes the unauthenticated condition applicable. Optional or absent authentication makes it inapplicable. Role authorization makes the forbidden condition applicable; public or authenticated authorization makes it inapplicable.

`render-state` requires `unauthorized` for the unauthenticated condition or `forbidden` for the forbidden condition in the route's `states` collection. `redirect` and `not-applicable` prohibit the corresponding state reference.

`authenticationReturn` remains independent: it describes whether successful authentication returns to the original route. It does not choose the initial failure behavior, redirect destination, identity provider, or authorization recovery flow. Those implementation details remain product-owned.

Routes schema version 2 introduced this required declaration. Repositories migrating from version 1 must follow [`docs/migrations/routes-v1-to-v2.md`](docs/migrations/routes-v1-to-v2.md).

## UI-state scope representation

A `route`-scoped state is rendered within the ownership boundary of one or more canonical routes. At least one route must list its identifier. Multiple routes may share the same route-scoped state.

A `global` state is owned outside canonical route presentation, such as by an application shell, router, or top-level error boundary. A route must not list a global state identifier. The scope declaration describes observable presentation ownership; it does not select a state store, routing library, rendering framework, or component architecture.

UI states schema version 2 introduced this required distinction. Repositories migrating from version 1 must follow [`docs/migrations/ui-states-v1-to-v2.md`](docs/migrations/ui-states-v1-to-v2.md).

## Viewport breakpoint representation

`contracts/viewports.json` records an ordered sequence of lower bounds. The first `minWidthPx` must be `0`, and every following value must be strictly greater than the previous value. A viewport applies over the half-open interval from its lower bound up to, but not including, the next viewport's lower bound; the final viewport has no upper bound.

Upper bounds are deliberately not stored. Deriving them from the next lower bound avoids fractional-width gaps under browser zoom and prevents adjacent declarations from disagreeing about a shared boundary.

Input capabilities are declared once in the top-level `inputCapabilities` collection. They are not attached to breakpoints because viewport width does not determine whether touch, pointer, keyboard, voice, or switch input is available. Responsive layout tests must exercise supported input modes independently of viewport width.

## Implementation evidence representation

`contracts/implementation-evidence.json` is a closed evidence matrix for every surface, route, UI state, viewport, input capability, and registered contract transition.

The template document uses `mode: template`. Its records state which implementation boundary and positive, negative, command, and release evidence a generated repository must provide, but they do not claim that the framework-neutral template contains a product implementation.

A generated repository uses `mode: product` only after every record has:

- a verified implementation boundary and concrete locator;
- verified positive evidence;
- verified negative evidence wherever access, degraded behavior, failure, connectivity, or a breaking transition requires it;
- an authoritative command for every proof;
- at least one release gate; and
- release gates that execute every command used by the record's proofs.

The evidence validator proves reference integrity and coverage. It does not execute product commands or decide whether a test semantically proves the declaration. See [`docs/architecture/implementation-evidence.md`](docs/architecture/implementation-evidence.md).

## Contract evolution representation

A new contract family starts at version 1 with `changeType: initial`. Each later version adds one contiguous history entry classified as `additive` or `breaking` and registers `docs/migrations/<migration-slug>-vN-to-vN+1.md`.

The migration slug is a stable family identifier independent of the current document path. Preserve it across document and schema moves so historical migration filenames are never rewritten.

An additive transition must preserve the validity, meaning, and implementation obligations of every document accepted by the preceding version. A breaking transition includes any new invalidation, changed meaning, new mandatory cross-contract invariant, closed-enum change, stable-identifier rename or removal, contract-family retirement, or changed implementation-evidence obligation.

Documentation clarifications, diagnostic improvements, validator refactors, and test refactors do not increment a domain contract version when accepted documents and semantics remain unchanged. Version numbers are local to each contract family and must not be aligned artificially.

Contract identifiers, migration slugs, entity identifiers, and manifest-retained document and schema paths are public repository references. Renaming or removing one is a breaking change and requires an explicit migration that accounts for all contract references, implementation boundaries, tests, evidence, deployment consequences, and rollback implications.

When retiring a non-core family, move its identity and history to a tombstone rather than deleting them. The retirement version follows the last live document version and the final transition is breaking. Core families remain active unless the bootstrap schema itself is changed through a separate reviewed migration.

`validate_contracts` verifies current active contract structure and cross-file invariants. `validate_contract_evolution` verifies active and retired histories, stable migration ownership, and the closed migration-artifact inventory. `validate_implementation_evidence` verifies evidence coverage and release-reference closure. The detailed evolution rules are defined in [`docs/architecture/contract-evolution.md`](docs/architecture/contract-evolution.md).

## Compatibility rule

The contract files and `contracts/manifest.json` are public repository interfaces. Renaming identifiers, moving contract files, retiring a family, changing schema versions, or changing semantics requires coordinated updates to the schema, example document or tombstone, manifest history, migration, validators, implementation, navigation, authorization, documentation, deployment configuration, tests, evidence, and rollback plan.
