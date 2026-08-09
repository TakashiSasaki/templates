---
name: text-stat-mcp-apps
description: Compute deterministic text statistics through MCP 2026-07-28 with optional MCP Apps presentation.
---

# Text statistics MCP Apps skill

## Purpose

Provide deterministic UTF-8 byte, line, and word counts through a Modern MCP stdio server. Hosts that negotiate `io.modelcontextprotocol/ui` may additionally render the bundled sandboxed result View; Hosts without Apps support receive the same complete core result.

## Use this skill when

Use this skill when an MCP-capable agent Host can register the trusted bundled stdio server and may benefit from a Host-embedded interactive presentation without requiring a standalone Web application.

## Workflow

1. Register `node mcp/server.mjs` as the trusted stdio server from the Skill root.
2. Require MCP core revision `2026-07-28`; never retry with a Legacy initialization handshake.
3. If the Host supports MCP Apps, advertise `io.modelcontextprotocol/ui` with `text/html;profile=mcp-app`; otherwise continue as a core-only Host.
4. Discover the raw tool inventory and apply Apps visibility rules in the Host when the extension is active.
5. Call `text_stats` with one string-valued `text` argument.
6. Preserve the textual core result and `structuredContent` regardless of Apps support.
7. When Apps is active, read `ui://text-stats/result`, initialize the View bridge with `ui/initialize` / `ui/notifications/initialized`, and send the completed tool result to the View only after initialization.
8. Close the MCP client/Host connection when finished.

## Public execution interfaces

Stdio server registration command: `node mcp/server.mjs`
Preferred agent route: see INTERFACES.md
Core MCP contract: MCP_INTERFACE.md
MCP Apps contract: MCP_APPS.md
Runtime, core revision, and extension selection authority: RUNTIME.md

## Output requirements

`text_stats` returns non-negative integer `bytes`, `lines`, and `words` in `structuredContent` plus a textual JSON representation in `content`. The Apps View may present those aggregate fields but does not replace the core result. `refresh_stats` is App-only and `model_summary` is model-only in Host-derived visibility views.

## Validation

Run `npm install --ignore-scripts`, `npm run check`, and `npm test`. The executable evidence uses the official MCP TypeScript core SDK 2.0.0 for Modern discovery, tools, resources, and stdio. It validates Apps `2026-01-26` resource, metadata, visibility, progressive fallback, security metadata, and View↔Host lifecycle directly against the stable extension contract.

The repository fixture harness also runs the canonical Skill validators, including the MCP `2026-07-28` semantic gate and MCP extension activation validator, against this concrete Skill.

## Safety and approval

All tools are deterministic and read-only. The server opens no listener, performs no remote network access, and uses no credentials. The App resource declares no external CSP origin and requests no browser permission. The Host bridge denies model-only and cross-server App-mediated calls and does not send ordinary messages to the View before bridge initialization completes.

Selected profiles: mcp-enabled
