# MCP public interface contract

## Status

Selection status: SELECTED

## MCP protocol reference

Runtime, SDK, revision, era boundary, and schema source of truth: RUNTIME.md
Public negotiation and fallback behavior: The server is Modern-only. Clients discover `2026-07-28` through `server/discover` or send a `2026-07-28` request directly; unsupported revisions receive `UnsupportedProtocolVersionError`. There is no Legacy fallback.
Public compatibility statement: Only MCP `2026-07-28` Modern behavior is supported. Initialization-based MCP revisions are intentionally unsupported because this fixture represents the unpublished template baseline.

The official SDK supplies per-request protocol version and client-capability metadata on Modern calls. The server does not accept `initialize` as a compatibility path and does not require `notifications/initialized`.

## stdio MCP server variant

Supported: YES
Launch command: `node mcp/server.mjs`
Lifecycle owner: MCP host or the test client's `StdioClientTransport`

The server uses the official TypeScript SDK's `serveStdio` entry with `legacy: "reject"`. stdout is protocol-only and diagnostics go to stderr. `server/discover` advertises the supported Modern revision before ordinary tool calls. The only tool, `text_stats`, is read-only and delegates to `src/text_stats.mjs`.

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

The fixture deliberately makes no Streamable HTTP conformance claim. The template retains Modern Streamable HTTP contract guidance for concrete Skills that select it, but this representative executable evidence isolates core protocol behavior on stdio.

## Bundled ad hoc MCP tool client

Supported: NO
Scope: NOT SUPPORTED
Command: NOT SUPPORTED
Transport used: NOT SUPPORTED
Negotiation and compatibility behavior: NOT SUPPORTED; `tests/test_mcp.mjs` uses the official client package only as maintainer evidence.
Invocation scope: NOT SUPPORTED
Interaction modes: NOT SUPPORTED
Task or extension support: NOT SUPPORTED

There is no public bundled client in this fixture. Test-only client code must not be interpreted as a distributed Skill interface.

### Recommended command mapping

The fixture defines no public client command mapping. Maintainer tests call the official SDK directly so the evidence cannot be mistaken for an invented MCP CLI method.

### Recommended options

No public client options are defined because the bundled client is not supported.

### Tool inventory, schemas, and caching

The Modern test client calls `tools/list` and requires exactly the `text_stats` tool. The tool input schema accepts one string field named `text`; the output schema describes non-negative integer `bytes`, `lines`, and `words` fields. The fixture does not claim pagination, cache-hint, or cross-request inventory caching behavior beyond what the SDK and selected core revision provide for this one-page inventory.

### Lossless paginated tool-list output

The fixture does not publish a client-side serialization contract. The maintainer test inspects the SDK result without flattening the tool names before checking the one-page inventory. A concrete Skill that adds a bundled client must preserve raw pages according to the template contract.

### Tool-call results and errors

`text_stats` returns textual content plus `structuredContent`. The Modern wire representation is produced by the official SDK and therefore carries the revision-required result typing. The test checks the decoded structured result and distinguishes protocol negotiation failures from a successful tool result.

### Multiple calls and application state

The operation is deterministic and has no hidden application state. Reusing one Modern stdio connection does not alter results. The fixture makes no protocol-session state claim because Modern MCP has no initialization session.

### Selected modern multi-round-trip requests

The `text_stats` operation never requires additional input after the initial call, so it does not return `input_required`. If a future operation needs additional client input, it must use the Modern MRTR result/retry model rather than a server-to-client request channel.

### Selected initialization-era server-to-client requests

NOT SUPPORTED. The fixture neither advertises nor implements Legacy elicitation, sampling, roots, or initialization-session callbacks. A Legacy `initialize` opening is a negative test and must receive the unsupported-protocol-version error identifying `2026-07-28` as supported.

### Cancellation, tasks, and extensions

The fixture advertises no Tasks extension or other optional extension. Closing the test client closes the stdio transport and child process. The bounded tool completes synchronously and does not detach work. Extension behavior will be added only through an independently versioned and capability-gated contract.

### Ownership and workspace policy

The MCP host owns the trusted `node mcp/server.mjs` child process. The fixture exposes no arbitrary command launcher, workspace argument, filesystem write, network call, or deprecated Roots capability. Its only input is the explicit `text` tool argument.

## Semantic-equivalence and test requirements

`src/text_stats.mjs` is the single domain implementation. MCP tests prove Modern discovery, official-client connection, exact tool inventory, deterministic structured results, rejection of the `2025-11-25` Legacy initialization opening, and rejection of an unsupported future revision with error code `-32022`. The fixture's stdio path is the only public adapter, so no cross-transport equivalence is claimed.

## Decision rationale

Rationale: The fixture is deliberately small and Modern-only. It uses the official TypeScript SDK 2.0.0 serving API with explicit Legacy rejection so the executable evidence directly proves the initial template's `2026-07-28` baseline instead of carrying compatibility machinery that has never been published to users.
