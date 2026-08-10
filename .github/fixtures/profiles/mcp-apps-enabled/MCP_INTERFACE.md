# MCP public interface contract

## Status

Selection status: SELECTED

## MCP protocol reference

Runtime, SDK, revision, era boundary, and schema source of truth: RUNTIME.md
Public negotiation and fallback behavior: The server implements `server/discover`, serves only MCP `2026-07-28`, requires Modern per-request metadata, and returns `UnsupportedProtocolVersionError` for unsupported revisions. It advertises `io.modelcontextprotocol/ui` as an optional extension but keeps core tool behavior usable when the Host does not advertise Apps.
Public compatibility statement: Only MCP `2026-07-28` Modern behavior is supported. Apps-specific behavior is separately authoritative in `MCP_APPS.md` and does not restore Legacy core initialization.

The official SDK supplies protocol-version and client-capability metadata on every Modern request. Apps-capable Hosts additionally advertise `capabilities.extensions.io.modelcontextprotocol/ui.mimeTypes`; core-only Hosts omit that extension and continue to use ordinary tool results.

## stdio MCP server variant

Supported: YES
Launch command: `node mcp/server.mjs`
Lifecycle owner: see RUNTIME.md

The server uses the official TypeScript SDK `serveStdio` entry with `legacy: "reject"`. stdout is protocol-only, diagnostics go to stderr, and `server/discover` reports core `2026-07-28` plus the selected Apps extension capability. `text_stats`, `refresh_stats`, and `model_summary` delegate to the same deterministic domain implementation; Host visibility policy determines which tools are model- or App-visible.

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

This fixture makes no Streamable HTTP conformance claim. Apps resource and bridge semantics are independent of the core transport selected here.

## Bundled ad hoc MCP tool client

Supported: NO
Scope: NOT SUPPORTED
Command: NOT SUPPORTED
Transport used: NOT SUPPORTED
Negotiation and compatibility behavior: NOT SUPPORTED; official SDK clients and the Host bridge model under `tests/` are source-maintainer evidence only.
Invocation scope: NOT SUPPORTED
Interaction modes: NOT SUPPORTED
Task or extension support: MCP Apps `io.modelcontextprotocol/ui` is server capability evidence only; there is no bundled public client.

No public client command, option surface, or serialization contract exists in this fixture.

### Recommended command mapping

No public command mapping applies because the bundled client is not supported. Maintainer tests call the official SDK directly.

### Recommended options

No public client options apply because the bundled client is not supported.

### Tool inventory, schemas, and caching

The raw MCP `tools/list` inventory contains `text_stats`, `refresh_stats`, and `model_summary` plus Apps `_meta.ui` metadata. An Apps Host derives the model-visible inventory and App-visible inventory from the selected extension visibility rules; raw server results are not rewritten by the fixture. Each tool accepts one string `text` field and returns non-negative integer `bytes`, `lines`, and `words` fields.

### Lossless paginated tool-list output

The fixture publishes no bundled-client serialization. Maintainer tests inspect the SDK result directly before deriving visibility-filtered Host views.

### Tool-call results and errors

`text_stats` returns textual `content` plus `structuredContent`. The same core result is returned to Apps-capable and core-only Hosts. UI rendering failure therefore cannot erase the primary MCP result. Host-side App visibility denial is distinct from a server tool error.

### Multiple calls and application state

All three tools are deterministic and keep no hidden application or protocol-session state. Reusing one Modern stdio connection does not change operation semantics. The Apps View lifecycle is Host-local state and is not an MCP server session.

### Selected modern multi-round-trip requests

The fixture tools never require additional input, so they never return `input_required`. Any concrete tool that needs additional input must use the Modern MRTR result/retry model.

### Selected initialization-era server-to-client requests

NOT SUPPORTED. Core Legacy `initialize`, elicitation, sampling, roots, and initialization-session callbacks are not advertised. Apps `ui/initialize` is a separate View↔Host bridge request governed by `MCP_APPS.md`.

### Cancellation, tasks, and extensions

The only optional extension is `io.modelcontextprotocol/ui`. Its exact revision, resources, visibility, bridge lifecycle, sandbox policy, and failure behavior are in `MCP_APPS.md`. Closing a core test client closes the stdio transport and child process. The Apps bridge model has no detached work.

### Ownership and workspace policy

The MCP Host owns the trusted `node mcp/server.mjs` child process. The fixture exposes no arbitrary command launcher, workspace argument, filesystem write beyond reading its bundled HTML resource, remote network call, credential, or deprecated Roots capability.

## Semantic-equivalence and test requirements

`src/text_stats.mjs` is the single domain implementation. Tests prove Modern discovery, extension settings, exact Apps resource metadata, tool-to-UI linkage, model/App visibility derivation, same-server App-only calls, denial of model-only and cross-server App calls, core fallback without Apps capability, and the separate Apps bridge lifecycle. stdio is the only core MCP transport, so no cross-transport equivalence claim is made.

## Decision rationale

Rationale: The fixture adds MCP Apps as progressive enhancement of a small Modern stdio server. Core MCP stays independently conformant and useful without an App-capable Host, while Apps-specific presentation and bridge semantics are isolated in `MCP_APPS.md` and executable Host simulation.
