# Template scope and customization contract

## Purpose

This branch defines the repository-level foundation for browser-facing web applications. It starts with contracts that remain useful across frameworks and deployment platforms.

## Included in the foundation

- explicit application-surface classification;
- canonical route and navigation contracts;
- user-visible loading, empty, partial, error, offline, and recovery states;
- supported viewport declarations;
- JSON Schemas for those contracts;
- local validation, tests, and CI;
- traceability to applicable `agent-policy` rules.

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
3. Define trusted authorization enforcement independently of route or directory names.
4. Select one implementation toolchain and record authoritative build, test, lint, and deployment commands.
5. Add implementation-level tests that prove the declared contracts.
6. Remove template-only guidance that no longer applies.
7. Integrate `agent-policy` using a pinned full commit SHA after the repository-specific project policy is written.

## Route-path representation

`contracts/routes.json` records canonical URL pathnames, not arbitrary URLs or framework route-pattern syntax. The foundation accepts `/` or slash-separated, non-empty segments composed only of ASCII URL-unreserved characters: letters, digits, `.`, `_`, `~`, and `-`. A segment may not be exactly `.` or `..`.

Raw whitespace, control characters, non-ASCII characters, percent encoding, query strings, fragments, backslashes, empty segments, and trailing slashes are rejected. Products that require internationalized paths, encoded octets, parameters, query contracts, or fragment contracts must add a normalization model and collision tests before relaxing this conservative representation.

## Compatibility rule

The contract files are public repository interfaces. Renaming identifiers or changing semantics requires coordinated updates to implementation, navigation, authorization, documentation, deployment configuration, tests, and migration notes.
