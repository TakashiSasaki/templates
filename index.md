# Integration authority navigation

## Start here

- [Integration overview](README.md) - Explains exact provider selection, deterministic Publication Bundle production, and downstream Site separation.
- [Integration authority boundary](AUTHORITY.md) - Defines Integration decision rights and the boundaries with Modeling, Composition, Policy, and Site.
- [Repository agent instructions](AGENTS.md) - Defines branch-local operating constraints and the Integration maintenance route.
- [Release procedure](RELEASE.md) - Defines Integration release, qualification, promotion, and handoff boundaries.

## Publication inputs and contracts

- [Provider selection](publication-sources.json) - Records the exact reviewed provider revisions selected by Integration.
- [Publication staging](publication-staging.json) - Records explicit staging state for publication processing.
- [Site manifest](site-manifest.json) - Defines the integrated publication destination and reader information-architecture contract.
- [Contracts](contracts/) - Contains Publication Bundle and compatibility contracts, schemas, registries, and qualification-report definitions.
- [Integration documentation](docs/) - Contains Integration-owned glossary and publication catalog inputs.

## Implementation and qualification

- [Integration implementation](integration/) - Implements provider qualification, publication assembly, compatibility, navigation, translation, and glossary processing.
- [Publication Bundle contract implementation](publication_bundle/) - Implements the portable Bundle validation and read-model contract.
- [Scripts](scripts/) - Contains production, qualification, reconciliation, adoption, and verification entry points.
- [Tests](tests/) - Contains deterministic Bundle, compatibility, transport, and authority-boundary regression coverage.
