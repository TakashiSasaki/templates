# Skill artifact architecture

`artifact.skill-core` represents Agent Skill semantics. It is intentionally not an application-runtime bundle.

## Two independent axes

A concrete Skill has two orthogonal selections:

1. **Skill profile** — instruction, knowledge, assets, helper scripts;
2. **composition capabilities** — runtime, CLI, MCP, MCP Apps, standalone Web, headless service.

This avoids the former flat profile ladder in which an Agent Skill's resource pattern and an application's public interfaces were mixed in one namespace.

## Authority boundaries

`SKILL.md` owns:

- trigger and exclusions;
- prerequisites;
- workflow;
- Skill-specific references/assets/helpers;
- agent-facing preferred route and fallback conditions;
- outputs, validation, safety, and recovery.

Reusable capability contracts own caller-visible interface/runtime semantics. A capability must not depend on `artifact.skill-core`; the same capability may later be selected by a Web application or another artifact type.

## Agent routing

The previous `INTERFACES.md` document mixed two authorities: Skill-specific route selection and generic cross-interface invariants. The composition model removes that file.

Preferred agent route and fallback belong in `SKILL.md`. Semantic equivalence, security, transport, and compatibility remain in each reusable capability contract.

## Resource directories

`references/`, `assets/`, and helper `scripts/` are created only when the concrete Skill selects the corresponding Skill profile. Empty placeholder directories are not part of `artifact.skill-core`.

## Consumer validation

`artifact.skill-core` materializes a small stdlib-only validator and CI workflow. It validates Skill-specific structure and known capability projection. Generic composition-lock semantics remain composer validation responsibility.
