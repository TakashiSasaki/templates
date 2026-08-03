# Public interface selection contract

## Status

Selection status: SELECTED

## Execution policy

Preferred agent interface: existing Streamable HTTP MCP endpoint
Fallback 1: native MCP tool already registered in the host
Fallback 2: bundled ad hoc MCP tool client over stdio or Streamable HTTP

The preferred route means the configured endpoint is used only when readiness succeeds and the caller has the required Bearer token. The agent checks that existing endpoint but never starts another listener implicitly. When an agent needs a bounded local discovery or invocation helper and no native MCP route is available, it may explicitly invoke the private bundled client, which launches only the fixed stdio server command. This helper is not a stable public CLI and there is no non-MCP operation fallback.

## Contract index

| Selected profile or interface | Authoritative contract |
|---|---|
| MCP caller behavior | `MCP_INTERFACE.md` |
| Runtime, SDK, revision, command, transport, security, and lifecycle selection | `RUNTIME.md` |

## Cross-interface invariants

Both maintained routes use `mcp/server_factory.rb`, the same `TextStatsTool`, and the same `src/text_stats.rb` operation. Test clients traverse the actual stdio and Streamable HTTP transports, initialize the same selected revision, discover the same tool definition, and prove equal structured results for the same input. Neither adapter calls a transport-specific domain implementation.

## Availability and failure behavior

Unavailable preferred interface behavior: Report the HTTP readiness, authentication, request-policy, or transport failure, then use the trusted stdio route only when the host explicitly selects the private bundled client.
Fallback activation conditions: The configured HTTP endpoint is absent, fails `GET /readyz`, rejects the caller, or cannot complete MCP initialization; fallback never starts another HTTP server and never retries a request across transports.
Failure classification exposed to callers: Distinguish HTTP readiness failures from MCP authentication or capacity failures, HTTP policy failures, process startup or transport failure, bounded timeout, JSON-RPC error, MCP tool result with `isError: true`, invalid result, pagination failure, and successful MCP tool result. The private helper bounds `tools run` to 32 sequential calls and preserves completed results when a later call fails.

## Decision rationale

Rationale: An existing authenticated loopback endpoint permits several local clients to reuse one bounded service, while stdio remains the no-listener fallback owned by the MCP host. The order is deterministic, never creates an implicit listener, and keeps both transports on one server factory and operation implementation.
