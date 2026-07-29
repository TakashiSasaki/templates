---
name: agent-skill-template
description: Template scaffold for designing a portable Agent Skill with a human-facing CLI and an optional stdio MCP adapter. Use only when creating or restructuring an Agent Skill repository; do not use as an operational domain skill without customization.
---

# Agent Skill Template

This repository is a template, not a completed operational skill.

Before using it as a concrete skill:

1. Rename the skill and update the frontmatter above.
2. Complete `RUNTIME.md`.
3. Complete `INTERFACES.md`.
4. Replace this template workflow with the concrete skill workflow.
5. Add only the implementation files required by the selected runtime.

## Runtime-independent design rules

- Keep the repository root directly installable as `.agents/skills/<skill-name>/`.
- Put operational instructions in this file.
- Put documents needed during operation under `references/`.
- Put maintainer-only material under `docs/`.
- Keep CLI and MCP adapters thin.
- Implement domain behavior once and share it across all adapters.
- Document one preferred agent execution path and explicit fallbacks.
- Do not require an agent to infer whether it should use a direct CLI or an ad hoc MCP client.

## Execution

A concrete skill must replace this section with exact commands copied from `RUNTIME.md` and the selected execution policy from `INTERFACES.md`.

Do not direct an agent to invoke internal modules whose paths may change. Point it to a stable public launcher or installed command.

## Additional resources

- Runtime decision record: `RUNTIME.md`
- Interface contracts: `INTERFACES.md`
- Operational references: `references/README.md`
