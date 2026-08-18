# Composition source

This orphan branch is the development source for reusable artifact, capability, and lifecycle components in `TakashiSasaki/templates`.

Consumer repositories are not created by copying a monolithic `template/` directory. A future deterministic composer will resolve a recipe plus explicit consumer intent, materialize the selected component set, write a lock, and leave the resulting consumer repository self-contained.

## PR1 scope

The first pull request establishes only the composition architecture and its machine-readable data contracts:

- component descriptors;
- artifact recipes;
- consumer composition intent;
- resolved composition locks;
- file-ownership and destination-path invariants;
- deterministic, hook-free composition boundaries; and
- schema validation in read-only CI.

PR1 does **not** migrate Webapp or Skill content, implement the composer, change Site publication, or retire the `webapp` and `skill` branches.

See [`docs/architecture/composition-model.md`](docs/architecture/composition-model.md).
