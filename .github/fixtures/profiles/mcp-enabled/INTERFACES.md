# Public interface selection contract

## Status

Selection status: SELECTED

## Execution policy

Preferred agent interface: existing Streamable HTTP MCP endpoint
Fallback 1: native MCP tool already registered in the host
Fallback 2: bundled ad hoc MCP tool client over stdio or Streamable HTTP

The preferred route means the configured endpoint is used only when readiness succeeds and the caller has the required Bearer token. The agent checks that existing endpoint but never starts, restarts, or stops a listener implicitly. An operator may choose either direct foreground launch or the private managed local lifecycle controller before agent execution. When an agent needs a bounded local discovery or invocation helper and no native MCP route is available, it may explicitly invoke the private bundled client, which launches only the fixed stdio server command. Neither helper is a stable public CLI and there is no non-MCP operation fallback.

## Contract index

| Selected profile or interface | Authoritative contract |
|---|---|
| MCP caller behavior | `MCP_INTERFACE.md` |
| Runtime, SDK, revision, command, transport, security, and lifecycle selection | `RUNTIME.md` |

## Cross-interface invariants

Both maintained transports use `mcp/server_factory.rb`, the same `TextStatsTool`, and the same `src/text_stats.rb` operation. Direct foreground and managed local HTTP modes execute the same `mcp/http_server.rb` adapter and do not define a second listener implementation. Test clients traverse the actual stdio and Streamable HTTP transports, initialize the same selected revision, discover the same tool definition, and prove equal structured results for the same input. No lifecycle controller calls the domain implementation or exposes service control as an MCP operation.

## Availability and failure behavior

Unavailable preferred interface behavior: Report the HTTP readiness, liveness, authentication, request-policy, lifecycle, or transport failure, then use the trusted stdio route only when the host explicitly selects the private bundled client.
Fallback activation conditions: The configured HTTP endpoint is absent, fails readiness, rejects the caller, or cannot complete MCP initialization; fallback never starts another HTTP server, invokes lifecycle control, or retries a request across transports.
Failure classification exposed to callers: Distinguish HTTP readiness and liveness failures, managed start/stop/restart and stale-record failures, authentication or capacity failures, HTTP policy failures, process startup or transport failure, bounded timeout, JSON-RPC error, MCP tool result with `isError: true`, invalid result, pagination failure, and successful MCP tool result. The private helper bounds `tools run` to 32 sequential calls and preserves completed results when a later call fails.

## Decision rationale

Rationale: An existing authenticated loopback endpoint permits several local clients to reuse one bounded service, while stdio remains the no-listener fallback owned by the MCP host. Optional managed lifecycle gives an operator bounded local process control without becoming an agent interface, widening the network boundary, or claiming an OS service manager. The order remains deterministic and keeps both transports on one server factory and operation implementation.
