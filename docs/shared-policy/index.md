# Shared policy corpus

## Canonical policy families

* [Core policy modules](../../policy/core/) - Contains application-type-independent core operating rules selected by the core profile.
* [Review policy modules](../../policy/review/) - Contains application-type-independent rules selected for review operations.
* [Pull-request policy modules](../../policy/pull-request/) - Contains generic pull-request merge-readiness rules.
* [Security policy modules](../../policy/security/) - Contains application-type-independent security baseline rules.
* [Artifact-related shared modules](../../policy/artifacts/) - Contains shared rules whose semantics remain independent of a particular product repository.

## Selection profiles

* [Core profile](../../profiles/core.yml) - Selects the default core shared-policy modules.
* [Review profile](../../profiles/review.yml) - Selects shared rules for review context composition.
* [Pull-request profile](../../profiles/pull-request.yml) - Selects generic pull-request merge gates.
* [Security baseline profile](../../profiles/security-baseline.yml) - Selects shared security baseline rules.
* [External artifact intake profile](../../profiles/external-artifact-intake.yml) - Selects rules for validated external-artifact intake.

## Corpus semantics and authority

* [Policy authoring](../policy-authoring.md) - Defines shared-policy ownership, atomic rule modules, repository-local extensions, and override semantics.
* [Policy authority inventory](../policy-authority-inventory.md) - Enumerates the maintained authority surfaces and distinguishes semantic authorities from projections and adapters.
* [Shared review policy](../review-policy.md) - Describes the shared review-policy family and its provider-neutral boundary.
* [External artifact intake](../external-artifact-intake.md) - Describes the shared context policy for intake of external artifacts.
* [Regression prevention](../regression-prevention.md) - Describes cross-cutting regression-prevention semantics represented in shared policy.
