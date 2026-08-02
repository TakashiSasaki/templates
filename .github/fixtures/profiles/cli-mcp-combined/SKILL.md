---
name: text-stat-multi-interface
description: Compute deterministic text statistics through equivalent packaged CLI and stdio MCP interfaces backed by one shared Ruby implementation.
---

# Text statistics multi-interface skill

## Purpose

Provide deterministic byte, line, and word counts through either a host-registered stdio MCP tool or a stable packaged CLI without duplicating domain behavior.

## Use this skill when

Use this skill when an agent environment may expose the text-statistics operation through MCP but also needs a documented CLI fallback for local automation or CI.

## Workflow

1. Follow the preferred route and fallback order in `INTERFACES.md`.
2. When the MCP tool is registered, initialize `bundle exec ruby mcp/server.rb`, discover `text_stats`, and call it with one string-valued `text` argument.
3. When MCP is unavailable and fallback conditions apply, run `text-stat --output json INPUT` or the documented in-place launcher.
4. Distinguish interface availability failures from invalid input, protocol errors, MCP tool errors, and successful domain results.
5. Validate that either interface returns the same byte, line, and word counts for equivalent UTF-8 input.

## Public execution interfaces

Canonical command: text-stat
Working directory: any directory with the installed command on PATH
Preferred agent route: see INTERFACES.md
Detailed interface contract: CLI_INTERFACE.md and MCP_INTERFACE.md

## Output requirements

Return deterministic integer `bytes`, `lines`, and `words` values. CLI structured output must include `contractVersion`, `ok`, and `result`; MCP callers must preserve the complete tool result including additive fields.

## Validation

Run both repository test suites, complete repository validation, gem build and isolated CLI installation, actual stdio MCP initialization and calls, and the cross-interface semantic-equivalence test.

## Safety and approval

Both interfaces are read-only, stateless, and network-free. They may run automatically on caller-supplied readable input. The MCP host owns the trusted child process and must apply bounded shutdown; no interface may modify files or external state.

Selected profiles: packaged-cli, mcp-enabled
