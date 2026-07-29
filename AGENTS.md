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

## Architecture

Separate these concerns:

1. `SKILL.md`: when and how an agent should use the skill.
2. CLI adapter: human terminal interface and optional agent launcher.
3. MCP server factory or operation registry: shared tool definitions.
4. stdio MCP adapter: child-process transport and lifecycle.
5. Streamable HTTP MCP adapter: independently managed local network transport and lifecycle.
6. Application/domain implementation: reusable behavior.
7. Tests: contract, adapter, integration, transport, and security verification.

CLI and MCP adapters must call the same application logic. stdio and Streamable HTTP adapters must share tool definitions rather than registering parallel copies.

## Interface policy

`INTERFACES.md` is the contract index. It must state:

- the canonical human CLI command;
- the canonical in-place agent command, if different;
- the stdio MCP server launch command, if supported;
- the ad hoc stdio MCP client command, if supported;
- the local Streamable HTTP server start, stop, endpoint, and readiness contract, if supported;
- the Streamable HTTP client command, if supported;
- the preferred agent interface and deterministic fallback order;
- output formats and exit-code meanings.

An agent must not be left to choose arbitrarily between equivalent execution paths. In particular, it must know whether to connect to an existing local endpoint, launch stdio ad hoc, or use the CLI.

## stdio MCP requirements

When an stdio MCP server exists:

- stdout is reserved for MCP protocol traffic;
- diagnostics and logs go to stderr;
- startup performs no expensive repository-wide scan;
- the process exits when stdin closes;
- paths are resolved and constrained to the allowed workspace;
- tools expose narrow domain operations, not arbitrary shell execution.

## Local Streamable HTTP MCP requirements

When an independently running local MCP server exists:

- call it a Streamable HTTP transport, not a raw TCP transport, unless a non-standard custom transport is intentional;
- bind to `127.0.0.1` or `::1` by default;
- do not bind to `0.0.0.0` or `::` merely for convenience;
- define endpoint path, port policy, session mode, concurrency, readiness, and shutdown behavior;
- validate Host headers and protect against DNS rebinding;
- define allowed origins when browser-based clients are possible;
- require explicit authentication and network-security decisions before non-loopback access;
- keep HTTP and service-management concerns out of the application/domain layer;
- test semantic equivalence with the stdio adapter and CLI.

## Completion criteria

Before reporting a change complete:

1. Update `SKILL.md` when operational behavior changes.
2. Update `RUNTIME.md` when commands, runtimes, package managers, endpoints, or service lifecycle change.
3. Update `INTERFACES.md` when CLI or MCP contracts change.
4. Run the selected runtime's tests and static checks.
5. Verify CLI, stdio MCP, and Streamable HTTP MCP semantic equivalence for every supported operation.
6. Test loopback binding and host/origin rejection when the network variant exists.
7. Confirm generated files and lockfiles correspond only to selected tooling.
8. Review the final repository as if it were cloned directly into `.agents/skills/<skill-name>/`.