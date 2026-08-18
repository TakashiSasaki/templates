# Agent instructions for a concrete Skill repository

This repository represents one Agent Skill artifact.

## Authority

- `SKILL.md` owns trigger, workflow, Skill-specific resources, agent routing, outputs, and safety.
- `RUNTIME.md` owns runtime, commands, dependencies, environment, distribution, and deployment when materialized.
- `CLI_INTERFACE.md`, `MCP_INTERFACE.md`, `MCP_APPS.md`, `WEB_INTERFACE.md`, and `SERVICE_INTERFACE.md` own their caller-visible capability contracts when present.
- `.template-composition/lock.json`, when present, is composer-owned resolved state. Do not hand-edit it.

Do not duplicate an interface contract into `SKILL.md`. Summarize only the preferred route and fallback conditions needed by the agent.

## Minimality

Keep only the Skill-specific resource structures actually needed by the concrete workflow:

- create `references/` for maintained operational knowledge;
- create `assets/` for static resources;
- create `scripts/` for bounded helper scripts.

Do not recreate removed legacy profile files merely to resemble the old monolithic template.

## Editing rules

- Replace `template-scaffold` in `SKILL.md` before treating the repository as an operational Skill.
- Keep frontmatter `name` and `description` concrete and trigger-oriented.
- Make side effects, permissions, approvals, and retry/idempotency behavior explicit.
- Do not weaken authentication, authorization, confirmation, workspace, or write restrictions when adding interface fallbacks.
- When several interfaces expose the same operation, preserve semantic equivalence and share tested domain logic where justified.

## Validation

Run `python .github/scripts/validate_skill.py .` after structural changes. Run capability-specific tests required by every selected interface contract before release.
