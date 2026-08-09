# MCP public interface contract

Retain and complete this file only when `mcp-enabled` is selected. It defines caller-visible MCP behavior. Runtime, SDK, the exact core protocol revision, transport startup commands, and distribution selections remain authoritative in `RUNTIME.md`.

This unpublished template uses the MCP `2026-07-28` **Modern** protocol as its only core baseline. Earlier initialization-based revisions are not a compatibility target.

## Status

```text
Selection status: UNSELECTED
```

Change the status to `SELECTED` only after all supported variants are concrete, every unsupported variant is explicitly marked `NO`, and the public behavior agrees with `RUNTIME.md`.

## MCP protocol reference

```text
Runtime, SDK, revision, era boundary, and schema source of truth: RUNTIME.md
Public negotiation and fallback behavior: Modern per-request metadata; no automatic Legacy initialization fallback
Public compatibility statement: MCP 2026-07-28 Modern only; MCP 2025-11-25 and earlier are NOT SUPPORTED
```

Do not duplicate SDK version selections here. A selected contract must state that callers use Modern per-request metadata, that the server implements `server/discover`, that unsupported revisions produce `UnsupportedProtocolVersionError`, and that no automatic fallback to the Legacy initialization handshake occurs.

Every Modern request carries the selected protocol version and client capabilities in request `_meta`. Identity metadata is handled according to the selected revision and SDK. Optional MCP extensions are capability-gated and do not change core behavior unless both sides advertise the extension.

## stdio MCP server variant

```text
Supported: UNSELECTED
Launch command: TODO or NOT SUPPORTED
Lifecycle owner: MCP host / bundled tool client / other: TODO
```

When supported:

- stdout is protocol-only and diagnostics use stderr;
- the launcher command is exact, trusted, and bounded;
- the Host or bundled client owns child-process shutdown and escalation;
- the caller sends Modern requests using the revision selected in `RUNTIME.md`;
- the server implements `server/discover` and rejects Legacy `initialize` openings rather than silently switching eras;
- cancellation and process-exit behavior are documented in `RUNTIME.md`.

## Streamable HTTP MCP server variant

Supported: UNSELECTED
Endpoint URL: TODO or see RUNTIME.md
Authentication: TODO or NOT SUPPORTED

When supported, the endpoint uses the exact path, bind address, port policy, authentication, and deployment authority recorded in `RUNTIME.md`. Host and Origin checks apply to **every HTTP request**, including requests that reuse an existing keep-alive or multiplexed connection. A previous request must not authorize a later request on the same connection. Every present disallowed Origin returns HTTP 403.

For MCP `2026-07-28`, callers send each JSON-RPC message in a new POST to the MCP endpoint. Requests declare the selected protocol revision in both `MCP-Protocol-Version` and request `_meta`, and the two values agree. Requests include `Mcp-Method`; `tools/call`, `resources/read`, and `prompts/get` also include `Mcp-Name`. Header values use the encoding defined by the selected specification and SDK.

Clients advertise `Accept: application/json, text/event-stream`. A response may be ordinary JSON or request-scoped SSE. Closing a request SSE stream cancels that request; the server does not continue sending messages for the cancelled request.

The Modern baseline does not use protocol-level `Mcp-Session-Id`, the old standalone GET stream, session DELETE, or `Last-Event-ID` resumability. Long-lived change notifications, when supported, use `subscriptions/listen`. Automatic fallback to an initialization-era protocol on the same endpoint is not supported.

When this Skill acts as an HTTP MCP client, tool definitions carrying `x-mcp-header` are validated before their declared headers are emitted as `Mcp-Param-*`. Server-only implementations that never issue HTTP MCP calls may mark that client behavior not applicable in `RUNTIME.md`.

## Bundled ad hoc MCP tool client

Supported: UNSELECTED
Stable command: TODO or NOT SUPPORTED
Supported transports: TODO or NOT SUPPORTED

When supported, the bundled client is a bounded MCP client, not a generic JSON-RPC console or shell escape. It pins or otherwise requires the Modern `2026-07-28` baseline and does not retry a failed opening with Legacy `initialize`.

### Discovery and inventory

Server discovery: TODO or NOT SUPPORTED
Tool list: TODO or NOT SUPPORTED
Tool show: TODO or NOT SUPPORTED

If the client exposes server discovery, it uses `server/discover`. `tools/list` pagination preserves every raw page record in lossless modes. Any flattened tool inventory is an explicitly derived presentation, not a substitute for lossless protocol output.

### Tool invocation

Single tool call: TODO or NOT SUPPORTED
Sequential tool run: TODO or NOT SUPPORTED

Sequential runs are repeated `tools/call` operations, not JSON-RPC batch requests. The client does not expose caller-selected JSON-RPC request IDs. Complete tool-call results, including structured content, textual content, errors, and applicable result metadata, remain available in lossless output.

### Modern server-request replacement and notifications

Modern MRTR behavior: TODO or NOT SUPPORTED
Subscriptions: TODO or NOT SUPPORTED

The Modern core does not use initialization-era server-to-client requests. If the selected operation requires a Modern replacement such as MRTR, its support and approval behavior are explicit. Long-lived notifications use selected Modern subscription mechanisms rather than the removed general GET stream.

### Cancellation, tasks, and extensions

Cancellation and timeout behavior: TODO
Task support: TODO or NOT SUPPORTED
Optional extension behavior: TODO or NOT SUPPORTED

Optional extensions remain separately capability-gated and versioned. Core MCP success must not depend on an extension unless the public operation explicitly requires that extension and the Host capability requirement is documented.

## Result semantics

Every successful operation preserves the complete MCP result defined by the selected SDK/specification. Text-only presentation is not allowed to discard `structuredContent`, resource content, tool metadata, cache hints, or extension-defined result data that the caller contract promises to expose.

When a tool defines an output schema, returned `structuredContent` conforms to it. Text content may provide a human-readable or compatibility representation, but it does not replace the structured result.

Errors distinguish protocol/transport failure from a valid negative domain result. Unsupported protocol revisions are surfaced as `UnsupportedProtocolVersionError`; they are not converted into Legacy negotiation attempts.

## Cross-interface equivalence

When the same domain operation is exposed through MCP and another maintained interface, inputs, results, side effects, authorization, confirmation, workspace policy, and failure meaning are equivalent unless a documented transport limitation prevents parity. Presentation differences do not change domain semantics.

## Required tests

A concrete MCP Skill must test every claimed transport and public client path. For the Modern baseline, tests include at least:

- successful `2026-07-28` discovery/ordinary calls;
- rejection of an unsupported revision;
- rejection of a Legacy initialization opening rather than fallback;
- every claimed stdio or Streamable HTTP transport;
- Streamable HTTP per-request Host/Origin enforcement when HTTP is supported;
- `MCP-Protocol-Version` / request `_meta` consistency when HTTP is supported;
- required `Mcp-Method` / conditional `Mcp-Name` behavior when HTTP is supported;
- JSON/SSE response and cancellation behavior for claimed HTTP capabilities;
- complete result/structured-content preservation;
- every selected optional extension and its core-only fallback behavior.

## Decision rationale

TODO
