# Public interface selection contract

## Status

Selection status: SELECTED

## Execution policy

Preferred agent interface: native MCP tool already registered in the host
Fallback 1: NONE
Fallback 2: NONE

The host registration uses the authoritative stdio launch command in `RUNTIME.md`. This fixture does not expose a public ad hoc client and does not start a network server as an implicit fallback.

## Contract index

| Selected profile or interface | Authoritative contract |
|---|---|
| MCP caller behavior | `MCP_INTERFACE.md` |
| Runtime, SDK, revision, command, and transport selection | `RUNTIME.md` |

## Cross-interface invariants

There is one maintained public interface. Test clients traverse the actual stdio MCP transport and do not call the operation implementation directly when asserting protocol behavior. Registration, discovery, tool calls, errors, and shutdown therefore exercise the same server adapter that an MCP host uses.

## Availability and failure behavior

Unavailable preferred interface behavior: Report that the MCP server is not registered or could not be started; do not substitute a non-MCP call.
Fallback activation conditions: No fallback is activated.
Failure classification exposed to callers: Distinguish process startup or transport failure, JSON-RPC error, MCP tool result with `isError: true`, and successful MCP tool result.

## Decision rationale

Rationale: A host-registered stdio tool is the smallest caller-visible route, opens no listening socket, and gives the host direct ownership of initialization, timeouts, and child-process shutdown. A public bundled client or HTTP endpoint would expand this fixture beyond the selected contract.
