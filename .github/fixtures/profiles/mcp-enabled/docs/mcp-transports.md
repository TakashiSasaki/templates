# MCP transport decisions for the Modern fixture

This fixture selects only trusted stdio and only MCP core revision `2026-07-28`.

## stdio

- Entry point: `node mcp/server.mjs`.
- Serving API: official `@modelcontextprotocol/server` 2.0.0 `serveStdio` entry.
- Legacy mode: `reject`.
- Discovery: `server/discover` with the Modern request metadata envelope.
- Protocol revision: exactly `2026-07-28`.
- Process owner: the MCP host or maintainer test transport.
- stdout: MCP traffic only.
- stderr: diagnostics only.

The official client evidence pins `2026-07-28`; it does not use automatic era fallback.

## Streamable HTTP

NOT SUPPORTED by this fixture. No listener, endpoint, authentication policy, protocol session, readiness endpoint, GET stream, session DELETE, or resumability behavior is claimed.

The copyable template still documents Modern Streamable HTTP for concrete Skills that intentionally select it. This fixture stays stdio-only so its evidence isolates core protocol revision semantics from deployment and HTTP security concerns.

## Negative evidence

`tests/test_mcp.mjs` sends a Legacy `initialize` opening and requires `UnsupportedProtocolVersionError`. It also sends a Modern-envelope request naming an unsupported future revision and requires the same error with the requested and supported revisions identified.
