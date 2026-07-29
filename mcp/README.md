# Optional MCP adapters

Delete this directory when the concrete skill does not expose MCP.

When MCP is supported, this directory may contain:

- a shared MCP server factory or operation registry;
- an stdio server entry point;
- a local Streamable HTTP server entry point;
- a bounded ad hoc MCP tool client used by the skill or contract tests;
- MCP-specific schemas and adapter tests.

The implementation language is selected in `RUNTIME.md`.

## Standard transport terminology

MCP defines stdio and Streamable HTTP as standard transports. A local server that listens on a TCP port should normally be described as a **local Streamable HTTP MCP server**, not as a raw TCP MCP transport.

A custom raw TCP transport is outside the normal interoperability contract and should only be added with an explicit compatibility requirement.

Protocol revision is separate from transport. Complete the supported revisions, SDK version, negotiation policy, and optional extensions in `RUNTIME.md` and `INTERFACES.md`.

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

A bundled tool client must drive these entry points through MCP rather than bypassing the protocol and calling the application layer directly.

## stdio variant

Use this variant when an MCP host or bundled tool client owns the server process.

Constraints:

- the host or client launches the server as a child process;
- stdin and stdout carry protocol messages;
- logs and diagnostics go to stderr;
- the server must not daemonize;
- the server must terminate when the client connection or invocation closes;
- the client and server must perform the lifecycle or discovery exchange required by the selected protocol revision;
- expensive initialization should be delayed until an operation requires it;
- no listening socket is opened.

This is normally the preferred variant for an Agent Skill that launches MCP only while performing a particular workflow.

## Local Streamable HTTP variant

Use this variant when the MCP server must run independently and serve one or more clients through a local TCP listening socket.

Default constraints:

- bind to `127.0.0.1` or `::1`;
- expose an explicitly documented endpoint, normally `/mcp`;
- validate the Host header and protect against DNS rebinding;
- validate `Origin` on every incoming connection and reject a present disallowed origin with HTTP 403;
- document how an absent `Origin` is handled for non-browser clients;
- define revision-specific state behavior rather than assuming the transport is always stateful or stateless;
- define concurrent-client behavior;
- define startup, readiness, cancellation, shutdown, restart, and stale-process handling;
- keep bind address and port configurable without changing tool behavior;
- do not bind to all interfaces by default;
- do not assume loopback removes every browser-origin risk;
- document authentication before enabling non-loopback access.

Binding to `0.0.0.0` or `::` changes the security model. A concrete skill must not do so merely for convenience. It requires explicit allowed-host/origin policy, authentication, firewall assumptions, and—where traffic leaves the machine—transport-security decisions.

## Ad hoc MCP tool-client behavior

A bundled command that only discovers and invokes tools is an **ad hoc MCP tool client**. It is not automatically a native agent tool or a complete MCP host. From the host's perspective it is normally a program invoked through a shell or process tool.

For stdio, the client normally starts and owns the trusted server child process. For Streamable HTTP, it normally connects to an already-running endpoint. It must not silently start another network server unless `INTERFACES.md` explicitly defines that fallback.

The client CLI is local to the skill. Recommended operations map as follows:

| Local operation | MCP behavior |
|---|---|
| `server-info` | Revision-appropriate lifecycle or discovery exchange |
| `tools list` | `tools/list`, including opaque cursor pagination |
| `tools show TOOL` | Local filtering over `tools/list`; not an MCP method |
| `tools call TOOL` | One `tools/call` request |
| `tools run` | Several independent `tools/call` requests; not an MCP or JSON-RPC batch method |

The client must:

- declare supported protocol revisions and negotiation behavior;
- preserve standard tool definitions and result fields, including `content`, `structuredContent`, `isError`, and `_meta` when present;
- distinguish transport failures, protocol errors, returned tool errors, and successful results;
- treat tool annotations from untrusted servers as hints;
- keep tool names case-sensitive and cursors opaque;
- expose a lossless MCP JSON output mode;
- document additional-input behavior for non-interactive, interactive, and response-file use;
- apply revision-appropriate cancellation and clean up requests, connections, and child processes;
- capability-gate tasks and extensions;
- avoid arbitrary server shell commands and caller-selected JSON-RPC request IDs;
- distinguish MCP roots from skill-specific workspace configuration.

Do not add resources, prompts, completion, subscriptions, tasks, sampling, elicitation, roots, or other client features merely to make the client appear complete. Implement and advertise only what the concrete skill needs and tests.

## Test requirements

When both variants or a bundled tool client exist, tests should verify:

- every claimed protocol revision and negotiation path;
- identical tool names and input schemas across transports;
- complete `tools/list` pagination;
- semantically equivalent results and errors;
- preservation of MCP result and extension fields;
- correct separation of transport, protocol, and `isError` failures;
- identical workspace and write restrictions;
- clean stdio shutdown on client disconnect;
- timeout cancellation and process cleanup;
- documented non-interactive handling of additional-input results;
- any claimed task or extension behavior;
- local HTTP readiness and shutdown behavior;
- rejection of disallowed hosts or origins;
- loopback bind as the default;
- no transport-specific domain behavior;
- confirmation that `tools show` and `tools run` remain local conveniences rather than nonexistent MCP methods.
