# Web application architecture

## Contract model

* [Contract completeness](contract-completeness.md) - Defines the closed contract-family inventory and the criteria for extending it.
* [Contract evolution](contract-evolution.md) - Defines version histories, stable migration ownership, retirement, and rollback rules.
* [Responsibility boundaries](responsibility-boundaries.md) - Separates template, generated-product, and operational ownership.
* [Validation toolchain](validation-toolchain.md) - Defines the validation environment, locked dependencies, and supported validator entry points.

## Implementation and release evidence

* [Implementation evidence](implementation-evidence.md) - Connects surfaces, routes, UI states, viewports, input capabilities, and migrations to positive and negative implementation proof.
* [Release evidence](release-evidence.md) - Binds command and release-gate results to one exact product revision.
* [Release bundle](release-bundle.md) - Defines the digest-closed handoff bundle produced after approved release evidence.

## Template maintenance and distribution

* [Completion roadmap](completion-roadmap.md) - Records the cross-cutting completion criteria used to finish the Webapp template foundation.
* [Distribution boundary](distribution-boundary.md) - Defines the separation between template-maintenance artifacts and the copyable `template/` subtree.
* [Distribution classification](distribution-classification.json) - Provides machine-readable classification of top-level distribution and maintainer paths.
* [Distribution readiness audit](distribution-readiness-audit.md) - Records evidence that the copyable distribution boundary is complete and internally consistent.
* [Final readiness audit](final-readiness-audit.md) - Records the final cross-cutting readiness review for the maintained template.
* [Generated repository conformance](generated-repository-conformance.md) - Defines and verifies clean-room transition from template mode to generated product mode.

## Copyable architecture

* [Consumer architecture](../../template/docs/architecture/) - Enumerates architecture documentation included in copied repositories.
