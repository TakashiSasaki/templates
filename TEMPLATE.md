# Template scope and customization contract

## Purpose

This branch defines the repository-level foundation for browser-facing web applications. It starts with contracts that remain useful across frameworks and deployment platforms.

## Included in the foundation

- explicit application-surface classification;
- canonical route and navigation contracts;
- user-visible loading, empty, partial, error, offline, and recovery states;
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
2. Declare every externally observable surface and canonical route.
3. Keep `contracts/manifest.json` synchronized when adding, removing, or versioning contract families.
4. Define trusted authorization enforcement independently of route or directory names.
5. Select one implementation toolchain and record authoritative build, test, lint, and deployment commands.
6. Add implementation-level tests that prove the declared contracts.
7. Remove template-only guidance that no longer applies.

The complete generated-repository sequence, including contract customization, implementation evidence, CI integration, and deployment ownership, is described in [`docs/operationalization.md`](docs/operationalization.md).

## Contract-set completeness

`contracts/manifest.json` is the repository-local inventory of domain contracts. It records each contract identifier, document path, schema path, document schema version, and purpose.

Validation rejects:

- contract or schema files that are present but not registered;
- registered files that are missing or symbolic links;
- duplicate identifiers, document paths, or schema paths;
- paths outside the repository-owned contract and schema directories;
- document `$schema` declarations or `schemaVersion` values that differ from the manifest.

The manifest and its schema are validator bootstrap metadata, not a fifth product-domain contract. See `docs/architecture/contract-completeness.md` for the current coverage boundary and the criteria for adding another contract family.

## Route-path representation

`contracts/routes.json` records canonical URL pathnames, not arbitrary URLs or framework route-pattern syntax. The foundation accepts `/` or slash-separated, non-empty segments composed only of ASCII URL-unreserved characters: letters, digits, `.`, `_`, `~`, and `-`. A segment may not be exactly `.` or `..`.

Raw whitespace, control characters, non-ASCII characters, percent encoding, query strings, fragments, backslashes, empty segments, and trailing slashes are rejected. Products that require internationalized paths, encoded octets, parameters, query contracts, or fragment contracts must add a normalization model and collision tests before relaxing this conservative representation.

## Viewport breakpoint representation

`contracts/viewports.json` records an ordered sequence of lower bounds. The first `minWidthPx` must be `0`, and every following value must be strictly greater than the previous value. A viewport applies over the half-open interval from its lower bound up to, but not including, the next viewport's lower bound; the final viewport has no upper bound.

Upper bounds are deliberately not stored. Deriving them from the next lower bound avoids fractional-width gaps under browser zoom and prevents adjacent declarations from disagreeing about a shared boundary.

Input capabilities are declared once in the top-level `inputCapabilities` collection. They are not attached to breakpoints because viewport width does not determine whether touch, pointer, keyboard, voice, or switch input is available. Responsive layout tests must exercise supported input modes independently of viewport width.

## Compatibility rule

The contract files and `contracts/manifest.json` are public repository interfaces. Renaming identifiers, moving contract files, changing schema versions, or changing semantics requires coordinated updates to implementation, navigation, authorization, documentation, deployment configuration, tests, and migration notes.
