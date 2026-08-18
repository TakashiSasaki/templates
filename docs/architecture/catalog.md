# Production catalog architecture

PR2 turns the component model established by PR1 into a closed source-authority catalog.

## Authority

`catalog/catalog.json` is the inventory authority. It does not duplicate full descriptors or recipes; it names the component and recipe IDs whose canonical documents live at deterministic repository paths.

The catalog is intentionally closed:

```text
catalog component IDs == components/*/component.json identities
catalog recipe IDs    == recipes/*.json identities
```

An unlisted component directory or recipe file is invalid, as is a catalog entry without its canonical file.

## Component source closure

For a copied `managed` or `seed` material, `materials[].source` is relative to the component directory. PR2 uses a conventional `files/` subtree and requires every file below that subtree to be declared by exactly one copied material.

This makes component source content reviewable as a closed set rather than allowing undeclared files to acquire accidental authority.

## Dependency graph

Catalog validation proves dependency references exist and the current graph is acyclic. Generic capability/lifecycle descriptors must not depend on artifact-specific components.

This is source-graph validation, not the general consumer resolver. The later resolver will apply recipe defaults, explicit include/exclude intent, parameters, conflicts, and transitive closure to a concrete consumer configuration.

## Recipe validation

Every production recipe names one catalog artifact and only catalog capability/lifecycle selections. Required/default/optional groups are disjoint.

PR2's `skill` recipe has no default application capabilities. This preserves the minimal Agent Skill: runtime and public interfaces are opt-in rather than silently materialized.

## Portable destination ownership

Before a recipe is consumable, tested selections must have one portable owner per destination. Validation compares ASCII paths case-insensitively and rejects file/directory-prefix collisions.

PR2 proves this invariant for the union of all six Skill application capabilities. Later artifact/lifecycle migrations must extend the same catalog tests.

## Relation to PR1 wording

`docs/architecture/composition-model.md` records the PR1 foundation and therefore describes a production catalog as future work at several points. PR2 satisfies the **source catalog** portion of that boundary. The general resolver, production lock generation, materializer, and update behavior remain future work.
