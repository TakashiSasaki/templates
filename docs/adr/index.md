# Architecture decisions

## Decisions

* [ADR-0002: Repository adoption](0002-repository-adoption.md) - Defines how existing repositories adopt the policy toolchain without destructively replacing existing instructions.
* [ADR-0003: Application-neutral policy scope](0003-application-neutral-policy-scope.md) - Keeps shared policy focused on application-type-independent agent operation rather than product architecture.
* [ADR-0004: Integrated bootstrap skill](0004-integrated-bootstrap-skill.md) - Keeps the bootstrap trust seed in the `policy` history while preserving immutable full-SHA and route boundaries.
* [ADR-0005: Single policy authority](0005-single-policy-authority.md) - Establishes one canonical policy authority and treats generated instructions as projections of that authority.
* [ADR-0006: Copyable artifact policy adoption](0006-copyable-artifact-policy-adoption.md) - Defines how copyable template artifacts opt into shared policy without importing maintainer-only repository policy.
