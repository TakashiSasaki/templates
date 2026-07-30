# Optional MCP adapters

Delete this directory when the concrete skill does not expose MCP.

When MCP is supported, this directory may contain:

- a shared MCP server factory or operation registry;
- a stdio server entry point;
- a Streamable HTTP server entry point;
- a bounded ad hoc MCP tool client used by the skill or contract tests;
- MCP-specific schemas and adapter tests.

The implementation language, SDK, exact protocol revisions, compatibility policy, era boundary, and commands are selected only in `RUNTIME.md`.

## Standard terminology

MCP defines stdio and Streamable HTTP as standard transports. A server listening on a TCP port should normally be described as a **Streamable HTTP MCP server**, not a raw TCP MCP transport.

A command that only discovers and invokes tools is an **ad hoc MCP tool client**. It is not automatically a native agent tool, complete MCP host, or general-purpose MCP client.

Use revision-neutral terms such as selected modern mode and selected initialization-era mode in this document. Do not maintain a separate date-based revision boundary here.

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

MCP server adapters call the same application/domain implementation used by the CLI. The bundled tool client must traverse an MCP adapter rather than call the application layer directly.

## stdio implementation checklist

- launch only a trusted bundled server command;
- reserve stdout for protocol messages;
- send diagnostics to stderr;
- do not daemonize or open a listening socket;
- perform the discovery, initialization, or negotiation behavior required by the selected revision;
- implement only advertised server-to-client capabilities;
- use revision-appropriate cancellation;
- close stdin or the connection according to the SDK contract;
- wait for process exit and use bounded shutdown escalation;
- avoid hidden application-state assumptions across calls.

## Streamable HTTP implementation checklist

General requirements:

- bind to `127.0.0.1` or `::1` by default for local-only deployments;
- expose a documented endpoint, normally `/mcp`;
- validate Host and protect against DNS rebinding on every HTTP request;
- validate Origin independently on every HTTP request before dispatch;
- do not reuse an earlier request's Origin decision when HTTP/1.1 keep-alive, HTTP/2, or later protocols reuse or multiplex a connection;
- return HTTP 403 for every request with a present disallowed Origin;
- document absent-Origin behavior;
- perform authentication, authorization, size-limit, and protocol-header checks per request;
- define supported protocol eras, concurrency, readiness, cancellation, and shutdown;
- require a separate security design for non-loopback access.

When the selected modern revision requires the modern Streamable HTTP contract:

- use one POST for each JSON-RPC request;
- accept both JSON and SSE response media types;
- send required protocol-version and method/name request headers;
- keep request headers consistent with JSON body metadata;
- support request-scoped SSE cancellation;
- avoid initialization-era session IDs, independent GET/DELETE endpoints, or resumability in modern mode;
- validate tool-defined HTTP-header declarations;
- exclude invalid HTTP tool definitions from the usable inventory;
- move designated arguments into encoded transport headers;
- test any initialization-era compatibility separately.

## Bundled tool-client behavior

Recommended local operations:

| Local operation | MCP behavior |
|---|---|
| `server-info` | Report discovery or negotiated server information according to the selected revision |
| `tools list` | `tools/list` with ordered raw-page lossless output and optional flattened presentation |
| `tools show TOOL` | Local filtering over the derived flattened inventory; not an MCP method |
| `tools call TOOL` | One `tools/call` request |
| `tools run` | Several independent `tools/call` requests; not an MCP or JSON-RPC batch |

The client must:

- preserve each raw `tools/list` page in order, including page-specific cursors, cache fields, `_meta`, and unknown extensions;
- keep a flattened inventory separate and label aggregate metadata as derived;
- preserve complete tool-call results, including `resultType`, standard fields, `_meta`, and unknown extensions;
- keep tool names case-sensitive and cursors opaque;
- support the schema dialects selected in `RUNTIME.md`;
- accept any permitted JSON type in `structuredContent`;
- distinguish transport, protocol, invalid-result, input-required, tool-error, and success outcomes;
- generate request IDs internally;
- avoid arbitrary server shell commands;
- capability-gate tasks, elicitation, sampling, roots, and other features;
- distinguish MCP roots from skill-specific workspace configuration.

For paginated lists, store the cursor used to request each page as client metadata outside the raw `mcpResult`. Do not merge page-level `ttlMs`, `cacheScope`, `_meta`, or unknown fields into one alleged lossless result. A single-page response uses the same page-record representation with one element.

## Additional input

Selected modern multi-round-trip behavior:

- preserve an `input_required` result in non-interactive mode when permitted by the selected revision;
- in interactive or response-file mode, retry with `inputResponses` and echoed `requestState`;
- use a new JSON-RPC request ID for every retry.

Selected initialization-era behavior:

- advertise elicitation or other client capabilities only when implemented;
- answer form elicitation with `accept`, `decline`, or `cancel`;
- document automatic decline or cancellation in non-interactive mode;
- wait for the original request's final result;
- do not synthesize a modern input-required result.

## Test requirements

Test every claimed revision, transport, and optional feature. At minimum verify:

- negotiation and compatibility fallback;
- equivalent operations under the same identity, authorization, configuration, and workspace policy;
- ordered raw-page preservation and flattened inventory derivation;
- page-specific cursors, cache fields, `_meta`, and unknown extensions;
- selected schema dialects and `structuredContent` types;
- lossless tool-call result and unknown-field preservation;
- selected modern multi-round-trip and initialization-era elicitation behavior;
- cancellation, maximum timeout, and child-process cleanup;
- modern HTTP headers, JSON/SSE responses, and tool-defined HTTP headers when required by the selected revision;
- loopback binding and per-request Host/Origin validation;
- at least two requests on one reused or multiplexed HTTP connection with different Origin values;
- HTTP 403 for every present disallowed Origin and documented absent-Origin handling;
- readiness, concurrency, graceful shutdown, restart, and stale-process behavior;
- no transport-specific domain behavior;
- local `tools show` and `tools run` remain conveniences rather than nonexistent methods.
