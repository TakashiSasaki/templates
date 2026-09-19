# Site authority navigation

## Start here

- [Repository overview](README.md) - Explains the five-authority repository model, primary consumer entry points, and the Site publication boundary.
- [Machine-readable agent discovery](agent.json) - Provides the repository entry point intended for coding-agent discovery.
- [Templates maintainer onboarding](docs/maintainer-onboarding.md) - Routes maintenance work to the owning authority and its first validation path.
- [Repository agent instructions](AGENTS.md) - Defines the active generated operating instructions for changes on the Site authority.

## Publication and maintenance

- [Site publication and deployment](PUBLISHING.md) - Defines Integration adoption, Site qualification, Pages authorization, and deployment boundaries.
- [Site maintenance](MAINTENANCE.md) - Describes maintenance procedures and the local completion path.
- [Freshness model](FRESHNESS.md) - Describes runtime freshness and cache behavior.
- [Publication freshness](PUBLICATION_FRESHNESS.md) - Describes freshness semantics for publication inputs and deployed outputs.

## Documentation and contracts

- [Documentation](docs/) - Contains reader-facing and maintainer-facing Site documentation and architecture material.
- [Contracts](contracts/index.md) - Contains Site-owned contract instances and declared repository topology inputs.
- [Schemas](schemas/) - Contains Site-owned schema material used to validate Site contracts and publication inputs.
- [Translations](translations/) - Contains Site-owned translation sources and synchronization metadata.

## Implementation

- [Site renderer](site_renderer/) - Implements rendering of the selected immutable Publication Bundle and Site-owned content.
- [Publication Bundle consumer](publication_bundle/) - Implements the Site-side Bundle validation and read-model boundary.
- [Scripts](scripts/) - Contains build, qualification, validation, generation, and maintenance commands.
- [Tests](tests/) - Contains Site acceptance and regression coverage.
