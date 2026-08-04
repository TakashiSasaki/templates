# Responsibility boundaries

This document defines ownership boundaries for the Web-application repository template. The boundary is based on what a concern specifies, not on which person or automation consumes it.

## Template-owned concerns

The `webapp` template owns reusable, framework-neutral contracts for browser-facing applications:

- application surfaces and their audiences, access conditions, data classifications, stability, and dependencies;
- canonical routes, aliases, navigation behavior, authentication return behavior, access-failure presentation, and deep-link expectations;
- user-visible states, presentation ownership, and recovery behavior;
- viewport declarations and input-capability assumptions;
- the closed contract manifest, active and retired histories, stable migration ownership, and inventory invariants;
- the reusable shape for implementation boundaries, positive and negative proofs, authoritative commands, and release-gate definitions;
- the reusable shape for binding completed command and gate results to one exact candidate revision and current command definitions;
- JSON Schemas, cross-contract validation, reference tests, clean-room conformance, and template CI; and
- guidance for replacing example declarations with product-specific declarations and release results.

These artifacts define the structure and meaning of a Web application repository and the minimum evidence closure required before release. They are authoritative within the scope of this template.

The template does not execute arbitrary product command strings, infer provider-specific revision variables, approve a real release, or deploy a product.

## Product-repository concerns

A repository created from the template owns all concrete product decisions, implementation evidence, command execution, and release results, including:

- actual surfaces, routes, roles, terminology, and data classifications;
- framework, rendering model, package manager, backend, persistence, CI, artifact storage, and deployment choices;
- trusted authentication and authorization enforcement;
- authoritative build, test, lint, validation, release, and deployment commands;
- concrete implementation locators and expected proof results;
- implementation-level accessibility, security, integration, migration, retirement, rollback, and end-to-end tests;
- execution of authoritative commands for the exact candidate revision;
- command and gate result locators, provenance, retention, redaction, signing, and attestation;
- the release approval or rejection decision;
- deployment execution and post-deployment verification; and
- migration notes when public contract identifiers or semantics change.

The template must not pretend to make these choices by retaining multiple competing placeholders or by claiming product results in template mode.

## Concerns outside the Webapp contract

The following concerns are intentionally separate from the Web-application design and evidence contracts:

- coding-agent operating rules;
- organization-specific source-control, commit, review, approval, and release procedures;
- repository governance and organizational authorization;
- external policy compilers, generated instruction files, and unrelated policy toolchains;
- provider-specific workflow configuration beyond the template-maintainer validation job; and
- operational rules that apply equally to Web applications, command-line tools, libraries, services, and other repository types.

A product repository may adopt such mechanisms independently. Their adoption, identity, version, and generated artifacts must not become prerequisites for validating or using the Webapp contracts.

The release-evidence contract does not import an organization-specific release policy. It defines locally verifiable facts: exact revision, current command-definition digest, complete command and gate results, provenance locator, chronology, and decision status. Who may approve, how evidence is signed, how long it is retained, and which deployment system consumes it remain product- or organization-owned.

## Independence invariant

A checkout of this branch must be able to validate its template-mode contracts and run its tests using only the files in the checkout and the dependencies declared by this branch. It must not import external rule identifiers, profiles, generated policy artifacts, provider-specific credentials, or repository-specific product toolchain pins as design authority.

`contracts/manifest.json` closes the local contract set: every active product-domain contract and schema in the repository must be registered, every registered artifact must be present and synchronized, and retired families must retain their historical identity. This prevents an added file from silently falling outside the validator's authority.

`contracts/implementation-evidence.json` closes the reusable target, command, and gate references. `contracts/release-evidence.json` closes completed results against those current definitions and an explicitly supplied revision. Neither document authorizes the template to run product commands or approve a real product release.

Changes that add an external policy or provider dependency must first demonstrate that the concern is genuinely part of the Web-application design or evidence contract rather than an agent workflow, organizational approval policy, or repository-governance concern. Otherwise the change belongs outside this template.
