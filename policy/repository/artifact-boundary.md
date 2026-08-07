---
id: skill-source.preserve-artifact-boundaries
severity: mandatory
overridable: false
order: 1000
---
# Preserve source, distribution, and concrete-Skill boundaries

This branch is the source repository for a reusable Agent Skill template product. The repository root is not an installable Skill directory.

Treat these as distinct artifacts:

1. the complete source checkout;
2. the copyable `template/` distribution; and
3. a concrete Skill developed from that distribution.

The user-facing artifact is `template/`, whose contents are copied directly to a new Skill root. Consumer-facing Skill contracts, profile documentation, operational resource placeholders, and concrete-Skill instructions belong under `template/`; do not recreate them at the branch root as alternate authorities.

Source-only fixtures, negative cases, publication integration, source-maintainer review material, migration audits, and canonical adoption tests remain outside `template/`. Do not add source-only files to the distribution merely to make the trees look similar.
