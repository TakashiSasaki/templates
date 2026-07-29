# Optional MCP adapters

Delete this directory when the concrete skill does not expose MCP.

When MCP is supported, this directory may contain:

- a shared MCP server factory or operation registry;
- an stdio server entry point;
- a local Streamable HTTP server entry point;
- an ad hoc MCP client used by the skill or contract tests;
- MCP-specific schemas and adapter tests.

The implementation language is selected in `RUNTIME.md`.

## Standard transport terminology

MCP defines stdio and Streamable HTTP as standard transports. A local server that listens on a TCP port should normally be described as a **local Streamable HTTP MCP server**, not as a raw TCP MCP transport.

A custom raw TCP transport is outside the normal interoperability contract and should only be added with an explicit compatibility requirement.

## Required architecture

Use one shared server factory, operation registry, or equivalent composition root:

```text
                       +--> stdio transport entry point
shared MCP server -----+
factory / registry     +--> Streamable HTTP entry point
                       +--> in-memory or contract-test adapter
```

Transport entry points may configure lifecycle and protocol-specific concerns, but they must not duplicate tool definitions or domain logic.

The MCP adapters must call the same application/domain implementation used by the CLI. Handlers should validate protocol inputs, call the application layer, and translate results.

## stdio variant

Use this variant when an MCP host or bundled ad hoc client owns the server process.

Constraints:

- the host or client launches the server as a child process;
- stdin and stdout carry protocol messages;
- logs and diagnostics go to stderr;
- the server must not daemonize;
- the server must terminate when the client connection closes;
- expensive initialization should be delayed until a tool call requires it;
- no listening socket is opened.

This is normally the preferred variant for an Agent Skill that launches MCP only while performing a particular workflow.

## Local Streamable HTTP variant

Use this variant when the MCP server must run independently and serve one or more clients through a local TCP listening socket.

Default constraints:

- bind to `127.0.0.1` or `::1`;
- expose an explicitly documented endpoint, normally `/mcp`;
- validate the Host header and protect against DNS rebinding;
- define stateless or stateful session behavior;
- define concurrent-client behavior;
- define startup, readiness, shutdown, restart, and stale-process handling;
- keep bind address and port configurable without changing tool behavior;
- do not bind to all interfaces by default;
- do not assume loopback removes every browser-origin risk;
- document authentication before enabling non-loopback access.

Binding to `0.0.0.0` or `::` changes the security model. A concrete skill must not do so merely for convenience. It requires explicit allowed-host/origin policy, authentication, firewall assumptions, and—where traffic leaves the machine—transport-security decisions.

## Ad hoc client behavior

An ad hoc stdio client normally starts and owns the server child process.

An ad hoc Streamable HTTP client normally connects to an already-running local endpoint. It must not silently start another network server unless `INTERFACES.md` explicitly defines that fallback.

An ad hoc client is not automatically a native agent tool. From the host's perspective it is normally a program invoked through a shell or process tool.

## Test requirements

When both variants exist, tests should verify:

- identical tool names and input schemas;
- semantically equivalent results and errors;
- identical workspace and write restrictions;
- clean stdio shutdown on client disconnect;
- local HTTP readiness and shutdown behavior;
- rejection of disallowed hosts or origins;
- loopback bind as the default;
- no transport-specific domain behavior.