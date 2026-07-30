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
- `WEB_INTERFACE.md`
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

- `RUNTIME.md` is the source of truth for language, runtime, package manager, MCP SDK, supported protocol revisions, compatibility policy, transport modes, supported deployment choices, and exact commands.
- `INTERFACES.md` is the source of truth for public CLI and MCP commands, structured output, exit codes, interaction behavior, and deterministic fallback order.
- `WEB_INTERFACE.md` is the source of truth for an optional browser-facing verification, debugging, demonstration, or limited-operations interface.
- `SKILL.md` contains the operational instructions an agent actually follows.
- Maintainer documents explain rationale but must not silently redefine public contracts.

Do not duplicate revision, SDK, or deployment selections in several files. Reference the authoritative record and update all affected documents when behavior changes.

## Architecture

Separate these concerns:

1. `SKILL.md`: when and how an agent should use the skill.
2. CLI adapter: human terminal interface and optional stable agent launcher.
3. Optional human verification Web interface: browser-facing presentation and, when needed, a backend-for-frontend.
4. Bundled MCP tool client: a bounded protocol client that invokes MCP server adapters.
5. MCP server factory or operation registry: shared server-side tool definitions.
6. stdio MCP adapter: child-process transport and revision-aware lifecycle.
7. Streamable HTTP MCP adapter: network transport and revision-aware request handling.
8. Application/domain implementation: reusable behavior.
9. Tests: contract, adapter, integration, transport, compatibility, security, and deployment-topology verification.

The CLI and MCP server adapters must call the same application logic. stdio and Streamable HTTP adapters must share tool definitions rather than registering parallel copies. The bundled tool client must exercise the actual MCP path and must not call the application layer directly while claiming an MCP invocation.

A human page that claims to verify MCP must also traverse the actual MCP client, protocol, transport, and server adapter. It may reuse the same MCP client library and result representations as the bundled tool client.

## Optional human Web interface policy

Do not assume that a Web interface exists. When it is supported, complete `WEB_INTERFACE.md` and record its runtime commands and supported deployment choices in `RUNTIME.md`.

The final process, port, container, Pod, service, gateway, or reverse-proxy topology may remain deployment-selected. The template must support documenting a set of valid topologies instead of forcing one prematurely.

A debug-only Web interface may share the MCP server process, listener, or container. Even in that arrangement:

- keep the UI, UI backend, MCP endpoint, and health endpoints as separate logical interfaces;
- make enablement explicit and normally disabled outside development or diagnostics;
- avoid loading UI-only assets and debug state when the UI is disabled;
- keep authentication, authorization, routing, logging, redaction, and error handling explicit;
- do not equate Web UI readiness with MCP readiness;
- do not let a successful Web page response stand in for an MCP invocation test;
- do not expose mutating or destructive tools without trusted local policy and confirmation rules.

A separate port is optional. Shared-listener routing and reverse-proxy routing are valid when their security boundaries and path behavior are documented and tested.

## Interface policy

`INTERFACES.md` must state:

- the canonical human CLI command;
- the canonical in-place agent command, if different;
- the stdio MCP server launch command, if supported;
- the bundled MCP tool-client command and supported transports, if supported;
- the Streamable HTTP server start, stop, endpoint, and readiness contract, if supported;
- the preferred agent interface and deterministic fallback order;
- lossless and presentation-oriented output formats;
- for paginated `tools/list`, an ordered lossless page representation that preserves every raw page result separately from any flattened inventory view;
- exit-code meanings, including non-interactive additional-input behavior;
- legacy elicitation behavior and modern multi-round-trip behavior when either is supported.

`WEB_INTERFACE.md` must state, when supported:

- purpose and default enablement;
- production availability policy;
- supported deployment topologies without requiring a premature final choice;
- listener, path, port, and reverse-proxy options;
- whether the backend acts as an MCP client or the browser calls MCP directly;
- authentication, authorization, tool visibility, confirmation, and redaction policy;
- independent Web and MCP readiness behavior;
- tests for each claimed exposure and deployment mode.

An agent must not be left to choose arbitrarily between equivalent execution paths. It must know whether to connect to an existing endpoint, launch stdio through the bundled client, or use the CLI. The human Web interface is not an implicit agent fallback unless explicitly selected as one.

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
- bind to `127.0.0.1` or `::1` by default for local-only deployment;
- do not bind to `0.0.0.0` or `::` merely for convenience;
- define endpoint path, port policy, revision-specific state behavior, concurrency, readiness, cancellation, and shutdown;
- validate Host headers and protect against DNS rebinding;
- validate `Origin` on every HTTP request before dispatch, not once per accepted connection;
- repeat Origin validation for each request on HTTP keep-alive connections and for each request or stream on multiplexed HTTP connections;
- return HTTP 403 for every request with a present disallowed Origin;
- document handling of requests without `Origin`;
- when supporting `2026-07-28`, implement required request metadata headers, JSON and SSE responses, and `x-mcp-header` processing;
- require explicit authentication and network-security decisions before non-loopback access;
- keep HTTP and service-management concerns out of the application/domain layer.

Connection reuse must not reuse an earlier request's Origin decision. Host, Origin, authentication, authorization, and protocol-header validation must be request-scoped.

## Completion criteria

Before reporting a change complete:

1. Update `SKILL.md` when operational behavior changes.
2. Update `RUNTIME.md` when commands, runtimes, SDKs, protocol revisions, endpoints, supported topologies, or service lifecycle change.
3. Update `INTERFACES.md` when public CLI or MCP behavior changes.
4. Update `WEB_INTERFACE.md` when browser-facing behavior, enablement, security, or deployment support changes.
5. Update `AGENTS.md` and maintainer docs when architecture or contributor rules change.
6. Run the selected runtime's tests and static checks.
7. Verify CLI, stdio MCP, and Streamable HTTP MCP semantic equivalence under the same revision, identity, authorization, configuration, and workspace policy.
8. Test every claimed negotiation and fallback path.
9. Test ordered per-page `tools/list` preservation separately from flattened inventory presentation, including page-specific cursors, cache hints, `_meta`, and unknown fields.
10. Test lossless call-result preservation, cancellation, additional-input behavior, and any claimed extension.
11. Test loopback binding, request-scoped Host/Origin validation, and rejection behavior when the network variant exists.
12. Include a connection-reuse test that sends at least two requests over one keep-alive or multiplexed connection with different Origin values and verifies HTTP 403 for every present disallowed Origin.
13. When the Web interface exists, test disabled-by-default behavior, actual MCP-path verification, independent health checks, security policy, redaction, and each claimed topology or deployment-specific smoke test.
14. Confirm generated files and lockfiles correspond only to selected tooling.
15. Review the final repository as if it were cloned directly into `.agents/skills/<skill-name>/`.
