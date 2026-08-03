# MCP public interface contract

## Status

Selection status: SELECTED

## MCP protocol reference

Runtime, SDK, revision, era boundary, and schema source of truth: RUNTIME.md
Public negotiation and fallback behavior: The systemd-managed Streamable HTTP server selects revision `2025-11-25`. Another string revision receives `2025-11-25` in the initialization result and the caller decides whether to continue. Missing or non-string revisions are malformed. No stdio, legacy-revision, or automatic lifecycle fallback occurs.
Public compatibility statement: Within fixture version 1.x, the `text_stats` tool name, required string input `text`, read-only semantics, and integer `bytes`, `lines`, and `words` result fields remain compatible. Additive fields must be preserved by callers.

## stdio MCP server variant

Supported: NO
Launch command: NOT SUPPORTED
Lifecycle owner: NOT SUPPORTED

No stdio adapter is retained by this deployment fixture.

## Streamable HTTP MCP server variant

Supported: YES
Start command: sudo systemctl start text-stats-mcp.service
Stop command or shutdown method: sudo systemctl stop text-stats-mcp.service
Endpoint URL: http://127.0.0.1:4572/mcp
Bind address: 127.0.0.1
Port selection: fixed render-time integer, default 4572
Supported protocol eras: initialization-era revision 2025-11-25
Revision-specific state model: SDK-issued process-local sessions with 300-second idle expiry and explicit DELETE cleanup
Authentication: exact Bearer token from the systemd credential named `text-stats-mcp-token`, checked on every `/mcp` request
Health/readiness check: curl --fail --silent --show-error http://127.0.0.1:4572/readyz

The unit reaches active state only after `mcp/http_server.rb` creates the listener and sends `READY=1` through `NOTIFY_SOCKET`. Every HTTP request validates the exact loopback Host authority and either an absent Origin or the exact same-origin HTTP authority before authentication or dispatch. Invalid Host or Origin receives HTTP 403. Missing or invalid Bearer credentials receive HTTP 401 without exposing credential material.

Initialization uses JSON `POST /mcp`, returns `Mcp-Session-Id`, and selects revision `2025-11-25`. The initialized session uses independent POST requests carrying that session ID and `MCP-Protocol-Version: 2025-11-25`. `DELETE /mcp` releases the session. The transport selects JSON response mode; independent event streams and resumability are not supported.

The SDK limits request bodies to 65,536 bytes and live sessions to 16. Readiness and liveness remain minimal, unauthenticated, loopback-only responses and do not disclose systemd unit, credential, PID, cgroup, or session details. The agent never invokes `systemctl` or the renderer through MCP.

## Bundled ad hoc MCP tool client

Supported: NO
Scope: NOT SUPPORTED
Command: NOT SUPPORTED
Transport used: NOT SUPPORTED
Negotiation and compatibility behavior: NOT SUPPORTED
Invocation scope: NOT SUPPORTED
Interaction modes: NOT SUPPORTED
Task or extension support: NOT SUPPORTED

The smoke client under `tests/` is private validation code and is not a stable command.

### Tool inventory, schemas, and caching

`tools/list` returns one page containing the case-sensitive `text_stats` definition with Draft 2020-12 input and output schemas and read-only annotations. No cursor, custom cache hint, or application `_meta` value is emitted.

### Lossless paginated tool-list output

The selected inventory is one raw result page. No pagination helper or flattened public presentation is included. A future paginated client would require a separate contract.

### Tool-call results and errors

Successful calls preserve the complete MCP result including `content`, `structuredContent`, `isError`, `_meta`, and unknown additive fields. Invalid arguments produce an MCP tool result with `isError: true`; they are distinct from HTTP authentication, policy, capacity, transport, and JSON-RPC failures.

### Multiple calls and application state

A live session may perform multiple independent tool calls. The operation is stateless and depends only on the current `text` argument. systemd restart discards all process-local MCP sessions and clients must initialize again.

### Selected modern multi-round-trip requests

Modern input-required results, retries, and task workflows are not supported or advertised.

### Selected initialization-era server-to-client requests

The server advertises no elicitation, sampling, roots, or other server-to-client request capability.

### Cancellation, tasks, and extensions

The operation is synchronous and bounded. Client disconnect does not create a task or persistent work. systemd shutdown sends TERM to the process and owns bounded control-group escalation; this deployment behavior is not an MCP cancellation method.

### Ownership and workspace policy

systemd owns the service process and cgroup. The fixed unit owns lifecycle and credential injection; the MCP adapter owns request framing, Host, Origin, authentication, session, and protocol behavior; the shared domain module owns only deterministic text analysis. No arbitrary command, path, workspace, lifecycle, or deployment parameter is accepted through MCP.

## Semantic-equivalence and test requirements

Tests execute the same HTTP adapter directly and under the rendered systemd unit, verify `READY=1`, initialization, the real tool inventory, sequential authenticated tool invocations, deterministic structured results, Host and Origin rejection, configuration failure before listener creation, explicit restart, automatic on-failure restart, bounded stop, and credential redaction.

## Decision rationale

Rationale: the fixture selects one authenticated loopback Streamable HTTP transport because the intended contract is OS service-manager ownership, not transport breadth. Omitting stdio, a bundled public client, remote exposure, proxy trust, and TLS keeps the new trust boundary limited to systemd lifecycle, readiness, credentials, restart, and shutdown.
