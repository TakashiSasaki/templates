# Skill template documentation

This directory is the maintainer-facing documentation index for the `skill` branch. The copyable Skill template has its own consumer-facing index at [`template/docs/index.md`](../template/docs/index.md).

This file is a navigation index following the `index.md` conventions in OKF v0.2 section 8. It does not declare this directory or repository to be a formal OKF bundle.

## Distribution architecture

- [Distribution architecture index](architecture/index.md) — Groups the maintainer-only documents that define the copyable `template/` boundary.

## Publication and maintenance

- [Publication maintenance](publication-maintenance.md) — Defines how selected Skill documentation is prepared for the unrelated `site` publication branch.
- [Publication catalog data](publication-catalog.json) — Machine-readable list of Skill documents selected for publication.
- [Ruby-to-Python migration](ruby-to-python-migration.md) — Records the migration of maintained validation tooling from Ruby to Python.
- [Schema validator absence](schema-validator-absence.md) — Records the reviewed boundary where an external schema validator is intentionally not required.

## Copyable documentation

- [Consumer documentation index](../template/docs/index.md) — Describes the documentation and interface contracts actually included in repositories copied from `template/`.
