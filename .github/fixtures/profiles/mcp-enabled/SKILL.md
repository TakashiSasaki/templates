---
name: text-stat-mcp
description: Compute deterministic text statistics through one bounded stdio MCP tool implemented with the official Ruby SDK.
---

# Text statistics MCP skill

## Purpose

Provide deterministic byte, line, and word counts through a caller-visible MCP tool without opening a network listener.

## Use this skill when

Use this skill when an MCP-capable agent host needs read-only text statistics and can register a trusted bundled stdio server command.

## Workflow

1. Register `bundle exec ruby mcp/server.rb` as a stdio MCP server from the skill root.
2. Initialize the server with protocol revision `2025-11-25`.
3. Discover the `text_stats` tool through `tools/list`.
4. Call `text_stats` with one string-valued `text` argument.
5. Treat transport errors, JSON-RPC errors, MCP tool errors, and successful results as distinct outcomes.
6. Close the server input and wait for bounded child-process shutdown when the host is finished.

## Public execution interfaces

Server registration command: bundle exec ruby mcp/server.rb
Preferred agent route: see INTERFACES.md
Detailed interface contract: MCP_INTERFACE.md

## Output requirements

Return one MCP tool result containing deterministic `bytes`, `lines`, and `words` integer fields. Preserve the complete MCP result, including `content`, `structuredContent`, `isError`, `_meta`, and future additive fields supplied by the server.

## Validation

Run `bundle install`, then `bundle exec ruby tests/test_mcp_server.rb`, and run the repository validator with `ruby .github/scripts/validate-skill-repository.rb` when this fixture is copied into a temporary repository by the fixture harness.

## Safety and approval

The server is read-only, opens no network listener, writes only MCP protocol messages to stdout, sends diagnostics only to stderr, and terminates when its owning host closes stdin or stops the child process. No human confirmation is required for the `text_stats` operation.

Selected profiles: mcp-enabled
