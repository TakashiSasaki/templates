---
name: agent-skill-template
description: Template scaffold for designing a portable Agent Skill with a human-facing CLI, optional MCP adapters for stdio and Streamable HTTP, and an optional deployment-neutral human verification Web interface. Use only when creating or restructuring an Agent Skill repository; do not use as an operational domain skill without customization.
---

# Agent Skill Template

This repository is a template, not a completed operational skill.

Before using it as a concrete skill:

1. Rename the skill and update the frontmatter above.
2. Complete `RUNTIME.md`.
3. Complete `INTERFACES.md`.
4. Decide whether a human verification Web interface is supported and complete `WEB_INTERFACE.md` when it is.
5. Replace this template workflow with the concrete skill workflow.
6. Add only the implementation files required by the selected runtime.

## Runtime-independent design rules

- Keep the repository root directly installable as `.agents/skills/<skill-name>/`.
- Put operational instructions in this file.
- Put documents needed during operation under `references/`.
- Put maintainer-only material under `docs/`.
- Keep CLI, MCP, and optional Web adapters thin.
- Implement domain behavior once and share it across all adapters.
- When MCP is supported, explicitly select stdio, an existing Streamable HTTP endpoint, or both.
- Keep stdio and Streamable HTTP server variants semantically equivalent by sharing one server factory or operation registry.
- Route a bundled MCP tool client through an actual MCP server adapter; do not bypass protocol negotiation, framing, transport behavior, or protocol contract tests.
- When a bundled MCP command is provided, state whether it is tools-only or broader in scope; do not imply unsupported resources, prompts, completion, subscriptions, tasks, sampling, elicitation, or roots capabilities.
- Map bundled client commands to standard MCP methods and distinguish local conveniences such as “show” or sequential “run” from protocol methods.
- Record supported MCP revisions, the selected SDK, negotiation behavior, compatibility policy, schema dialects, optional extensions, and supported deployment choices in `RUNTIME.md`.
- Define public CLI and MCP interaction, cancellation, output, exit-code, and fallback behavior in `INTERFACES.md`.
- Preserve complete MCP call results and, for paginated `tools/list`, preserve every raw page result in order; treat a flattened inventory as a separate derived presentation.
- Distinguish modern multi-round-trip `input_required` results from initialization-era server-to-client elicitation requests.
- Document one preferred agent execution path and explicit fallbacks.
- Do not require an agent to infer whether it should use an existing MCP endpoint, launch stdio, invoke a direct CLI, or use a bundled tool client.
- Treat a human verification Web interface as optional. Do not assume a particular process, port, container, Pod, service, gateway, or reverse-proxy topology.
- Permit a debug-only Web interface to share the MCP server process, listener, or container when `WEB_INTERFACE.md` keeps routing, security, health, enablement, and failure behavior logically separate.
- Require a page that claims to verify MCP to traverse the actual MCP client, protocol, transport, and server adapter.
- Do not treat the Web interface as an implicit agent execution path or MCP health check.

## Execution

A concrete skill must replace this section with exact commands copied from `RUNTIME.md` and the selected execution policy from `INTERFACES.md`.

When a Streamable HTTP variant exists, state its endpoint, readiness check, authentication expectations, supported protocol era, and whether the agent may start or stop the server. Do not silently launch a second server when the execution policy requires connecting to an existing endpoint.

When a bundled MCP tool client exists, state the exact command, transport, interaction mode, and whether a command invokes one tool call or several sequential `tools/call` requests. Do not describe local command names as MCP-standard methods.

When a human verification Web interface exists, state whether it is enabled in the current environment. Do not instruct an agent to depend on a debug-only page unless that page is explicitly selected as part of the concrete workflow.

Do not direct an agent to invoke internal modules whose paths may change. Point it to a stable public launcher, declared MCP endpoint, installed command, or explicitly supported Web URL.

## Additional resources

- Runtime decision record: `RUNTIME.md`
- CLI and MCP interface contracts: `INTERFACES.md`
- Optional human Web interface contract: `WEB_INTERFACE.md`
- MCP transport decisions: `docs/mcp-transports.md`
- Operational references: `references/README.md`
