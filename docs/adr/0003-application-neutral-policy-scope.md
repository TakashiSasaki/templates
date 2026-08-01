# ADR-0003: Keep shared agent policy application-type independent

- Status: Accepted
- Date: 2026-08-01

## Context

The policy toolkit originally included a `web-application` profile containing rules for application surfaces, navigation, user-visible states, accessibility, diagnostics, and responsive layout. Those concerns are valid, but they describe the architecture and behavior of a Web application rather than the way a coding agent should investigate, modify, validate, and report work.

Keeping application design requirements in the shared agent-policy compiler creates two competing authorities:

- an operational policy system that tells agents how to work; and
- an application template that defines what a particular artifact must contain and how its contracts are validated.

It also encourages parallel profiles for command-line applications, libraries, mobile applications, services, and other artifact categories. That would turn the policy toolkit into a collection of product-architecture standards rather than a reusable agent-operation system.

## Decision

Built-in shared policy must be application-type independent.

A shared rule or profile belongs in this branch only when it can retain substantially the same meaning across repositories for Web applications, command-line tools, libraries, services, data projects, and other artifact categories. Appropriate subjects include:

- change scope, acceptance baselines, semantic decision gates, and regression prevention;
- validation order, evidence, truthful reporting, and compatibility handling;
- generated-artifact ownership and transaction boundaries;
- secret handling, trust-boundary validation, and destructive-action revalidation;
- operational contexts such as external-artifact intake or high-risk migration.

Built-in shared policy must not define artifact architecture such as:

- application surfaces, routes, navigation, or browser history;
- user-interface states, accessibility semantics, or responsive layout;
- framework, package, rendering, backend, persistence, or deployment topology;
- product roles, domain schemas, concrete endpoints, or product terminology.

Artifact-category requirements belong in the corresponding template or domain-specific contract system. Product-specific requirements belong in the product repository. A product repository may still reference its own design and verification documents from repository-local policy, but doing so does not make those design requirements part of the shared policy corpus.

References from shared policy documentation to an application template are informational only and must not create compiler, runtime, validation, or release dependencies between the policy and template branches.

Profiles may classify operational situations or risk postures. They must not classify repositories solely by artifact category, such as `web-application`, `cli-application`, `mobile-application`, `library`, or `backend-service`.

## Consequences

- The built-in `web-application` profile and its eight `interfaces.*` rules are removed.
- Web-application design authority remains with `TakashiSasaki/templates` branch `webapp`; the policy toolkit has no runtime or validation dependency on that branch.
- Consumers migrating to `templates:policy` must remove `web-application` from `.agent-policy.yml` and adopt the relevant Webapp contracts independently when applicable.
- Existing operational rules are reviewed by what they require an agent to do, not by the vocabulary in their identifier or documentation.
- Future application-category proposals are redirected to the appropriate template or domain-contract branch.

## Verification

Repository tests enforce that the removed profile, its rule files, and its documentation do not return, and that the scope decision remains present in the published documentation navigation.
