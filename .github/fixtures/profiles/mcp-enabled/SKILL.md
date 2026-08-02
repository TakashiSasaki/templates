---
name: text-stat-mcp
description: Compute deterministic text statistics through one bounded MCP tool exposed over trusted stdio or an explicitly started loopback Streamable HTTP endpoint.
---

# Text statistics MCP skill

## Purpose

Provide deterministic byte, line, and word counts through one caller-visible MCP tool while preserving equivalent behavior across trusted stdio and authenticated loopback Streamable HTTP transports.

## Use this skill when

Use this skill when an MCP-capable agent host needs read-only text statistics and can either register the bundled stdio command or connect to an already configured local HTTP endpoint.

## Workflow

1. Prefer the configured Streamable HTTP endpoint when `GET /readyz` succeeds and the caller possesses the externally supplied Bearer token.
2. Otherwise register `bundle exec ruby mcp/server.rb` as a trusted stdio MCP server from the skill root; do not start an HTTP listener as an implicit fallback.
3. Initialize the selected transport and verify that the response selects protocol revision `2025-11-25`; end the session if the caller cannot accept that revision.
4. Send `notifications/initialized`, then discover the `text_stats` tool through `tools/list`.
5. Call `text_stats` with one string-valued `text` argument and preserve the complete MCP result.
6. Treat transport failures, HTTP authentication or request-policy failures, JSON-RPC errors, MCP tool errors, and successful results as distinct outcomes.
7. Close stdio through the owning host, or delete the HTTP session and leave process shutdown to the operator that explicitly started the endpoint.

## Public execution interfaces

Stdio server registration command: bundle exec ruby mcp/server.rb
Streamable HTTP endpoint: http://127.0.0.1:4570/mcp by default
Preferred agent route: see INTERFACES.md
Detailed interface contract: MCP_INTERFACE.md

## Output requirements

Return one MCP tool result containing deterministic `bytes`, `lines`, and `words` integer fields. Preserve the complete MCP result, including `content`, `structuredContent`, `isError`, `_meta`, and future additive fields supplied by the server.

## Validation

Run `bundle install`, then `bundle exec ruby tests/test_mcp_server.rb`, `bundle exec ruby tests/test_http_server.rb`, `bundle exec ruby tests/test_http_boundaries.rb`, and `bundle exec ruby tests/test_http_lifecycle.rb`. The repository fixture harness also runs `ruby .github/scripts/validate-skill-repository.rb`, syntax checks every adapter and test, verifies canonical default-port authority handling, idle-expiry recovery, bounded post-disconnect completion and session reuse, pending startup shutdown delivery, and process-group timeout cleanup, and rejects missing shared implementation, adapters, or required contracts.

## Safety and approval

The operation is read-only and requires no human confirmation. The stdio route opens no listener and writes protocol messages only to stdout. The HTTP route starts only by explicit operator action, binds only to `127.0.0.1`, requires an externally supplied Bearer token on every MCP request, validates canonical Host authority and effective-port Origin on every request, accepts no non-loopback mode, and never places the token in command arguments, stdout, or diagnostics. Starting or stopping the HTTP listener remains an externally visible operator action and must not occur implicitly as fallback behavior. TERM or INT received during startup remains pending until the server instance can be shut down.

Selected profiles: mcp-enabled
