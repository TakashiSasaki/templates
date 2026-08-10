# Public interface selection contract

## Status

Selection status: SELECTED

## Execution policy

Preferred agent interface: native MCP tool already registered in the host
Fallback 1: NONE
Fallback 2: NONE

The representative fixture exposes only a trusted Modern stdio MCP server. A host registers `node mcp/server.mjs`; no network endpoint, bundled public client, CLI fallback, or browser fallback is defined. The host must require MCP `2026-07-28` and must not fall back to an initialization-based revision.

## Contract index

| Selected profile or interface | Authoritative contract | Retention rule |
|---|---|---|
| `mcp-enabled` | `MCP_INTERFACE.md` | Required for this fixture |
| Runtime, commands, dependency and protocol selection | `RUNTIME.md` | Required for this fixture |

## Cross-interface invariants

There is one maintained public interface and one domain implementation. `mcp/server.mjs` delegates `text_stats` to `src/text_stats.mjs`; test-only MCP client code is evidence and is not a second public interface. No fallback changes identity, authorization, workspace, side effects, or protocol era because no fallback is permitted.

## Availability and failure behavior

Unavailable preferred interface behavior: Surface the stdio process, Modern discovery, protocol, or tool error; do not start another transport or use a Legacy protocol revision.
Fallback activation conditions: NONE; the fixture intentionally has no public fallback route.
Failure classification exposed to callers: Distinguish process/transport failure, Modern protocol negotiation or unsupported-version error, JSON-RPC/MCP error, tool error result, and successful tool result.

## Decision rationale

Rationale: A single Modern stdio route is the smallest executable proof of the unpublished template's MCP `2026-07-28` baseline. Omitting HTTP and CLI fallbacks keeps transport deployment concerns out of the core protocol fixture and makes accidental Legacy compatibility observable as a test failure.
