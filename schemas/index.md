# Composition schema navigation

## Source contracts

- [Schema guide](README.md) - Explains the responsibilities and relationships of the Composition schemas.
- [Component schema](component.schema.json) - Validates reusable component descriptors and material ownership.
- [Recipe schema](recipe.schema.json) - Validates consumer-facing artifact recipes.
- [Catalog schema](catalog.schema.json) - Validates the closed component and recipe inventory.

## Resolved state and operations

- [Composition configuration schema](composition-config.schema.json) - Validates unresolved consumer intent.
- [Playground intent schema](composition-playground-intent.schema.json) - Validates the generated empty-target intent projection.
- [Composition lock schema](composition-lock.schema.json) - Validates immutable resolved managed state.
- [Composition transaction schema](composition-transaction.schema.json) - Validates crash-recoverable update and upgrade actions.
- [Playground projection schema](composition-playground-projection.schema.json) - Validates the generated Composition playground projection.
- [Installer release schema](composition-skill-installer-release.schema.json) - Validates immutable installer, Skill source, and toolchain identities.
