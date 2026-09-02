# Architecture decisions

## Current decisions

* [ADR-0002: Repository adoption](0002-repository-adoption.md) - Defines how existing repositories adopt the policy toolchain without destructively replacing existing instructions.
* [ADR-0003: Application-neutral policy scope](0003-application-neutral-policy-scope.md) - Keeps shared policy focused on application-type-independent agent operation rather than product architecture.
* [ADR-0005: Single policy authority](0005-single-policy-authority.md) - Establishes one canonical policy authority and treats generated instructions as projections of that authority.
* [ADR-0006: Copyable artifact policy adoption](0006-copyable-artifact-policy-adoption.md) - Defines how copyable template artifacts opt into shared policy without importing maintainer-only repository policy.
* [ADR-0007: Single agent-policy skill with persistent runtime cache](0007-single-agent-policy-skill-runtime-cache.md) - Uses one immutable repository-facing skill before and after adoption and reuses validated full-SHA runtimes.
* [ADR-0008: Review authority and GitHub runtime boundary](0008-review-authority-and-github-runtime-boundary.md) - Establishes immutable exact-base review authority, trusted bootstrap/runtime provenance, procedure freezing, identity stability, and review/merge separation; its result-representation coupling is superseded in part by ADR-0009.
* [ADR-0009: Review-result representation boundary](0009-review-result-representation-boundary.md) - Keeps provider serialization and GitHub request shape outside semantic and procedural review authority while preserving ADR-0008 trust machinery.

## Superseded decisions

* [ADR-0004: Integrated bootstrap skill](0004-integrated-bootstrap-skill.md) - Superseded by ADR-0007; retained only as historical rationale for the earlier bootstrap trust-boundary design.
