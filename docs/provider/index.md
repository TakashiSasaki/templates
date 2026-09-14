# Provider and toolchain documentation

This path explains maintenance of the Policy provider in `TakashiSasaki/templates`:
the compiler, shared corpus, release machinery, and documentation publication.
For adoption, configuration, or applying even advanced review rules in another
repository, start with [Consumer application](../consumer/index.md). References
such as the CLI and trust model can support both tasks without changing ownership.

## Orientation

* [Repository structure](../repository-structure.md) - Describes the maintained `policy` branch layout and the responsibility of each top-level directory.
* [Architecture](../architecture.md) - Describes the compiler, generated artifacts, lock state, and trust boundaries.
* [CLI reference](../cli.md) - Defines the `agent-policy` command-line interface and subcommands.

## Provider lifecycle and trust

* [Bootstrap model](../bootstrap-model.md) - Defines the immutable trust-seed model used before a consumer repository is managed.
* [Release lifecycle](../release-lifecycle.md) - Defines stable toolchain promotion and immutable release identity.
* [Threat model](../threat-model.md) - Defines defended threats and trust boundaries for the provider and toolchain.

## Maintainer lifecycle and publication

* [Policy completion roadmap](../policy-readiness.md) - Records completion criteria for the maintained policy toolchain.
* [Documentation publication](../documentation-publication.md) - Defines the branch-owned documentation publication boundary.
* [Publication catalog](../publication-catalog.md) - Documents the branch-owned publication allowlist.
* [PWA usage](../pwa.md) - Describes Progressive Web App behavior for policy documentation.
* [Architecture decisions](../adr/index.md) - Enumerates active architecture decision records.

## Agent environments

* [Google AI Studio Build mode](../agent-environments/google-ai-studio.md) - Describes environment-specific operating guidance owned by the provider documentation layer.
