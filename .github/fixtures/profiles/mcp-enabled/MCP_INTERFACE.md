# MCP public interface contract

## Status

Selection status: SELECTED

## MCP protocol reference

Runtime, SDK, revision, era boundary, and schema source of truth: RUNTIME.md
Public negotiation and fallback behavior: Both transports select revision `2025-11-25`. If a caller supplies another string revision, initialization succeeds with `2025-11-25` in the response; the caller must decide whether to continue. The configured HTTP endpoint is preferred when readiness and authentication succeed; otherwise a native MCP route is preferred, and the private client may be explicitly invoked over fixed stdio when no native route is available. No active session changes transport, and no agent request starts or controls the HTTP process.
Public compatibility statement: Within fixture version 1.x, the `text_stats` tool name, required string input `text`, read-only semantics, and existing `bytes`, `lines`, and `words` result fields remain compatible across both transports. Additive MCP result fields must be preserved by callers. Selecting direct foreground or managed local HTTP lifecycle does not change the MCP endpoint contract.

## stdio MCP server variant

Supported: YES
Launch command: bundle exec ruby mcp/server.rb
Lifecycle owner: MCP host

The host launches the trusted bundled command from the skill root, completes initialization before discovery, may send multiple sequential requests, closes stdin when finished, and uses the bounded shutdown escalation documented in `RUNTIME.md`. Stdout contains newline-delimited JSON-RPC protocol messages only. Startup, shutdown, and exception diagnostics use stderr.

## Streamable HTTP MCP server variant

Supported: YES
Start command: bundle exec ruby mcp/http_server.rb
Stop command or shutdown method: kill -TERM "$TEXT_STATS_MCP_HTTP_PID"
Managed start command: TEXT_STATS_MCP_HTTP_TOKEN_FILE=/path/to/mode-0600-token bundle exec ruby mcp/service_manager.rb start
Managed stop command: bundle exec ruby mcp/service_manager.rb stop
Managed restart command: bundle exec ruby mcp/service_manager.rb restart
Endpoint URL: see RUNTIME.md
Bind address: see RUNTIME.md
Port selection: see RUNTIME.md
Supported protocol eras: see RUNTIME.md
Revision-specific state model: see RUNTIME.md
Authentication: see RUNTIME.md
Health/readiness check: curl --fail --silent --show-error http://127.0.0.1:4570/readyz
Managed readiness check: bundle exec ruby mcp/service_manager.rb ready
Managed liveness check: bundle exec ruby mcp/service_manager.rb live

The default endpoint is `http://127.0.0.1:4570/mcp`; `RUNTIME.md` owns the startup-selected port and resulting authority. The endpoint is created only by explicit operator action. Foreground mode accepts an exact token through `TEXT_STATS_MCP_HTTP_TOKEN` or a permission-checked file through `TEXT_STATS_MCP_HTTP_TOKEN_FILE`. Managed mode requires the file source so the secret value is absent from argv and controller output. Before every request, including readiness, liveness, and requests reused on one HTTP/1.1 connection, the Rack gate requires the configured loopback Host authority in canonical form and either no Origin or an HTTP Origin whose host and effective port match that authority. Port 80 accepts the equivalent `127.0.0.1` and `127.0.0.1:80` Host forms and Origins with an omitted or explicit `:80`. Invalid Host or present cross-origin requests receive HTTP 403 before authentication or MCP dispatch. Missing or invalid Bearer credentials receive HTTP 401 without exposing the configured token.

Initialization uses one JSON `POST /mcp` request and returns `Mcp-Session-Id`. The client validates the selected revision's required `protocolVersion`, object-valued `capabilities`, known capability objects and boolean `tools`/`resources`/`prompts` flags, and `serverInfo.name`/`serverInfo.version` fields before sending `notifications/initialized` or continuing. All Streamable HTTP POST requests advertise both required response media types with `Accept: application/json, text/event-stream`; this fixture selects JSON response mode and therefore returns JSON for request messages. The bundled client requires each JSON response to declare the `application/json` media type before parsing and accepts `notifications/initialized` only when HTTP status is `202`. Subsequent notifications, discovery, and tool calls use independent JSON POST requests carrying the session ID and `MCP-Protocol-Version: 2025-11-25`. `DELETE /mcp` with the same session, version, and authorization headers releases the session. Independent `GET /mcp` event streams and resumability are not part of this contract.

The SDK bounds request bodies at 65,536 bytes and rejects a seventeenth live session with HTTP 503. Readiness remains available when MCP authentication, protocol validation, tool validation, or session-capacity checks fail. Liveness is a separate minimal endpoint. TERM or INT is recorded even if it arrives before the server callback attaches, then stops the foreground listener as soon as the server instance is available; shutdown closes SDK sessions and releases the port.

### Managed local lifecycle

The optional controller `mcp/service_manager.rb` is a private operator surface, not an MCP method, bundled client operation, or `packaged-cli` interface. It starts only the fixed `mcp/http_server.rb` entry point in one local process group. Startup validates a service-user-owned token file with no group or other access, rejects a live recorded identity, removes only a safely parsed stale record, creates owner-only runtime files, atomically publishes a mode-0600 record containing PID and Linux process start ticks, and requires readiness within a fixed deadline. Stop and restart identity-verify that record before signaling; TERM is followed by KILL only after bounded grace periods. A missing process, zombie, or start-tick mismatch is stale and is never signaled. Unsafe or malformed token, PID, and log paths fail closed.

This variant does not provide OS service installation, privilege separation, multiple workers, automatic restart, socket activation, zero-downtime upgrade, log rotation, non-loopback exposure, TLS, reverse proxy, container, orchestrator, persistence, or remote production deployment. Those remain separate trust boundaries requiring separate fixtures.

## Bundled ad hoc MCP tool client

Supported: YES
Scope: tools only; bounded discovery and invocation helper, not a general MCP host
Command: `bundle exec ruby mcp/client.rb`
Transport used: both
Negotiation and compatibility behavior: Fixed selected revision `2025-11-25`; initialize, verify the server-selected revision, validate known capability object shapes and boolean flags, send `notifications/initialized`, require its HTTP response status to be `202`, then continue; no cross-transport retry or revision fallback
Invocation scope: one tool call or multiple sequential `tools/call` requests, bounded to at most 32 sequential calls; `tools run` requires at least one `--call` before transport startup and rejects trailing operands; never JSON-RPC batch
Interaction modes: non-interactive JSON arguments only; terminal `--arguments-stdin` is rejected and non-EOF stdin reads are bounded by the configured `--timeout` before transport startup
Task or extension support: NOT SUPPORTED

The helper is not a stable public CLI and does not activate the `packaged-cli` profile. Its stdio command and HTTP endpoint are fixed or explicitly constrained by `RUNTIME.md`; it never accepts an arbitrary server command, caller-selected JSON-RPC ID, Bearer token argument, lifecycle action, implicit HTTP-server startup, or unbounded retry.

### Tool inventory, schemas, and caching

`tools/list` returns one page containing the case-sensitive `text_stats` definition with Draft 2020-12 input and output schemas and read-only annotations. The private client validates each listed tool's required name, object-valued `inputSchema` whose `type` is `object`, object-valued `outputSchema` when present, object-valued `annotations` when present with typed known fields, and object-valued per-tool `_meta` when present. It follows opaque `nextCursor` values with bounded pagination and retains each raw page plus unknown additive fields.

### Lossless paginated tool-list output

The selected inventory is one raw MCP result page. Validation keeps it intact, records the request cursor outside the result, and does not flatten, normalize, or invent page-level cache metadata. A flattened `tools show` view is derived and never replaces lossless output.

### Tool-call results and errors

A successful `tools/call` result preserves `content`, `structuredContent`, `isError`, `_meta`, and unknown additive fields. The private client validates required content discriminators and typed known optional fields before reporting success. Missing or invalid `text` arguments return a complete MCP tool result with `isError: true`; JSON-RPC errors, HTTP authentication, request-policy, capacity, invalid-result, timeout, and transport failures remain distinct.

### Multiple calls and application state

One initialized stdio process or HTTP session may serve multiple independent `tools/call` requests. The operation is stateless: every result depends only on the current request's `text` argument. Process, connection, session, and lifecycle-mode reuse do not create hidden domain state.

### Selected modern multi-round-trip requests

Modern input-required results and multi-round-trip retry behavior are not supported or advertised by the selected revision contract. The caller never fabricates input responses or retries a call as though that feature were negotiated.

### Selected initialization-era server-to-client requests

The fixture advertises no elicitation, sampling, roots, or other server-to-client request capability. Private test clients declare an empty capability object and therefore need no server-to-client request handlers.

### Cancellation, tasks, and extensions

The sole operation is synchronous and bounded. A stdio timeout closes stdin and applies bounded child-process escalation. In the pinned SDK 1.0.0 JSON-response HTTP transport, a caller timeout or socket close abandons the response path but does not itself signal MCP cancellation; bounded work may complete before the session is explicitly deleted. Protocol-level MCP cancellation is separate and is not claimed by this disconnect behavior. Tasks and optional extensions are not advertised.

### Ownership and workspace policy

The stdio MCP host owns its trusted child process. The bundled client owns its fixed stdio child only for one command. A manual HTTP launcher or the private lifecycle controller owns the explicitly selected loopback process; neither is callable through MCP. Every HTTP session request is reauthenticated. The tool has no filesystem workspace semantic and performs no network access beyond the selected local MCP transport.

## Semantic-equivalence and test requirements

Tests exercise exact-revision initialization, required initialization fields, `notifications/initialized`, response media types, revision selection, malformed revision rejection, tools-only capabilities, schema validation, deterministic success and tool errors, sequential calls, stdout/stderr separation, bounded stdio shutdown, authenticated HTTP initialization and deletion, request size and session capacity, readiness and liveness, per-request Host/Origin/authentication on reused connections, default-port authority forms, pending shutdown delivery, graceful HTTP shutdown and restart, and equal tool results through actual transports. Managed lifecycle tests execute real start, ready, live, restart, and stop; reject insecure and symlinked secrets before process creation; replace only stale safe records; reject symlinked PID records; verify token redaction; and prove TERM-to-KILL escalation for a resistant process group.

## Decision rationale

Rationale: The existing HTTP endpoint is preferred when several local clients need one bounded service; stdio remains the trusted no-listener fallback. Both adapters use one server factory and one domain operation. The managed variant adds explicit local process ownership and an external-secret boundary without changing MCP semantics or claiming remote deployment, reverse proxy, TLS, container, persistence, or automatic restart.
