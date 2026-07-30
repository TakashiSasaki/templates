# Optional MCP adapters

Delete this directory when the concrete skill does not expose MCP.

When MCP is supported, this directory may contain:

- a shared MCP server factory or operation registry;
- a stdio server entry point;
- a local Streamable HTTP server entry point;
- a bounded ad hoc MCP tool client used by the skill or contract tests;
- MCP-specific schemas and adapter tests.

The implementation language, SDK, protocol revisions, compatibility policy, and exact commands are selected in `RUNTIME.md`.

## Standard terminology

MCP defines stdio and Streamable HTTP as standard transports. A local server that listens on a TCP port should normally be described as a **local Streamable HTTP MCP server**, not as a raw TCP MCP transport.

A command that only discovers and invokes tools is an **ad hoc MCP tool client**. It is not automatically a native agent tool, complete MCP host, or general-purpose MCP client.

At the time this template was aligned, `2026-07-28` is the modern stateless, per-request revision, while `2025-11-25` and earlier revisions use the initialization-era protocol model. Recheck the current specification before implementation.

## Required architecture

```text
shared MCP server factory / registry
              |
              +--> stdio server adapter
              +--> Streamable HTTP server adapter
              +--> in-memory or contract-test adapter

bundled MCP tool client
              |
              +--> stdio server adapter
              +--> existing Streamable HTTP endpoint
```

Transport entry points may configure protocol, lifecycle, framing, request metadata, cancellation, and security. They must not duplicate tool definitions or domain logic.

The MCP server adapters call the same application/domain implementation used by the CLI. The bundled tool client must traverse an MCP adapter rather than call the application layer directly.

## stdio implementation checklist

- launch only a trusted bundled server command;
- reserve stdout for MCP protocol messages;
- send diagnostics to stderr;
- do not daemonize or open a listening socket;
- perform the discovery or initialization behavior required by the selected revision;
- implement only advertised server-to-client capabilities;
- use revision-appropriate cancellation;
- close stdin or the connection according to the SDK contract;
- wait for process exit and use bounded shutdown escalation;
- avoid hidden application-state assumptions across calls.

## Streamable HTTP implementation checklist

General requirements:

- bind to `127.0.0.1` or `::1` by default;
- expose a documented endpoint, normally `/mcp`;
- validate Host and protect against DNS rebinding;
- validate Origin and reject a present disallowed value with HTTP 403;
- document absent-Origin behavior;
- define supported protocol eras, concurrency, readiness, cancellation, and shutdown;
- require a separate security design for non-loopback access.

For `2026-07-28` support:

- use one POST for each JSON-RPC request;
- accept both JSON and SSE response media types;
- send required protocol-version and method/name request headers;
- keep request headers consistent with JSON body metadata;
- support request-scoped SSE cancellation;
- do not use modern-mode session IDs, independent GET/DELETE endpoints, or resumability;
- validate `x-mcp-header` tool declarations;
- exclude invalid HTTP tool definitions from the usable inventory;
- move designated arguments into encoded `Mcp-Param-*` headers;
- test any initialization-era compatibility separately.

## Bundled tool-client behavior

Recommended local operations:

| Local operation | MCP behavior |
|---|---|
| `server-info` | Modern `server/discover` or initialization-era negotiated server information |
| `tools list` | `tools/list` with complete opaque-cursor pagination |
| `tools show TOOL` | Local filtering over `tools/list`; not an MCP method |
| `tools call TOOL` | One `tools/call` request |
| `tools run` | Several independent `tools/call` requests; not an MCP or JSON-RPC batch |

The client must:

- preserve complete list and call result objects, including `resultType`, cache fields, `_meta`, and unknown extensions;
- keep tool names case-sensitive and cursors opaque;
- support JSON Schema 2020-12 where required;
- accept any permitted JSON type in `structuredContent`;
- distinguish transport, protocol, invalid-result, input-required, tool-error, and success outcomes;
- generate request IDs internally;
- avoid arbitrary server shell commands;
- capability-gate tasks, elicitation, sampling, roots, and other features;
- distinguish MCP roots from skill-specific workspace configuration.

## Additional input

Modern `2026-07-28` multi-round-trip behavior:

- preserve an `input_required` result in non-interactive mode;
- in interactive or response-file mode, retry with `inputResponses` and echoed `requestState`;
- use a new JSON-RPC request ID for every retry.

Initialization-era behavior:

- advertise elicitation or other client capabilities only when implemented;
- answer form elicitation with `accept`, `decline`, or `cancel`;
- document automatic decline or cancellation in non-interactive mode;
- wait for the original request's final result;
- do not synthesize a modern input-required result.

## Test requirements

Test every claimed revision, transport, and optional feature. At minimum verify:

- negotiation and compatibility fallback;
- equivalent operations under the same identity, authorization, configuration, and workspace policy;
- full pagination and cache scope;
- schema dialects and `structuredContent` types;
- lossless result and unknown-field preservation;
- modern multi-round-trip and legacy elicitation behavior;
- cancellation, maximum timeout, and child-process cleanup;
- modern HTTP headers, JSON/SSE responses, and `x-mcp-header`;
- loopback binding, Host/Origin rejection, readiness, concurrency, and shutdown;
- no transport-specific domain behavior;
- local `tools show` and `tools run` remain conveniences rather than nonexistent methods.
