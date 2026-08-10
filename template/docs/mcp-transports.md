# MCP transport guidance

This guide applies only when the concrete Skill selects `mcp-enabled`. The unpublished template baseline is MCP core revision `2026-07-28`, Modern era only. `RUNTIME.md` owns the exact SDK/library, commands, transport selections, bind/port choices, and deployment lifecycle; `MCP_INTERFACE.md` owns caller-visible protocol behavior.

## Core baseline

A selected implementation must use the Modern per-request metadata model. There is no MCP initialization session in the template baseline.

- Servers implement `server/discover`.
- Every request declares the protocol revision in request `_meta`.
- Clients send the client capabilities required by the selected revision on every request.
- Unsupported revisions receive `UnsupportedProtocolVersionError` and the server's supported revisions.
- Earlier `initialize` / `notifications/initialized` behavior is not supported.
- Optional extensions are negotiated through `capabilities.extensions` and do not silently alter core behavior.

Use an official SDK path that explicitly supports `2026-07-28`. Some SDKs still default to the 2025-era lifecycle unless Modern support is selected explicitly, so a dependency upgrade by itself is not evidence of conformance.

## stdio

Use stdio for local host-launched servers when opening a listener is unnecessary.

Required invariants:

- stdin and stdout carry MCP protocol traffic only;
- diagnostics go to stderr;
- the host or bounded bundled client owns the child process lifetime;
- Modern discovery and per-request metadata are used from the first exchange;
- Legacy openings are rejected rather than accepted through an initialization handshake;
- process shutdown is bounded and deterministic;
- operation semantics match every other maintained adapter under the same identity, authorization, configuration, and workspace policy.

For the official TypeScript SDK v2, `serveStdio(factory, { legacy: 'reject' })` is the intended Modern-only serving shape. Do not replace it with a hand-constructed legacy `StdioServerTransport` path and assume that installing v2 changed the wire protocol.

## Streamable HTTP

A Modern Streamable HTTP server exposes one MCP endpoint that accepts POST. Each JSON-RPC client message is sent in a new POST. Protocol-level HTTP sessions are not part of `2026-07-28`.

### Request requirements

For each applicable POST:

- require `MCP-Protocol-Version` and require it to match the request `_meta` protocol version;
- require `Mcp-Method` for requests;
- require `Mcp-Name` for `tools/call`, `resources/read`, and `prompts/get`;
- require clients to advertise both `application/json` and `text/event-stream` in `Accept`;
- validate and safely decode/encode the standard header values;
- when a tool input schema uses `x-mcp-header`, a conforming Streamable HTTP client validates the annotation and mirrors the selected primitive argument into `Mcp-Param-*`.

The server returns either one JSON result or an SSE stream scoped to that request. A request-scoped SSE stream may carry related notifications before the final response, but it is not a general server-to-client request channel.

### Cancellation

Closing the request-scoped SSE response stream cancels that request. Stop work as soon as practical and send no later messages for the cancelled request. Do not send a Legacy `notifications/cancelled` POST as the Modern HTTP cancellation mechanism.

### Removed session behavior

Do not implement these as part of the Modern MCP endpoint:

- `Mcp-Session-Id`;
- a standalone MCP GET stream;
- DELETE for MCP session termination;
- resumable SSE via `Last-Event-ID`.

Application state may still exist, but it must be represented as application-owned resources, handles, storage, request state, or explicit configuration rather than hidden protocol-session state.

### Long-lived change notifications

When the Skill exposes change notifications, use `subscriptions/listen`. Its SSE response is the long-lived notification stream selected by the client. Do not recreate the removed general GET stream.

## HTTP security boundary

Validate security decisions per HTTP request, never once per TCP/TLS connection.

- Validate every present `Origin`; reject an invalid present Origin with HTTP 403.
- Bind local-only servers to loopback by default.
- Validate Host/authority consistently and defend against DNS rebinding.
- Apply authentication, authorization, request-size limits, protocol-header checks, and operation policy before dispatch.
- A valid first request on a keep-alive or multiplexed connection must not authorize a later request with different headers.
- Non-loopback exposure requires an explicit authentication and transport-security design.

Readiness and liveness endpoints are operational interfaces, not proof that MCP discovery or tool invocation succeeds. Keep their authorization and routing contracts explicit.

## Modern multi-round-trip requests

The Modern core does not open arbitrary server-to-client JSON-RPC request channels for elicitation, sampling, or roots. When an operation needs additional client input, use the `InputRequiredResult` / `resultType: "input_required"` MRTR model defined by the selected core revision and retry the original method with the matching input responses.

Every retry uses a new JSON-RPC request ID. The request state echoed by the protocol is not a license to keep undocumented hidden session state.

## Deprecated surfaces

The initial template does not advertise deprecated Roots, Sampling, Logging, or the older HTTP+SSE transport. Do not add them merely because an SDK still exposes compatibility APIs. If a future template revision intentionally adopts a deprecated surface for a concrete interoperability requirement, that change must update the normative requirement matrix, contract, validator, and evidence together.

## Extensions

Core protocol revision and extension revision are separate concerns. An extension is advertised only when its own contract is retained and its capability is explicitly selected. If the peer does not advertise that extension, fall back to meaningful core behavior or reject the operation as specified by that extension; never silently assume support.

MCP Apps is handled by its own contract when selected. A standalone browser-facing verification interface remains governed by `WEB_INTERFACE.md` and is not implied by MCP Apps support.

## Required evidence

For every selected MCP transport, test at least:

- successful Modern discovery and ordinary request execution;
- rejection of an unsupported protocol revision;
- required request metadata;
- result-type preservation;
- cancellation and timeout behavior;
- semantic equivalence with other maintained adapters;
- negative tests for the transport-specific security boundary.

Streamable HTTP evidence additionally covers required headers, header/body mismatches, Host and per-request Origin checks, connection reuse, JSON and SSE responses, and confirmation that session identifiers, GET/DELETE MCP lifecycle operations, and resumability are absent.
