# Public interface selection contract

## Status

Selection status: SELECTED

## Execution policy

Preferred agent interface: native MCP tool already registered in the host
Fallback 1: installed human CLI command
Fallback 2: stable in-place CLI launcher

The MCP route is used only when the host has registered the authoritative stdio command. The fallback does not start another MCP server or network listener.

## Contract index

| Selected profile or interface | Authoritative contract |
|---|---|
| Packaged CLI caller behavior | `CLI_INTERFACE.md` |
| MCP caller behavior | `MCP_INTERFACE.md` |
| Runtime, commands, packaging, SDK, revision, and transport selection | `RUNTIME.md` |

## Cross-interface invariants

The MCP tool, installed CLI, and in-place CLI launcher invoke the same `TextStat.analyze` implementation. Equivalent UTF-8 input therefore has identical byte, line, and word semantics. Fallback changes framing and failure classification only; it does not weaken read-only behavior or introduce network access.

## Availability and failure behavior

Unavailable preferred interface behavior: If the MCP tool is not registered or the trusted stdio server cannot start, use the installed CLI only when the documented fallback conditions are satisfied; otherwise report the unavailable interface.
Fallback activation conditions: Use the installed `text-stat` command when MCP is unavailable and the command is on PATH; use the in-place Ruby launcher only from a trusted repository checkout when the installed command is absent and CRuby 3.1 or newer is available.
Failure classification exposed to callers: Distinguish MCP startup or transport failure, JSON-RPC error, MCP tool result with `isError: true`, CLI exit codes 2, 3, or 5, and successful domain results.

## Decision rationale

Rationale: Prefer the host-native MCP route for agent integration and retain the packaged CLI as a deterministic network-free fallback. Sharing one domain implementation proves that the combined profile union adds interfaces rather than duplicate behavior.
