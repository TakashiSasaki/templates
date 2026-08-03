# Public interface selection contract

## Status

Selection status: SELECTED

## Execution policy

Preferred agent interface: existing Streamable HTTP MCP endpoint
Fallback 1: native MCP tool already registered in the host
Fallback 2: NONE

The preferred endpoint is the existing systemd-managed listener described by `RUNTIME.md`. The agent uses it only after systemd reports the unit active and the loopback readiness probe succeeds. The agent never installs, starts, restarts, or stops the unit, never renders deployment files, and never reads the credential source. A separately registered native MCP route may be selected by the host; no stdio server, bundled client, CLI, or non-MCP operation fallback is included.

## Contract index

| Selected profile or interface | Authoritative contract |
|---|---|
| MCP caller behavior | `MCP_INTERFACE.md` |
| Runtime, SDK, systemd lifecycle, credential, exposure, and deployment selection | `RUNTIME.md` |

## Cross-interface invariants

The systemd unit starts only `mcp/http_server.rb`, which uses `mcp/server_factory.rb` and `src/text_stats.rb`. The deployment renderer never calls the domain operation, changes tool semantics, or exposes service control as MCP operations. Direct test launch and systemd launch traverse the same HTTP adapter and tool definition.

## Availability and failure behavior

Unavailable preferred interface behavior: Report inactive-unit, readiness, authentication, request-policy, protocol, capacity, or transport failure without attempting lifecycle control.
Fallback activation conditions: A native MCP tool already registered by the host may be used only when the host explicitly selects it; endpoint failure never triggers automatic process start or cross-transport retry.
Failure classification exposed to callers: Distinguish systemd unit failure, readiness failure, authentication or request-policy failure, MCP initialization or JSON-RPC failure, tool-result `isError`, capacity rejection, transport timeout, and successful tool result.

## Decision rationale

Rationale: systemd ownership is a separate deployment topology from a bundled lifecycle controller. Keeping the listener loopback-only isolates lifecycle, credential, readiness, restart, and control-group behavior without claiming remote-service safety or introducing a second application interface.
