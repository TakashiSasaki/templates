# ADR-0003: Keep shared agent policy application-type independent

- Status: Accepted
- Date: 2026-08-01

## Context

The policy toolkit originally included a `web-application` profile containing rules for application surfaces, navigation, user-visible states, accessibility, diagnostics, and responsive layout. Those concerns are valid, but they describe the architecture and behavior of a Web application rather than the way a coding agent should investigate, modify, validate, and report work.

Keeping application design requirements in the shared agent-policy compiler creates two competing authorities:

- an operational policy system that tells agents how to work; and
- an artifact contract system that defines what a particular artifact must contain and how its contracts are validated.

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

Artifact-category requirements belong in the corresponding Composition artifact, capability, lifecycle, recipe, or domain-specific contract. Product-specific requirements belong in the product repository. A product repository may still reference its own design and verification documents from repository-local policy, but doing so does not make those design requirements part of the shared policy corpus.

References from shared policy documentation to Composition are informational only and must not create compiler, runtime, validation, or release dependencies between Policy and Composition. Cross-authority coexistence is governed by the Site-owned Policy–Composition coexistence contract.

Profiles may classify operational situations or risk postures. They must not classify repositories solely by artifact category, such as `web-application`, `cli-application`, `mobile-application`, `library`, or `backend-service`.

## Consequences

- The built-in `web-application` profile and its eight `interfaces.*` rules are removed.
- Web-application design authority belongs to the `composition` authority; the policy toolkit has no runtime or validation dependency on Composer or Composition state.
- Consumers using shared Policy must not encode Webapp artifact selection as a Policy profile; relevant Composition contracts are selected independently when applicable.
- Existing operational rules are reviewed by what they require an agent to do, not by the vocabulary in their identifier or documentation.
- Future application-category proposals are redirected to Composition or another appropriate artifact/domain-contract authority rather than added to shared Policy.

## Verification

Repository tests enforce that the removed profile, its rule files, and its documentation do not return, that the scope decision remains present in the published documentation navigation, and that Policy does not reclaim Composition artifact semantics.
