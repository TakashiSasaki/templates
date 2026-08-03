# Template scope and customization contract

## Purpose

This branch defines the repository-level foundation for browser-facing web applications. It starts with contracts that remain useful across frameworks and deployment platforms.

## Included in the foundation

- explicit application-surface classification;
- canonical route and navigation contracts with explicit access-failure presentation behavior;
- user-visible loading, empty, partial, error, offline, and recovery states with explicit route or global ownership scope;
- supported viewport declarations;
- a closed manifest that inventories every domain contract and schema;
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
5. Keep `contracts/manifest.json` synchronized when adding, removing, or versioning contract families.
6. Define trusted authorization enforcement independently of route or directory names.
7. Select one implementation toolchain and record authoritative build, test, lint, and deployment commands.
8. Add implementation-level tests that prove the declared contracts.
9. Remove template-only guidance that no longer applies.

The complete generated-repository sequence, including contract customization, implementation evidence, CI integration, and deployment ownership, is described in [`docs/operationalization.md`](docs/operationalization.md).

## Contract-set completeness

`contracts/manifest.json` is the repository-local inventory of domain contracts. It records each contract identifier, document path, schema path, document schema version, and purpose.

Validation rejects:

- contract or schema files that are present but not registered;
- registered files that are missing or symbolic links;
- duplicate identifiers, document paths, or schema paths;
- paths outside the repository-owned contract and schema directories;
- document `$schema` declarations or `schemaVersion` values that differ from the manifest;
- declared surfaces that are not owned by any canonical route;
- access-failure behavior that is inconsistent with route authentication or surface authorization;
- rendered access failures without their corresponding route-scoped UI states;
- redirected or inapplicable access failures that still declare those UI states;
- route-scoped UI states that are not declared by any route;
- global UI states that are declared by a route.

The manifest and its schema are validator bootstrap metadata, not a fifth product-domain contract. See `docs/architecture/contract-completeness.md` for the current coverage boundary and the criteria for adding another contract family.

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

## Compatibility rule

The contract files and `contracts/manifest.json` are public repository interfaces. Renaming identifiers, moving contract files, changing schema versions, or changing semantics requires coordinated updates to implementation, navigation, authorization, documentation, deployment configuration, tests, and migration notes.
