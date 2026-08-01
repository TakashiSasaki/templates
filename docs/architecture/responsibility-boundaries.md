# Responsibility boundaries

This document defines ownership boundaries for the Web-application repository template. The boundary is based on what a concern specifies, not on which person or automation consumes it.

## Template-owned concerns

The `webapp` template owns reusable, framework-neutral contracts for browser-facing applications:

- application surfaces and their audiences, access conditions, data classifications, stability, and dependencies;
- canonical routes, aliases, navigation behavior, authentication return behavior, and deep-link expectations;
- user-visible states and recovery behavior;
- viewport declarations and input-capability assumptions;
- the closed contract manifest and its inventory invariants;
- JSON Schemas, cross-contract validation, reference tests, and template CI;
- guidance for replacing example declarations with product-specific declarations.

These artifacts define the structure and meaning of a Web application. They are authoritative within the scope of this template.

## Product-repository concerns

A repository created from the template owns all concrete product decisions and implementation evidence, including:

- actual surfaces, routes, roles, terminology, and data classifications;
- framework, rendering model, package manager, backend, persistence, and deployment choices;
- trusted authentication and authorization enforcement;
- build, test, lint, release, and deployment commands;
- implementation-level accessibility, security, integration, and end-to-end tests;
- migration notes when public contract identifiers or semantics change.

The template must not pretend to make these choices by retaining multiple competing placeholders.

## Concerns outside the Webapp contract

The following concerns are intentionally separate from the Web-application design contract:

- coding-agent operating rules;
- source-control, commit, review, approval, and release procedures;
- repository governance and organizational authorization;
- external policy compilers, generated instruction files, lock files, and toolchain pins;
- operational rules that apply equally to Web applications, command-line tools, libraries, services, and other repository types.

A product repository may adopt such mechanisms independently. Their adoption, identity, version, and generated artifacts must not become prerequisites for validating or using the Webapp contracts.

## Independence invariant

A checkout of this branch must be able to validate its contracts and run its tests using only the files in the checkout and the dependencies declared by this branch. It must not import external rule identifiers, profiles, generated policy artifacts, or repository-specific toolchain pins as design authority.

`contracts/manifest.json` closes the local contract set: every product-domain contract and schema in the repository must be registered, and every registered artifact must be present and synchronized. This prevents an added file from silently falling outside the validator's authority.

Changes that add an external policy dependency must first demonstrate that the concern is genuinely part of the Web-application design contract rather than an agent workflow or repository-governance concern. Otherwise the change belongs outside this template.
