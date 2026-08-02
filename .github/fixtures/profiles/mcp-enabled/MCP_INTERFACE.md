# MCP public interface contract

## Status

Selection status: SELECTED

## MCP protocol reference

Runtime, SDK, revision, era boundary, and schema source of truth: RUNTIME.md
Public negotiation and fallback behavior: Both transports select revision `2025-11-25`. If a caller supplies another string revision, initialization succeeds with `2025-11-25` in the response; the caller must decide whether to continue. The configured HTTP endpoint is preferred when readiness and authentication succeed; otherwise a native MCP route is preferred, and the private client may be explicitly invoked over fixed stdio when no native route is available. No active session changes transport.
Public compatibility statement: Within fixture version 1.x, the `text_stats` tool name, required string input `text`, read-only semantics, and existing `bytes`, `lines`, and `words` result fields remain compatible across both transports. Additive MCP result fields must be preserved by callers.

## stdio MCP server variant

Supported: YES
Launch command: bundle exec ruby mcp/server.rb
Lifecycle owner: MCP host

The host launches the trusted bundled command from the skill root, completes initialization before discovery, may send multiple sequential requests, closes stdin when finished, and uses the bounded shutdown escalation documented in `RUNTIME.md`. Stdout contains newline-delimited JSON-RPC protocol messages only. Startup, shutdown, and exception diagnostics use stderr.

## Streamable HTTP MCP server variant

Supported: YES
Start command: bundle exec ruby mcp/http_server.rb
Stop command or shutdown method: kill -TERM "$TEXT_STATS_MCP_HTTP_PID"
Endpoint URL: see RUNTIME.md
Bind address: see RUNTIME.md
Port selection: see RUNTIME.md
Supported protocol eras: see RUNTIME.md
Revision-specific state model: see RUNTIME.md
Authentication: see RUNTIME.md
Health/readiness check: curl --fail --silent --show-error http://127.0.0.1:4570/readyz

The default endpoint is `http://127.0.0.1:4570/mcp`; `RUNTIME.md` owns the startup-selected port and resulting authority. The endpoint is an explicitly started local foreground process and is never created as an implicit fallback. Before every request, including requests reused on one HTTP/1.1 connection, the Rack gate requires the configured loopback Host authority in canonical form and either no Origin or an HTTP Origin whose host and effective port match that authority. Port 80 therefore accepts the equivalent `127.0.0.1` and `127.0.0.1:80` Host forms and Origins with an omitted or explicit `:80`. Invalid Host or present cross-origin requests receive HTTP 403 before authentication or MCP dispatch. Missing or invalid Bearer credentials receive HTTP 401 without exposing the configured token.

Initialization uses one JSON `POST /mcp` request and returns `Mcp-Session-Id`. The client validates the selected revision's required `protocolVersion`, object-valued `capabilities`, and `serverInfo.name`/`serverInfo.version` fields before sending `notifications/initialized` or continuing. All Streamable HTTP POST requests advertise both required response media types with `Accept: application/json, text/event-stream`; this fixture selects JSON response mode and therefore returns JSON for request messages. Subsequent notifications, discovery, and tool calls use independent JSON POST requests carrying that session ID and `MCP-Protocol-Version: 2025-11-25`. `DELETE /mcp` with the same session, version, and authorization headers releases the session. A deletion, connection-close, or classified HTTP cleanup failure is surfaced as an actionable diagnostic and a non-success exit status; it is never silently converted into a successful command. Independent `GET /mcp` event streams and resumability are not part of this public contract.

The SDK bounds request bodies at 65,536 bytes and rejects a seventeenth live session with HTTP 503. Readiness remains available when MCP authentication, protocol validation, tool validation, or session-capacity checks fail. TERM or INT is recorded even if it arrives before the server callback attaches, then stops the foreground listener as soon as the server instance is available; shutdown closes SDK sessions, emits lifecycle diagnostics only to stderr, and releases the port for a later restart. Non-loopback, TLS, reverse-proxy, service-manager, container, and automatic-restart modes are not supported.

## Bundled ad hoc MCP tool client

Supported: YES
Scope: tools only; bounded discovery and invocation helper, not a general MCP host
Command: `bundle exec ruby mcp/client.rb`
Transport used: both
Negotiation and compatibility behavior: Fixed selected revision `2025-11-25`; initialize, verify the server-selected revision, send `notifications/initialized`, then continue; no cross-transport retry or revision fallback
Invocation scope: one tool call or multiple sequential `tools/call` requests; never JSON-RPC batch
Interaction modes: non-interactive JSON arguments only
Task or extension support: NOT SUPPORTED

The helper is not a stable public CLI and does not activate the `packaged-cli` profile. Its stdio command and HTTP endpoint are fixed or explicitly constrained by `RUNTIME.md`; it never accepts an arbitrary server command, caller-selected JSON-RPC ID, Bearer token argument, implicit HTTP-server startup, or unbounded retry.

The repository test clients are private validation code and are not stable public commands.

### Tool inventory, schemas, and caching

`tools/list` returns one page containing the case-sensitive `text_stats` definition with Draft 2020-12 input and output schemas and read-only annotations. The private client validates each listed tool's required name and object-valued `inputSchema`, and requires any result `_meta` to be an object before reporting success. It follows an opaque `nextCursor` until it is absent, retains each raw page under an ordered `pages` record, and bounds pagination to 32 pages by default or 128 at most. No cursor, cache hint, or custom `_meta` value is emitted by this server, but the client preserves those fields and unknown additive fields if a selected server supplies them.

### Lossless paginated tool-list output

The selected inventory is a single raw MCP result page. Validation keeps that result intact, records the request cursor as `null` outside the result when constructing test assertions, and does not flatten, normalize, or invent page-level cache metadata. Future pagination would require a separate contract and tests before being claimed.

### Tool-call results and errors

A successful `tools/call` result preserves `content`, `structuredContent`, `isError`, `_meta`, and unknown additive fields. When present, `_meta` must be an object. The private client validates each content block against the selected revision's discriminator and required fields before reporting success; malformed results use the invalid-result exit code. Missing or invalid `text` arguments return a complete MCP tool result with `isError: true`; they are not transport failures. The private client emits that complete result and exits with the tool-result code. JSON-RPC errors remain distinct from tool results. HTTP 401, 403, 413, and 503 responses remain HTTP authentication, request-policy, or capacity failures and are not reclassified as MCP tool results.

### Multiple calls and application state

One initialized stdio process or HTTP session may serve multiple independent `tools/call` requests. The operation is stateless: every result depends only on the current request's `text` argument. Process, connection, and session reuse do not create hidden domain state.

### Selected modern multi-round-trip requests

Modern input-required results and multi-round-trip retry behavior are not supported or advertised by the selected revision contract. The caller never fabricates input responses or retries a call as though that feature were negotiated.

### Selected initialization-era server-to-client requests

The fixture advertises no elicitation, sampling, roots, or other server-to-client request capability. Private test clients declare an empty capability object and therefore need no server-to-client request handlers.

### Cancellation, tasks, and extensions

The sole operation is synchronous and bounded. A stdio timeout closes stdin and applies bounded child-process escalation. In the pinned SDK 1.0.0 JSON-response HTTP transport, a caller timeout or socket close abandons the response path but does not itself signal MCP cancellation; the synchronous operation may continue in the serving request thread until bounded completion. It is not detached into a task or independent background operation, and the session remains reusable before explicit DELETE releases it. Protocol-level MCP cancellation is a separate mechanism and is not claimed by the socket-disconnect contract. Tasks and optional extensions are not advertised.

### Ownership and workspace policy

The stdio MCP host owns its trusted child process. The bundled client owns its fixed child only for the duration of one command and applies bounded shutdown. The HTTP launcher owns one explicitly started loopback process and supplies one local Bearer identity; every session request is reauthenticated. The tool accepts text directly, has no filesystem workspace semantic, exposes no arbitrary command or caller-selected request ID, and performs no network access beyond the selected local MCP transport.

## Semantic-equivalence and test requirements

Tests exercise exact-revision initialization, required initialization fields before `notifications/initialized`, the required `notifications/initialized` transition before discovery or tool calls, both required Streamable HTTP POST Accept media types, server-selected revision negotiation after another string revision, malformed revision rejection, tools-only capabilities, raw tool inventory, deterministic success, missing-input tool error, unknown-method JSON-RPC error, sequential calls after errors, stdio stdout/stderr separation, bounded stdio shutdown, authenticated HTTP initialization and session deletion, request-size and session-count limits, readiness isolation, per-request Host/Origin/authentication checks on a reused keep-alive connection, canonical port-80 Host and Origin forms, pending shutdown delivery before server attachment, graceful HTTP shutdown and restart, prompt configuration failures, and equal structured tool results through actual stdio and Streamable HTTP adapters. Bundled-client tests additionally execute `server-info`, lossless paginated inventory, local `tools show`, one and sequential `tools/call` operations, required content-block field validation, stdio/HTTP equivalence, token-redacted authentication failures, loopback endpoint rejection, transport failures, bounded timeout, and codec preservation of unknown additive fields without sending `tools/show` or JSON-RPC batch methods.

## Decision rationale

Rationale: The existing HTTP endpoint is preferred when several local clients need one bounded service; stdio remains the trusted no-listener fallback. Both adapters use one server factory and one domain operation. Loopback binding, request-scoped canonical Host and Origin validation, Bearer authentication, bounded sessions and bodies, explicit listener startup, and foreground lifecycle keep the HTTP expansion proportional without claiming a remote deployment or public client.
