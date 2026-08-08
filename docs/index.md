# Policy documentation

## Start here

* [Overview](overview.md) - Introduces the `agent-policy` toolchain, its purpose, repository structure, and primary commands.
* [Getting started](getting-started.md) - Describes first-time setup and the main usage path.
* [Managed repository operation](managed-operation.md) - Describes normal operation after adoption.
* [CLI reference](cli.md) - Defines the command-line interface and subcommands.
* [Bootstrap skill](bootstrap.md) - Describes the immutable trust-seed path into initialization and adoption.
* [Repository adoption](adoption.md) - Defines staged adoption while preserving existing instructions.

## Lifecycle and publication

* [Release lifecycle](release-lifecycle.md) - Defines the policy toolchain release lifecycle.
* [Policy completion roadmap](policy-readiness.md) - Records completion criteria for the maintained policy toolchain.
* [Policy readiness audit](policy-readiness-audit.md) - Records the maintainer readiness audit.
* [Documentation publication](documentation-publication.md) - Defines documentation publication boundaries.
* [Publication catalog](publication-catalog.md) - Documents the branch-owned publication allowlist.
* [PWA usage](pwa.md) - Describes Progressive Web App behavior for the policy documentation.

## Design

* [Repository structure](repository-structure.md) - Describes the maintained repository layout and responsibilities.
* [Architecture](architecture.md) - Describes the compiler, generated artifacts, lock state, and trust boundaries.
* [Configuration](configuration.md) - Defines the policy configuration model.
* [Policy authoring](policy-authoring.md) - Defines how shared policy rules are authored.
* [Policy authority inventory](policy-authority-inventory.md) - Enumerates policy authority surfaces.
* [Shared review policy](review-policy.md) - Defines shared review behavior.
* [External artifact intake](external-artifact-intake.md) - Defines safe intake of external artifacts.
* [Regression prevention](regression-prevention.md) - Defines cross-cutting regression-prevention rules.
* [Bootstrap model](bootstrap-model.md) - Defines the bootstrap trust model.
* [Threat model](threat-model.md) - Defines defended threats and trust boundaries.

## Subdirectories

* [Architecture decisions](adr/) - Enumerates active architecture decision records.
* [Agent environments](agent-environments/) - Contains environment-specific operating guidance.
