# Provider and toolchain documentation

## Orientation

* [Overview](../overview.md) - Introduces `agent-policy`, its purpose, the branch-owned toolchain, and the separation between provider, shared-policy, and consumer layers.
* [Repository structure](../repository-structure.md) - Describes the maintained `policy` branch layout and the responsibility of each top-level directory.
* [Architecture](../architecture.md) - Describes the compiler, generated artifacts, lock state, and trust boundaries.
* [CLI reference](../cli.md) - Defines the `agent-policy` command-line interface and subcommands.

## Provider lifecycle and trust

* [Bootstrap model](../bootstrap-model.md) - Defines the immutable trust-seed model used before a consumer repository is managed.
* [Release lifecycle](../release-lifecycle.md) - Defines stable toolchain promotion and immutable release identity.
* [Threat model](../threat-model.md) - Defines defended threats and trust boundaries for the provider and toolchain.

## Maintainer lifecycle and publication

* [Policy completion roadmap](../policy-readiness.md) - Records completion criteria for the maintained policy toolchain.
* [Policy readiness audit](../policy-readiness-audit.md) - Records the maintainer readiness audit.
* [Documentation publication](../documentation-publication.md) - Defines the branch-owned documentation publication boundary.
* [Publication catalog](../publication-catalog.md) - Documents the branch-owned publication allowlist.
* [PWA usage](../pwa.md) - Describes Progressive Web App behavior for policy documentation.
* [Architecture decisions](../adr/index.md) - Enumerates active architecture decision records.

## Agent environments

* [Agent environment guidance](../agent-environments/) - Contains environment-specific operating guidance owned by the provider documentation layer.
