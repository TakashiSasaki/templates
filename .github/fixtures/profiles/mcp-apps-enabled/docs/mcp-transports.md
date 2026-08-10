# MCP transport decisions

This fixture selects only trusted stdio for core MCP traffic.

## Core stdio

- Core revision: `2026-07-28` Modern only.
- Entry point: `node mcp/server.mjs`.
- Official serving API: `@modelcontextprotocol/server` 2.0.0 `serveStdio` with `legacy: "reject"`.
- Discovery: `server/discover`.
- Process owner: MCP Host or maintainer test client.
- stdout: MCP protocol traffic only.
- stderr: diagnostics only.

## MCP Apps extension

The Apps extension does not add a second core transport. The MCP server advertises `io.modelcontextprotocol/ui` through the Modern core extension capability map and exposes the App as the standard MCP resource `ui://text-stats/result`.

After the Host reads the resource and creates its sandboxed View, View↔Host traffic uses the Apps JSON-RPC `postMessage` bridge defined by `MCP_APPS.md`. That bridge is separate from stdio Host↔server traffic and its `ui/initialize` method is not the removed core Legacy initialization handshake.

## Streamable HTTP

NOT SUPPORTED by this fixture. There is no HTTP MCP endpoint, network listener, standalone browser route, protocol session, GET stream, session DELETE, or SSE resumability claim.

## Security boundary

The server reads only its bundled `mcp/apps/result.html` resource and performs no remote network I/O. The resource declares empty external CSP domain lists and no browser permissions. Host simulation denies App calls to model-only tools and all cross-server app-only calls.
