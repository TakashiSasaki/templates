# Composition component maintenance

These instructions apply to maintenance work under `components/` in the
Composition authority. They do not define consumer-repository behavior by
themselves; component descriptors, schemas, validators, and material bytes
remain the semantic sources for the artifacts that Composition produces.

## Distribution material boundary

- Treat `components/<component-id>/files/**` as distribution/materialization
  source data for consumer repositories, not as repository-maintainer
  instructions for `TakashiSasaki/templates`.
- Do not add an exact file named `AGENTS.md` anywhere below a component
  `files/**` tree. An exact instruction filename there can be discovered as
  active instructions while an agent is editing Composition source.
- When a component must materialize consumer-root `AGENTS.md`, store the
  source under a non-discoverable material name such as
  `files/AGENTS.md.template` and declare `"destination": "AGENTS.md"` in
  that component's `component.json`.
- Consumer-facing instruction prose in such a template is data owned by the
  artifact contract. Do not interpret it as permission or procedure for
  maintaining this Composition repository.
- Keep the source filename, descriptor destination, ownership mode, and
  materialized consumer bytes conceptually separate during review.

## Descriptor and ownership changes

`component.json` is the Composition authority for each material's source,
destination, and ownership mode. A descriptor-byte change requires the
component version to increase under the repository's component-version guard.
Do not alter `managed`, `generated`, or `seed` ownership merely to avoid a
validation failure.

When changing a material path, verify both sides of the contract:

1. the repository source path is safe and intentionally named for maintainer
   discovery behavior; and
2. the consumer destination remains the artifact path required by the
   component contract.

## Validation

Run the focused boundary tests after changing component instruction material:

```text
python -m unittest tests.test_component_agent_instruction_boundary tests.test_component_version_guard
```

Then run the normal Composition construction preflight required by the root
maintainer instructions:

```text
python3 scripts/run_composition_preflight.py fast
```

Materialization behavior must be checked through the Composer; a source rename
alone is not evidence that the consumer destination is unchanged.
