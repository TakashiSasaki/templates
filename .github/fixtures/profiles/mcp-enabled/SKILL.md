---
name: text-stat-mcp
description: Compute deterministic text statistics through one bounded MCP 2026-07-28 Modern stdio tool.
---

# Text statistics MCP skill

## Purpose

Provide deterministic UTF-8 byte, line, and word counts through one read-only MCP tool while serving only the MCP `2026-07-28` Modern protocol.

## Use this skill when

Use this skill when an MCP-capable agent host can register the bundled trusted stdio command and needs deterministic text statistics without opening a network listener.

## Workflow

1. Register `node mcp/server.mjs` as the trusted stdio MCP server from the Skill root.
2. Use Modern discovery and require protocol revision `2026-07-28`; do not retry with a Legacy initialization handshake.
3. Discover `text_stats` through `tools/list`.
4. Call `text_stats` with one string-valued `text` argument.
5. Preserve the MCP result and use its `structuredContent.bytes`, `structuredContent.lines`, and `structuredContent.words` values.
6. Treat transport/protocol failures separately from a successful tool result.
7. Close the stdio client/host connection when finished so the owned child process terminates.

## Public execution interfaces

Stdio server registration command: `node mcp/server.mjs`
Preferred agent route: see INTERFACES.md
Detailed interface contract: MCP_INTERFACE.md
Runtime and protocol authority: RUNTIME.md

## Output requirements

The tool returns deterministic non-negative integer `bytes`, `lines`, and `words` fields in `structuredContent` plus a textual JSON representation in `content`. The implementation has no filesystem, network, workspace, or hidden session state.

## Validation

Run `npm install --ignore-scripts`, `npm run check`, and `npm test`. The executable tests connect through the official MCP TypeScript client using a pinned `2026-07-28` Modern negotiation mode, list and call the tool, reject a `2025-11-25` Legacy `initialize` opening, and verify `UnsupportedProtocolVersionError` for an unsupported Modern revision. The repository fixture harness also runs the canonical Python Skill validators against this concrete profile.

## Safety and approval

The operation is read-only, deterministic, and requires no human confirmation. The stdio server opens no listener, accepts no shell command, performs no file or network I/O, and logs only to stderr. The host owns the process lifetime. No Legacy protocol compatibility, Streamable HTTP endpoint, bundled public client, browser UI, service manager, or optional MCP extension is claimed by this fixture.

Selected profiles: mcp-enabled
