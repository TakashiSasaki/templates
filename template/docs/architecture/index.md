# Web application architecture

This directory contains the architecture documentation distributed with the Webapp template. Maintainer-only distribution audits, completion records, and publication material are intentionally absent.

This file is a navigation index following the `index.md` conventions in OKF v0.2 section 8. It does not declare this directory or generated repository to be a formal OKF bundle.

## Contract model

- [Contract completeness](contract-completeness.md) — Defines the closed contract-family inventory and the criteria for extending it.
- [Contract evolution](contract-evolution.md) — Defines version histories, stable migration ownership, retirement, and rollback rules.
- [Responsibility boundaries](responsibility-boundaries.md) — Separates template, generated-product, and operational ownership.
- [Validation toolchain](validation-toolchain.md) — Defines the validation environment, locked dependencies, and supported validator entry points.

## Implementation and release evidence

- [Implementation evidence](implementation-evidence.md) — Connects implementation targets to positive and negative evidence and release gates.
- [Release evidence](release-evidence.md) — Binds command and release-gate results to one exact product revision.
- [Release bundle](release-bundle.md) — Defines the digest-closed handoff bundle produced after approved release evidence.
