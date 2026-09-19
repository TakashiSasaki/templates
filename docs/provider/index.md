# Provider and toolchain documentation

## Orientation

* [Consumer application](../consumer/index.md) - Use Policy in another repository, including advanced review configuration. This provider path covers the compiler, shared corpus, release machinery, and documentation publication in `TakashiSasaki/templates`; shared references such as the CLI can support both tasks.

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
