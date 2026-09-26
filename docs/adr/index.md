# Architecture decisions

## Current decisions

* [Maintainer publication sources](../publication-catalog.md#deferred-maintainer-publications) - ADR-0008 remains current for trust and provenance, with partial supersession by ADR-0009 for review-result representation. Both decisions are now cataloged Policy publications; Site staging and later promotion control their integrated reader exposure.

* [ADR-0002: Repository adoption](0002-repository-adoption.md) - Defines how existing repositories adopt the policy toolchain without destructively replacing existing instructions.
* [ADR-0003: Application-neutral policy scope](0003-application-neutral-policy-scope.md) - Keeps shared policy focused on application-type-independent agent operation rather than product architecture.
* [ADR-0005: Single policy authority](0005-single-policy-authority.md) - Establishes one canonical policy authority and treats generated instructions as projections of that authority.
* [ADR-0006: Copyable artifact policy adoption](0006-copyable-artifact-policy-adoption.md) - Defines how copyable template artifacts opt into shared policy without importing maintainer-only repository policy.
* [ADR-0007: Single agent-policy skill with persistent runtime cache](0007-single-agent-policy-skill-runtime-cache.md) - Uses one immutable repository-facing skill before and after adoption and reuses validated full-SHA runtimes.

* [ADR-0008: Review authority and GitHub runtime boundary (partially superseded)](0008-review-authority-and-github-runtime-boundary.md) - Preserves trusted review bootstrap, provenance, and the GitHub runtime boundary; read ADR-0009 for the superseded representation requirements.
* [ADR-0009: Review-result representation boundary](0009-review-result-representation-boundary.md) - Keeps representation outside review authority while preserving the identity-bound completion handoff; partially supersedes ADR-0008.

## Superseded decisions

* [ADR-0004: Integrated bootstrap skill](0004-integrated-bootstrap-skill.md) - Superseded by ADR-0007; retained only as historical rationale for the earlier bootstrap trust-boundary design.

- [Discovery adapter candidate](0010-discovery-adapter-candidate.md) - Defines the proposed local adapter and isolated migration boundary.
