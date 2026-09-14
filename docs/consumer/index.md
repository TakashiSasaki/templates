# Applying policy to a consumer repository

This path covers using Policy in another repository, including its ongoing
operation and advanced review configuration. Repository-local policy belongs to
that consumer. Changing the shared corpus, compiler, or provider release system
belongs to [Provider and toolchain documentation](../provider/index.md).

## Adoption and initialization

* [Getting started](../getting-started.md) - Describes first-time setup and the main path into a managed consumer repository.
* [Bootstrap skill](../bootstrap.md) - Describes the immutable trust-seed path into initialization and adoption preparation.
* [Repository adoption](../adoption.md) - Defines staged adoption while preserving existing repository instructions.

## Effective policy and managed operation

* [Local policy authoring](../policy-authoring.md#repository-local-extension-and-override) - Explains local extensions and permitted overrides without restating shared rules.

* [Configuration](../configuration.md) - Defines how a consumer repository selects shared profiles, adds repository-local policy, and declares generated outputs.
* [Managed repository operation](../managed-operation.md) - Describes normal operation after adoption and the repository-local control state.
* [Policy authority inventory](../policy-authority-inventory.md) - Distinguishes canonical shared policy, repository-local policy, generated projections, and adapter-specific output surfaces.

## Operational contexts

* [External artifact intake](../external-artifact-intake.md) - Describes selection and use of the external-artifact intake policy context.
* [Shared review policy](../review-policy.md) - Describes the provider-neutral review semantics that a consumer may select for review operations.
