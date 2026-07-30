# Repository instructions

## Repository identity

The repository root is the Agent Skill root. It must remain suitable for installation directly at:

```text
.agents/skills/<skill-name>/
```

Do not add an additional enclosing `skill/` directory.

## Required reading

Before changing implementation or packaging, read:

- `RUNTIME.md`
- `INTERFACES.md`
- `docs/architecture.md`
- `docs/runtime-selection.md`
- `docs/mcp-transports.md`

## Runtime policy

This template is intentionally language-neutral.

- Do not assume Python or Node.js.
- Do not assume uv, pip, npm, pnpm, yarn, or bun.
- Do not add manifests or lockfiles for runtimes that are not selected.
- A concrete skill must record one primary runtime and its exact commands in `RUNTIME.md`.
- Supporting a second runtime requires a documented reason and tests proving equivalent behavior.

## Authority boundaries

- `RUNTIME.md` is the source of truth for language, runtime, package manager, MCP SDK, supported protocol revisions, compatibility policy, transport modes, and exact commands.
- `INTERFACES.md` is the source of truth for public commands, structured output, exit codes, interaction behavior, and deterministic fallback order.
- `SKILL.md` contains the operational instructions an agent actually follows.
- Maintainer documents explain rationale but must not silently redefine public contracts.

Do not duplicate revision or SDK selections in several files. Reference `RUNTIME.md` from public contracts and update all affected documents when behavior changes.

## Architecture

Separate these concerns:

1. `SKILL.md`: when and how an agent should use the skill.
2. CLI adapter: human terminal interface and optional stable agent launcher.
3. Bundled MCP tool client: a bounded protocol client that invokes MCP server adapters.
4. MCP server factory or operation registry: shared server-side tool definitions.
5. stdio MCP adapter: child-process transport and revision-aware lifecycle.
6. Streamable HTTP MCP adapter: independently managed local network transport and revision-aware request handling.
7. Application/domain implementation: reusable behavior.
8. Tests: contract, adapter, integration, transport, compatibility, and security verification.

The CLI and MCP server adapters must call the same application logic. stdio and Streamable HTTP adapters must share tool definitions rather than registering parallel copies. The bundled tool client must exercise the actual MCP path and must not call the application layer directly while claiming an MCP invocation.

## Interface policy

`INTERFACES.md` must state:

- the canonical human CLI command;
- the canonical in-place agent command, if different;
- the stdio MCP server launch command, if supported;
- the bundled MCP tool-client command and supported transports, if supported;
- the local Streamable HTTP server start, stop, endpoint, and readiness contract, if supported;
- the preferred agent interface and deterministic fallback order;
- lossless and presentation-oriented output formats;
- exit-code meanings, including non-interactive additional-input behavior;
- legacy elicitation behavior and modern multi-round-trip behavior when either is supported.

An agent must not be left to choose arbitrarily between equivalent execution paths. In particular, it must know whether to connect to an existing local endpoint, launch stdio through the bundled client, or use the CLI.

## MCP protocol requirements

A concrete skill must verify the current official MCP specification and selected SDK before implementation. At the time this template was aligned:

- `2026-07-28` is the current modern revision with stateless, self-contained requests and `server/discover`;
- `2025-11-25` and earlier revisions use the `initialize` / `notifications/initialized` lifecycle.

The template does not require support for both eras. Every claimed revision and negotiation path must be tested.

When stdio MCP exists:

- stdout is reserved for MCP protocol traffic;
- diagnostics and logs go to stderr;
- startup performs no expensive repository-wide scan;
- shutdown follows the selected SDK and revision, with bounded escalation if a child process does not exit;
- paths are resolved and constrained to the allowed workspace policy;
- tools expose narrow domain operations, not arbitrary shell execution.

When Streamable HTTP MCP exists:

- call it Streamable HTTP, not raw TCP, unless a non-standard transport is intentional;
- bind to `127.0.0.1` or `::1` by default;
- do not bind to `0.0.0.0` or `::` merely for convenience;
- define endpoint path, port policy, revision-specific state behavior, concurrency, readiness, cancellation, and shutdown;
- validate Host headers and protect against DNS rebinding;
- validate `Origin` and reject a present disallowed origin with HTTP 403;
- document the handling of requests without `Origin`;
- when supporting `2026-07-28`, implement required request metadata headers, JSON and SSE responses, and `x-mcp-header` processing;
- require explicit authentication and network-security decisions before non-loopback access;
- keep HTTP and service-management concerns out of the application/domain layer.

## Completion criteria

Before reporting a change complete:

1. Update `SKILL.md` when operational behavior changes.
2. Update `RUNTIME.md` when commands, runtimes, SDKs, protocol revisions, endpoints, or service lifecycle change.
3. Update `INTERFACES.md` when public CLI or MCP behavior changes.
4. Update `AGENTS.md` and maintainer docs when architecture or contributor rules change.
5. Run the selected runtime's tests and static checks.
6. Verify CLI, stdio MCP, and Streamable HTTP MCP semantic equivalence under the same revision, identity, authorization, configuration, and workspace policy.
7. Test every claimed negotiation and fallback path.
8. Test lossless result preservation, pagination, cancellation, additional-input behavior, and any claimed extension.
9. Test loopback binding and host/origin rejection when the network variant exists.
10. Confirm generated files and lockfiles correspond only to selected tooling.
11. Review the final repository as if it were cloned directly into `.agents/skills/<skill-name>/`.
