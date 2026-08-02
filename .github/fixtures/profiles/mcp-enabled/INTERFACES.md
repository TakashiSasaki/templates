# Public interface selection contract

## Status

Selection status: SELECTED

## Execution policy

Preferred agent interface: configured Streamable HTTP MCP endpoint when readiness succeeds and the caller has the required Bearer token
Fallback 1: native MCP tool registered with the trusted stdio command from `RUNTIME.md`
Fallback 2: NONE

The agent checks an existing HTTP endpoint but never starts another listener implicitly. When HTTP is unavailable, unauthorized, or fails readiness, the host may explicitly launch the bundled stdio command. This fixture exposes no public ad hoc MCP client and no non-MCP operation fallback.

## Contract index

| Selected profile or interface | Authoritative contract |
|---|---|
| MCP caller behavior | `MCP_INTERFACE.md` |
| Runtime, SDK, revision, command, transport, security, and lifecycle selection | `RUNTIME.md` |

## Cross-interface invariants

Both maintained routes use `mcp/server_factory.rb`, the same `TextStatsTool`, and the same `src/text_stats.rb` operation. Test clients traverse the actual stdio and Streamable HTTP transports, initialize the same selected revision, discover the same tool definition, and prove equal structured results for the same input. Neither adapter calls a transport-specific domain implementation.

## Availability and failure behavior

Unavailable preferred interface behavior: Report the HTTP readiness, authentication, request-policy, or transport failure, then use the trusted stdio route only when the host can explicitly launch it.
Fallback activation conditions: The configured HTTP endpoint is absent, fails `GET /readyz`, rejects the caller, or cannot complete MCP initialization; fallback never starts another HTTP server.
Failure classification exposed to callers: Distinguish HTTP readiness and policy failures, process startup or transport failure, JSON-RPC error, MCP tool result with `isError: true`, and successful MCP tool result.

## Decision rationale

Rationale: An existing authenticated loopback endpoint permits several local clients to reuse one bounded service, while stdio remains the no-listener fallback owned by the MCP host. The order is deterministic, never creates an implicit listener, and keeps both transports on one server factory and operation implementation.
