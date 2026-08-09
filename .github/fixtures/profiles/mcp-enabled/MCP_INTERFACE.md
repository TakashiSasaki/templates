# MCP public interface contract

## Status

Selection status: SELECTED

## MCP protocol reference

Runtime, SDK, revision, era boundary, and schema source of truth: RUNTIME.md
Public negotiation and fallback behavior: The server implements `server/discover`, serves only MCP `2026-07-28`, requires Modern per-request metadata, and returns `UnsupportedProtocolVersionError` for unsupported revisions. It never falls back to the Legacy initialization handshake.
Public compatibility statement: Only MCP `2026-07-28` Modern behavior is supported. Revisions `2025-11-25` and earlier are intentionally unsupported because this fixture represents the unpublished template baseline.

The official SDK supplies protocol-version and client-capability metadata on every Modern request. The server does not accept `initialize` as a compatibility path and does not require the Legacy initialized notification.

## stdio MCP server variant

Supported: YES
Launch command: `node mcp/server.mjs`
Lifecycle owner: MCP host or the maintainer test client's `StdioClientTransport`

The server uses the official TypeScript SDK `serveStdio` entry with `legacy: "reject"`. stdout is protocol-only, diagnostics go to stderr, and `server/discover` identifies the supported Modern revision before ordinary tool calls. The only tool, `text_stats`, is read-only and delegates to `src/text_stats.mjs`.

## Streamable HTTP MCP server variant

Supported: NO
Start command: NOT SUPPORTED
Stop command or shutdown method: NOT SUPPORTED
Endpoint URL: NOT SUPPORTED
Bind address: NOT SUPPORTED
Port selection: NOT SUPPORTED
Supported protocol eras: NOT SUPPORTED
Revision-specific state model: NOT SUPPORTED; the fixture opens no HTTP MCP endpoint.
Authentication: NOT SUPPORTED
Health/readiness check: NOT SUPPORTED

This fixture makes no Streamable HTTP conformance claim. The template retains a conditional Modern Streamable HTTP contract for concrete Skills that select it.

## Bundled ad hoc MCP tool client

Supported: NO
Scope: NOT SUPPORTED
Command: NOT SUPPORTED
Transport used: NOT SUPPORTED
Negotiation and compatibility behavior: NOT SUPPORTED; `tests/test_mcp.mjs` uses the official client package only as source-maintainer evidence.
Invocation scope: NOT SUPPORTED
Interaction modes: NOT SUPPORTED
Task or extension support: NOT SUPPORTED

No public client command, option surface, or serialization contract exists in this fixture. Test-only client code is evidence rather than a second distributed interface.

### Recommended command mapping

No public command mapping applies because the bundled client is not supported. Maintainer tests call the official SDK directly and do not invent MCP methods.

### Recommended options

No public client options apply because the bundled client is not supported.

### Tool inventory, schemas, and caching

The Modern maintainer client calls `tools/list` and requires exactly `text_stats`. The input schema accepts one string field named `text`; the output schema declares non-negative integer `bytes`, `lines`, and `words`. This one-page fixture claims no cross-request cache behavior.

### Lossless paginated tool-list output

The fixture publishes no client-side list serialization. Maintainer evidence inspects the SDK result directly. A concrete Skill that selects a bundled client must preserve raw result pages according to the template contract.

### Tool-call results and errors

`text_stats` returns textual content plus `structuredContent`. The official Modern codec supplies revision-required result typing. Tests distinguish protocol-version failures from a successful tool result and verify the structured fields exactly.

### Multiple calls and application state

The operation is deterministic and keeps no hidden application or protocol-session state. Reusing one Modern stdio connection does not change operation semantics.

### Selected modern multi-round-trip requests

The `text_stats` operation never requires additional input, so it never returns `input_required`. Any concrete operation that needs additional client input must use the Modern MRTR result/retry model defined by MCP `2026-07-28`.

### Selected initialization-era server-to-client requests

NOT SUPPORTED. The fixture advertises no Legacy elicitation, sampling, roots, or initialization-session request channel. A Legacy `initialize` opening is negative evidence and receives the unsupported-protocol-version error.

### Cancellation, tasks, and extensions

The fixture advertises no Tasks or other optional extension. Closing the test client closes the stdio transport and owned child process. The bounded tool does not detach work. Optional extensions require an independently versioned, capability-gated contract before they can be claimed.

### Ownership and workspace policy

The MCP host owns the trusted `node mcp/server.mjs` child process. The fixture exposes no arbitrary command launcher, workspace argument, filesystem write, network call, or deprecated Roots capability. Its only domain input is the explicit `text` tool argument.

## Semantic-equivalence and test requirements

`src/text_stats.mjs` is the single domain implementation. Tests prove Modern discovery, official-client connection, exact tool inventory, deterministic structured results, rejection of a `2025-11-25` Legacy initialization opening, and rejection of an unsupported future revision with error code `-32022`. stdio is the only public adapter, so no cross-transport equivalence claim is made.

## Decision rationale

Rationale: The fixture is deliberately small and Modern-only. It uses the official TypeScript MCP SDK 2.0.0 serving API with explicit Legacy rejection so executable evidence directly proves the initial template's `2026-07-28` baseline without retaining unpublished compatibility machinery.
