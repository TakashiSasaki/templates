# Agent Skill composition recipe

This scaffold is the Skill artifact produced by the `skill` composition recipe.

## New to Composition? Start with the worked example

If you are creating your first Agent Skill, follow the [Agent Skill first-use walkthrough](../../../docs/guides/skill-first-use-walkthrough.md) from a separate consumer repository. It starts with installation and `composition.json`, walks through `inspect -> plan -> apply -> validate`, explains concrete ownership, then turns the scaffold into a real knowledge-augmented Skill with a declared `references/` resource.

The initial Composition-valid scaffold is not yet an operational Skill: replace the `template-scaffold` sentinel and TODO semantics before treating the repository as a concrete Skill.

## Artifact model

The architecture separates:

- **Skill semantics** in `artifact.skill-core`: trigger, workflow, resources, agent routing, outputs, and safety;
- **application capabilities** such as runtime, CLI, MCP, MCP Apps, standalone Web, and headless service in reusable `capability.*` components.

A simple Skill does not need an application runtime. Start from `SKILL.md`; add references, assets, or helper scripts only when the workflow requires them. Select application capabilities through composition rather than by retaining unused interface documents.

## Skill profiles

Skill-specific profiles are deliberately small:

- `instruction-only`;
- `knowledge-augmented`;
- `asset-driven`;
- `script-assisted`.

The old `packaged-cli`, `mcp-enabled`, `browser-interface`, and `headless-service` profile tags are not part of the new Skill profile model. Their responsibilities live in composition capabilities.

The uncustomized seed uses `Selected profiles: template-scaffold` as a scaffold sentinel. It is **not** a fifth concrete Skill profile. Replace it before the repository becomes an operational Skill; concrete Skills may use only the four profiles above.

## Public interfaces

When a capability is selected, complete its materialized contract and summarize the preferred agent route/fallback in `SKILL.md`.

`INTERFACES.md` is intentionally not part of the new artifact. Agent routing belongs to the Skill; caller-visible interface behavior belongs to generic capability contracts.

## Validation

Run:

```sh
python .github/scripts/validate_skill.py .
```

The validator checks frontmatter, Skill-profile selection, declared resource paths, capability-file dependency relationships, and—when present—the projection of known composition capabilities from `.template-composition/lock.json`.

The composition lock itself remains composer-owned and is validated by the composition validation contract.
