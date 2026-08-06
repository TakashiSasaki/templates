# Changelog

All notable changes to the Agent Skill template product are documented here.

## Unreleased

### Changed

- Redefined the `skill` branch root as the template-product source repository rather than an installable Skill directory.
- Established `template/` as the sole directly copyable, profile-aware Agent Skill template.
- Preserved `template-scaffold`, all eight concrete profile tags, `instruction-only` exclusivity, and union-of-required-contracts composition.
- Added an exact distribution manifest with a closed file inventory, maintainer-path exclusions, and byte/mode-checked validator projections.
- Moved all canonical consumer contracts, profile guidance, optional resource placeholders, and concrete-Skill validation into `template/`.
- Removed the obsolete root-level Skill scaffold without removing any consumer artifact from `template/`.
- Changed clean-room adoption and clone, submodule, and archive installation tests to begin from a byte-preserving copy of `template/.`.
- Preserved stable publication document IDs while moving canonical consumer document sources below `template/`.
- Added a dedicated maintainer ownership boundary and a restructuring completion audit.

### Deployment

- GitHub Pages deployment remains suspended until the unrelated `site` branch locks the final reviewed Skill merge commit, publishes a dedicated Skill copyable-template tree, passes strict integration validation, and restores deployment in a separate reviewed pull request.
