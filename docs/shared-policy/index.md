# Shared policy corpus

## Corpus ownership and structure

* [Repository structure](../repository-structure.md) - Identifies `policy/` as the canonical shared-rule corpus and `profiles/` as the branch-owned rule-selection sets, separate from the provider toolchain and maintainer-only repository policy.
* [Policy authoring](../policy-authoring.md) - Defines shared-policy ownership, atomic rule modules, context policy, repository-local extensions, and override semantics.
* [Policy authority inventory](../policy-authority-inventory.md) - Enumerates semantic authority surfaces and distinguishes canonical rules from generated projections and adapters.

## Policy families and contexts

* [Shared review policy](../review-policy.md) - Describes the provider-neutral review-policy family selected for review operations.
* [External artifact intake](../external-artifact-intake.md) - Describes the context policy selected for validated external-artifact intake.
* [Regression prevention](../regression-prevention.md) - Describes cross-cutting regression-prevention semantics represented in the shared corpus.

## Selection, composition, and rendering

* [Policy profiles](profiles.md) - Explains what profiles are, how they compose shared rules inside policy contexts, which profiles are available, and when to select each one.
* [Configuration](../configuration.md) - Defines how a consumer selects shared profiles, adds repository-local policy, declares explicit overrides, and binds outputs to contexts.
* [Architecture](../architecture.md) - Describes how selected shared and repository-local rules are loaded, composed, rendered, and recorded in lock state.
