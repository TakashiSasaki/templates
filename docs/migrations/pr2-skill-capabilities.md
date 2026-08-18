# PR2 Skill capability migration

## Purpose

PR2 performs the second composition-migration stage: move Agent Skill application/runtime concerns out of the monolithic `skill` template and establish them as reusable production composition authorities.

This is an authority migration, not a history merge. The unrelated `skill` branch is read as source material only.

## Source snapshots

- composition base after PR1: `0395a43c07382118b46ef1537d34cb31c402bf35`
- Skill source snapshot: `b8b735dbe525ca76316fec445cdce43db02a955e`

The legacy branch remains unchanged and authoritative for its old distribution until a later cutover. PR2 does not merge, rebase, or cherry-pick its history into `composition`.

## Production authorities introduced

### Skill artifact

`artifact.skill-core` owns only Skill semantics:

- trigger and exclusions;
- prerequisites and workflow;
- operational references, static assets, and bounded helper scripts;
- preferred agent route and fallback conditions;
- outputs, validation, safety, and recovery;
- Skill-specific structural validation.

The Skill profile namespace is reduced to:

- `instruction-only`;
- `knowledge-augmented`;
- `asset-driven`;
- `script-assisted`.

### Generic capabilities

| New authority | Legacy source responsibility |
|---|---|
| `capability.runtime` | `RUNTIME.md` runtime, commands, dependency, distribution, environment, deployment |
| `capability.cli` | `CLI_INTERFACE.md` caller-visible packaged CLI |
| `capability.mcp` | `MCP_INTERFACE.md` plus `docs/mcp-transports.md` |
| `capability.mcp-apps` | `MCP_APPS.md` plus `docs/mcp-apps.md` |
| `capability.web-interface` | `WEB_INTERFACE.md` standalone browser interface |
| `capability.service` | headless-service caller/security/health behavior formerly embedded in `RUNTIME.md` |

Capability dependency graph:

```text
capability.cli ----------> capability.runtime
capability.mcp ----------> capability.runtime
capability.mcp-apps -----> capability.mcp ----> capability.runtime
capability.web-interface -> capability.runtime
capability.service ------> capability.runtime
```

No generic capability depends on `artifact.skill-core`.

## `INTERFACES.md` decomposition

The legacy `INTERFACES.md` mixed two authorities.

Skill-specific behavior moves to `SKILL.md`:

- preferred agent interface;
- deterministic fallback order;
- route availability/fallback conditions.

Generic behavior remains with reusable capabilities:

- caller-visible interface semantics;
- semantic equivalence;
- authentication/authorization preservation;
- transport/security behavior;
- failure classification.

`INTERFACES.md` is therefore not materialized by the new Skill recipe.

## Ownership choices

Concrete consumer decision records use `seed` ownership because the consumer must complete them for its own runtime/interface choices.

Reusable implementation guidance uses `managed` ownership because the composition source remains authoritative for that guidance.

The Skill validator and validation workflow are `managed`; Skill instructions and repository-local decision material are `seed`.

## Validator simplification

The legacy Skill distribution accumulated a large matrix of profile-specific validators. PR2 does not preserve that compatibility surface.

`artifact.skill-core` instead materializes a small stdlib-only validator under `.github/scripts/validate_skill.py`. It validates:

- Skill frontmatter;
- the four-profile model;
- declared references/assets/helper scripts;
- rejection of retired application profile tags;
- capability-contract dependency relationships;
- retirement of `INTERFACES.md`; and
- known capability/file projection against the composition lock when one exists.

The validator lives under `.github/scripts/` rather than `scripts/` so that the consumer `scripts/` namespace remains reserved for actual `script-assisted` helpers. This allows an `instruction-only` Skill to retain structural validation without falsely becoming script-assisted.

## Minimal resource layout

Empty placeholder `references/`, `assets/`, and helper `scripts/` directories are not materialized. Concrete Skills create those directories only when the corresponding Skill profile is selected.

This makes the generated artifact smaller and prevents unused template scaffolding from being mistaken for an active resource contract.

## Production catalog

PR2 adds the first closed production catalog. It includes `artifact.skill-core`, the six capabilities, and the `skill` recipe.

Source validation proves:

- exact catalog/path closure;
- component/recipe schema validity;
- exact copied-source inventory;
- dependency existence and acyclicity;
- recipe reference validity;
- known capability dependency closure;
- portable destination ownership for the full Skill capability set;
- successful validation of both the minimal Skill scaffold and a fully capability-composed Skill projection; and
- explicit rejection of retired application profile tags.

## Deliberately deferred

PR2 does not:

- migrate Webapp artifact semantics;
- migrate Webapp-derived lifecycle contracts;
- implement a general resolver/composer;
- generate production composition locks;
- implement update/merge behavior;
- change Site publication;
- change `policy`;
- modify or retire the legacy `skill` or `webapp` branches.

Those belong to later migration stages.
