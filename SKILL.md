---
name: agent-skill-template
description: Template scaffold for designing a portable Agent Skill with a human-facing CLI and optional MCP adapters for ad hoc stdio and independently managed local Streamable HTTP. Use only when creating or restructuring an Agent Skill repository; do not use as an operational domain skill without customization.
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
- When MCP is supported, explicitly select ad hoc stdio, an existing local Streamable HTTP endpoint, or both.
- Keep stdio and Streamable HTTP variants semantically equivalent by sharing one server factory or operation registry.
- When a bundled MCP command is provided, state whether it is a tools-only client or a broader MCP client; do not imply unsupported resources, prompts, completion, subscriptions, tasks, sampling, elicitation, or roots capabilities.
- Map bundled client commands to standard MCP methods and distinguish local conveniences such as “show” or sequential “run” from protocol methods.
- Declare supported MCP protocol revisions, negotiation behavior, optional features, interaction policy, and cancellation behavior in `RUNTIME.md` and `INTERFACES.md`.
- Preserve standard MCP result fields and distinguish JSON-RPC protocol errors from tool execution results with `isError`.
- Document one preferred agent execution path and explicit fallbacks.
- Do not require an agent to infer whether it should use an existing MCP endpoint, launch stdio, invoke a direct CLI, or use an ad hoc client.

## Execution

A concrete skill must replace this section with exact commands copied from `RUNTIME.md` and the selected execution policy from `INTERFACES.md`.

When a local Streamable HTTP variant exists, state its endpoint, readiness check, authentication expectations, and whether the agent may start or stop the server. Do not silently launch a second server when the execution policy requires connecting to an existing endpoint.

When a bundled MCP tool client exists, state the exact command, transport, supported protocol revisions, interaction mode, and whether a command invokes one tool call or several sequential `tools/call` requests. Do not describe local command names as MCP-standard methods.

Do not direct an agent to invoke internal modules whose paths may change. Point it to a stable public launcher, declared MCP endpoint, or installed command.

## Additional resources

- Runtime decision record: `RUNTIME.md`
- Interface contracts: `INTERFACES.md`
- MCP transport decisions: `docs/mcp-transports.md`
- Operational references: `references/README.md`
