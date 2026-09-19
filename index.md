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
- [Glossary contract](GLOSSARY.md) - Defines the terminology contract shared by the authority and publication surfaces.
- [Language and translation ownership](LANGUAGE.md) - Defines canonical language and translation ownership for Site documentation.
- [Publication staging](PUBLICATION_STAGING.md) - Describes the Integration-owned staging boundary consumed by Site.
- [Site PWA contract](PWA.md) - Describes Site-owned PWA and runtime contract inputs.

## Documentation and contracts

- [Documentation index](docs/index.md) - Routes reader-facing and maintainer-facing Site documentation and architecture material.
- [Contracts](contracts/index.md) - Contains Site-owned contract instances and declared repository topology inputs.
- [Reference consumer contract](reference-consumer.json) - Declares product, maintenance, and deployed publication relationships.
- [Integration selection](integration-source.json) - Binds the exact Integration revision and Bundle identity selected by Site.
- [Composition input](composition.json) - Records the Composition product input consumed by this Site authority.
- [Site maintenance policy](policy/project.md) - Records the Site-local policy source routed by the maintenance configuration.
- [Schemas](schemas/) - Contains Site-owned schema material used to validate Site contracts and publication inputs.
- [Translations](translations/) - Contains Site-owned translation sources and synchronization metadata.

## Implementation

- [Site renderer](site_renderer/) - Implements rendering of the selected immutable Publication Bundle and Site-owned content.
- [Publication Bundle consumer](publication_bundle/) - Implements the Site-side Bundle validation and read-model boundary.
- [Scripts](scripts/) - Contains build, qualification, validation, generation, and maintenance commands.
- [Tests](tests/) - Contains Site acceptance and regression coverage.
