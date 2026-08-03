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

1. Prefer the configured Streamable HTTP endpoint when readiness succeeds and the caller possesses the externally supplied Bearer token.
2. Otherwise register `bundle exec ruby mcp/server.rb` as a trusted stdio MCP server from the skill root; do not start an HTTP listener as an implicit fallback.
3. If a bounded local tool client is required and no native MCP route is available, invoke only the fixed helper `bundle exec ruby mcp/client.rb`; select `--transport http` only with an existing loopback endpoint and externally supplied token, or use its fixed stdio server fallback.
4. An operator may explicitly select the managed local HTTP variant with `TEXT_STATS_MCP_HTTP_TOKEN_FILE=/path/to/mode-0600-token bundle exec ruby mcp/service_manager.rb start`. This is not an agent fallback and must never be started implicitly.
5. Initialize the selected transport and verify that the response selects protocol revision `2025-11-25`; end the session if the caller cannot accept that revision.
6. Send `notifications/initialized`, then discover the `text_stats` tool through `tools/list`.
7. Call `text_stats` with one string-valued `text` argument and preserve the complete MCP result.
8. Treat readiness, liveness, lifecycle, transport, HTTP authentication or request-policy, JSON-RPC, MCP tool, and successful outcomes as distinct.
9. Close stdio through the owning host, delete the HTTP session, and leave manual or managed process shutdown to the operator that explicitly selected that lifecycle.

## Public execution interfaces

Stdio server registration command: bundle exec ruby mcp/server.rb
Streamable HTTP endpoint: http://127.0.0.1:4570/mcp by default
Preferred agent route: see INTERFACES.md
Detailed interface contract: MCP_INTERFACE.md

## Output requirements

Return one MCP tool result containing deterministic `bytes`, `lines`, and `words` integer fields. Preserve the complete MCP result, including `content`, `structuredContent`, `isError`, `_meta`, and future additive fields supplied by the server. The private client validates known initialization capability shapes, requires `application/json` for JSON HTTP responses, requires each listed tool's `inputSchema.type` discriminator to be `object`, its optional `outputSchema` to be an object when present, its optional `annotations` to be an object with string `title` and boolean known hint fields when present, and its optional `_meta` to be an object, and rejects any individual JSON response body or stdio message larger than 65,536 bytes before JSON parsing. Sequential `tools run` calls are bounded to at most 32 operations, and completed results remain available when a later operation fails. It accepts only non-interactive bounded JSON arguments: terminal `--arguments-stdin` is rejected, and a producer that does not provide EOF is bounded by the configured `--timeout` before transport startup.

## Validation

Run `bundle install`, then `bundle exec ruby tests/test_mcp_server.rb`, `bundle exec ruby tests/test_http_server.rb`, `bundle exec ruby tests/test_http_boundaries.rb`, `bundle exec ruby tests/test_http_lifecycle.rb`, `bundle exec ruby tests/test_mcp_client.rb`, and `bundle exec ruby tests/test_service_manager.rb`. The repository fixture harness also runs `ruby .github/scripts/validate-skill-repository.rb`, syntax checks every adapter, client, controller, and test, verifies lossless page and call results, bounded client timeout and cleanup, canonical default-port authority handling, idle-expiry recovery, bounded post-disconnect completion and session reuse, pending startup shutdown delivery, managed start/ready/live/restart/stop, per-start instance-owned health, lifecycle-lock serialization, external-secret and inode-alias validation, protected runtime directories, stale-record handling, failed-start record retention, and synchronized process-group timeout escalation, and rejects missing implementation or required contracts.

## Safety and approval

The operation is read-only and requires no human confirmation. The stdio route opens no listener and writes protocol messages only to stdout. The HTTP route starts only by explicit operator action, binds only to `127.0.0.1`, requires an externally supplied Bearer token on every MCP request, validates canonical Host authority and effective-port Origin on every request, accepts no non-loopback mode, and never places the token in command arguments, PID metadata, stdout, stderr, or managed logs. Managed mode requires a service-user-owned token file with no group or other permissions, serializes lifecycle commands, requires a matching per-start nonce for readiness and liveness, identity-verifies PID plus Linux start ticks, removes only an unchanged record inode after exit is proved, retains the record when bounded cleanup cannot prove exit, rejects unsafe runtime directories and token/log/lock aliases, and applies bounded TERM/KILL escalation. It is not an OS service installation, automatic restart system, reverse-proxy mode, container deployment, persistence layer, or remote production claim. The bundled client exposes neither an arbitrary server command nor caller-selected JSON-RPC IDs or unbounded retries. Starting, restarting, or stopping the HTTP listener remains an externally visible operator action and must not occur implicitly as fallback behavior.

Selected profiles: mcp-enabled
