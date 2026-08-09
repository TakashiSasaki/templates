# MCP implementation

This concrete maintainer fixture bundles one MCP `2026-07-28` Modern stdio server.

- `server.mjs` builds the `text_stats` tool with the official TypeScript MCP SDK 2.0.0.
- `serveStdio(createServer, { legacy: "reject" })` is mandatory for this fixture; a hand-wired 2025-era transport is not equivalent.
- `src/text_stats.mjs` is the only domain implementation.
- `tests/test_mcp.mjs` is maintainer evidence, not a bundled public client.

The fixture has no Streamable HTTP endpoint, no protocol sessions, no browser UI, no service controller, no deprecated Roots/Sampling/Logging capabilities, and no optional MCP extensions.
