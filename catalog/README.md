# Production composition catalog

`catalog.json` is the closed inventory of production component and recipe authorities available from this `composition` revision.

Every component ID resolves to `components/<component-id>/component.json`; every recipe ID resolves to `recipes/<recipe-id>.json`. Catalog arrays are unique and lexically ordered, and validation requires exact agreement with the physical authority directories/files.

## Closure rules

Production catalog validation establishes:

- descriptor/recipe/schema validity;
- exact component source-file declaration;
- dependency/conflict target existence and dependency acyclicity;
- generic capability/lifecycle independence from artifact-specific authorities;
- recipe reference validity and disjoint required/default/optional selections;
- global uniqueness of registered contract IDs, document paths, and schema paths;
- component ownership of every registered contract document/schema/migration;
- a unique generated owner for `contracts/manifest.json`;
- deterministic manifest rendering from resolved `contract_registrations`;
- portable single-owner material destinations; and
- successful materialized validation for production Skill and Webapp compositions.

The catalog is source authority, not consumer material and not an execution-hook registry.

The composer validates this closed source graph, resolves a recipe plus consumer configuration against one exact clean Git revision, and writes the resulting component/file closure to `.template-composition/lock.json` after successful initial materialization. Generated materials are dispatched only through allowlisted declarative generator IDs.

Existing managed repositories are intentionally outside the composer MVP's apply contract: a pre-existing composition lock causes update refusal rather than implicit merge/upgrade behavior.
